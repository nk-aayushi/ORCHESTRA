"""Main entry point for the criteria-based LLM evaluation framework.

Evaluates all 98 cases from concordant-new and discordant-new.
"""

import csv
import json
import logging
import sys
from pathlib import Path

from tqdm import tqdm

from config import MODEL_ID, OUTPUT_DIRECTORY, QUALITY_TO_SCORE
from judge import evaluate_case, JudgeError, CRITERIA_KEYS
from loader import Case, discover_all_cases

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(OUTPUT_DIRECTORY.parent / "evaluation.log", mode="a"),
    ],
)
logger = logging.getLogger(__name__)

VERDICT_TO_SCORE: dict[str, int | None] = {
    "PASS": 3,
    "minor issues": 2,
    "major issues": 1,
    "NOT_APPLICABLE": None,
}


def get_result_path(cancer_type: str, variant: str) -> Path:
    """Get result path keyed by cancer_type/variant."""
    folder = OUTPUT_DIRECTORY / cancer_type
    folder.mkdir(parents=True, exist_ok=True)
    return folder / f"{variant}.json"


def is_already_evaluated(cancer_type: str, variant: str) -> bool:
    """Check if already evaluated."""
    return get_result_path(cancer_type, variant).exists()


def save_result(case: Case, result: dict) -> Path:
    """Save evaluation result."""
    result["cancer_type"] = case.cancer_type
    result["case_id"] = case.case_id
    result["variant"] = case.variant
    result["source_dir"] = case.source_dir
    path = get_result_path(case.cancer_type, case.variant)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    return path


def write_master_csv(results: list[dict]) -> Path:
    """Write master CSV with all criteria verdicts and overall quality."""
    csv_path = OUTPUT_DIRECTORY / "master_scores.csv"
    columns = [
        "CancerType", "Variant", "CaseID", "SourceDir",
        *[c for c in CRITERIA_KEYS],
        "OverallQualityLabel", "OverallQualityScore", "OverallSummary", "JudgeModel",
    ]
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        for r in results:
            row = {
                "CancerType": r["cancer_type"],
                "Variant": r["variant"],
                "CaseID": r["case_id"],
                "SourceDir": r.get("source_dir", ""),
                "OverallQualityLabel": r.get("overall_quality_label", ""),
                "OverallQualityScore": r.get("overall_quality_score", ""),
                "OverallSummary": r.get("overall_summary", ""),
                "JudgeModel": MODEL_ID,
            }
            for criterion in CRITERIA_KEYS:
                row[criterion] = r[criterion]["verdict"] if criterion in r else ""
            writer.writerow(row)
    logger.info(f"Master CSV: {csv_path}")
    return csv_path


def load_existing_results() -> list[dict]:
    """Load all previously saved results."""
    results: list[dict] = []
    if not OUTPUT_DIRECTORY.exists():
        return results
    for cancer_folder in OUTPUT_DIRECTORY.iterdir():
        if not cancer_folder.is_dir():
            continue
        for json_file in cancer_folder.glob("*.json"):
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    results.append(json.load(f))
            except (json.JSONDecodeError, KeyError):
                pass
    return results


def print_summary(successful: int, failed: int, results: list[dict]) -> None:
    """Print final summary with pass rates and quality distribution."""
    print("\n" + "=" * 70)
    print("CRITERIA-BASED EVALUATION SUMMARY")
    print("=" * 70)
    print(f"  Model:        {MODEL_ID}")
    print(f"  Successful:   {successful}")
    print(f"  Failed:       {failed}")

    if not results:
        print("=" * 70)
        return

    # Pass rate per criterion
    print(f"\n  PASS RATES PER CRITERION (excluding NOT_APPLICABLE):")
    print(f"  {'Criterion':<30} {'PASS':<7} {'Minor':<7} {'Major':<7} {'N/A':<5} {'Pass%':<7}")
    print("  " + "-" * 63)
    for criterion in CRITERIA_KEYS:
        verdicts = [r[criterion]["verdict"] for r in results if criterion in r]
        n_pass = verdicts.count("PASS")
        n_minor = verdicts.count("minor issues")
        n_major = verdicts.count("major issues")
        n_na = verdicts.count("NOT_APPLICABLE")
        applicable = len(verdicts) - n_na
        pass_rate = (n_pass / applicable * 100) if applicable > 0 else 0
        print(f"  {criterion:<30} {n_pass:<7} {n_minor:<7} {n_major:<7} {n_na:<5} {pass_rate:<7.1f}")

    # Overall quality distribution
    print(f"\n  OVERALL QUALITY DISTRIBUTION:")
    quality_scores = [r.get("overall_quality_score", 0) for r in results]
    labels = {5: "Excellent", 4: "Good", 3: "Acceptable", 2: "Poor", 1: "Unsafe"}
    for score in [5, 4, 3, 2, 1]:
        count = quality_scores.count(score)
        pct = count / len(results) * 100
        print(f"    {labels[score]:<12} ({score}): {count:>3} ({pct:5.1f}%)")
    avg = sum(quality_scores) / len(quality_scores)
    print(f"\n    Average quality score: {avg:.2f}")

    print("=" * 70)


def main() -> None:
    OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)

    # Discover all cases
    cases = discover_all_cases()
    if not cases:
        logger.error("No cases discovered.")
        sys.exit(1)

    # Filter already evaluated
    pending = [c for c in cases if not is_already_evaluated(c.cancer_type, c.variant)]
    skipped = len(cases) - len(pending)
    if skipped:
        logger.info(f"Skipping {skipped} already-evaluated cases")

    # Evaluate
    successful = 0
    failed = 0
    for case in tqdm(pending, desc="Evaluating cases", unit="case"):
        try:
            result = evaluate_case(report=case.report, evidence=case.evidence)
            save_result(case, result)
            successful += 1
        except (JudgeError, Exception) as e:
            logger.error(f"Failed {case.cancer_type}/{case.variant}: {e}")
            failed += 1

    # Load all results and write CSV
    all_results = load_existing_results()
    if all_results:
        write_master_csv(all_results)

    print_summary(successful, failed, all_results)

    if not pending:
        print("\nNo new cases to evaluate. All cases already processed.")


if __name__ == "__main__":
    main()
