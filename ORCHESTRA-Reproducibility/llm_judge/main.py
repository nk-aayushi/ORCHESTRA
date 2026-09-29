"""Main entry point for the LLM-as-Judge evaluation framework."""

import logging
import sys

from tqdm import tqdm

from config import MODEL_ID, OUTPUT_DIRECTORY
from evaluator import EvaluationResult, evaluate_single_case, should_skip
from loader import discover_cases
from utils import ensure_output_dirs, load_existing_results, write_master_csv

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(OUTPUT_DIRECTORY.parent / "evaluation.log", mode="a"),
    ],
)
logger = logging.getLogger(__name__)


def print_summary(results: list[EvaluationResult]) -> None:
    """Print final summary statistics."""
    successful = [r for r in results if r.success]
    failed = [r for r in results if not r.success]

    print("\n" + "=" * 60)
    print("EVALUATION SUMMARY")
    print("=" * 60)
    print(f"  Judge Model:      {MODEL_ID}")
    print(f"  Total Processed:  {len(results)}")
    print(f"  Successful:       {len(successful)}")
    print(f"  Failed:           {len(failed)}")

    if successful:
        metrics = ["hallucination", "completeness", "usefulness", "grounding"]
        print("\n  Average Scores:")
        for metric in metrics:
            scores = [r.scores[metric]["score"] for r in successful if r.scores]
            avg = sum(scores) / len(scores) if scores else 0.0
            print(f"    {metric.capitalize():20s} {avg:.2f}")

    if failed:
        print("\n  Failed Cases:")
        for r in failed:
            print(f"    - {r.cancer_type}/{r.case_id}: {r.error}")

    print("=" * 60)


def main() -> None:
    """Run the full evaluation pipeline."""
    ensure_output_dirs()
    logger.info("Starting evaluation pipeline")

    cases = discover_cases()
    if not cases:
        logger.error("No cases discovered. Check ROOT_EVALUATION_DIRECTORY in config.py")
        sys.exit(1)

    pending = [c for c in cases if not should_skip(c)]
    skipped = len(cases) - len(pending)
    if skipped:
        logger.info(f"Skipping {skipped} already-evaluated cases")

    results: list[EvaluationResult] = []
    for case in tqdm(pending, desc="Evaluating cases", unit="case"):
        result = evaluate_single_case(case)
        results.append(result)

    all_results = load_existing_results()
    if all_results:
        write_master_csv(all_results)

    print_summary(results)

    if not results:
        print("\nNo new cases to evaluate. All cases already processed.")


if __name__ == "__main__":
    main()
