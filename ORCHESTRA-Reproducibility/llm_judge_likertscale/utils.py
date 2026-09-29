"""Utility functions for file I/O and results management."""

import csv
import json
import logging
from pathlib import Path

from config import MODEL_ID, OUTPUT_DIRECTORY

logger = logging.getLogger(__name__)

MASTER_CSV_COLUMNS = [
    "CancerType",
    "CaseID",
    "Hallucination",
    "Completeness",
    "Usefulness",
    "Grounding",
    "OverallComments",
    "JudgeModel",
]


def ensure_output_dirs() -> None:
    """Create the output directory structure."""
    OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)


def get_result_path(cancer_type: str, case_id: str) -> Path:
    """Get the path where a case result JSON should be saved."""
    folder = OUTPUT_DIRECTORY / cancer_type
    folder.mkdir(parents=True, exist_ok=True)
    return folder / f"{case_id}.json"


def is_already_evaluated(cancer_type: str, case_id: str) -> bool:
    """Check if a case has already been evaluated."""
    return get_result_path(cancer_type, case_id).exists()


def save_result(cancer_type: str, case_id: str, result: dict) -> Path:
    """Save a single evaluation result as JSON."""
    path = get_result_path(cancer_type, case_id)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    logger.info(f"Saved result: {path}")
    return path


def write_master_csv(results: list[dict]) -> Path:
    """Write the master CSV containing all evaluation scores."""
    csv_path = OUTPUT_DIRECTORY / "master_scores.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=MASTER_CSV_COLUMNS)
        writer.writeheader()
        for r in results:
            writer.writerow({
                "CancerType": r["cancer_type"],
                "CaseID": r["case_id"],
                "Hallucination": r["hallucination"]["score"],
                "Completeness": r["completeness"]["score"],
                "Usefulness": r["usefulness"]["score"],
                "Grounding": r["grounding"]["score"],
                "OverallComments": r["overall_comments"],
                "JudgeModel": MODEL_ID,
            })
    logger.info(f"Master CSV written: {csv_path}")
    return csv_path


def load_existing_results() -> list[dict]:
    """Load all previously saved result JSON files."""
    results: list[dict] = []
    if not OUTPUT_DIRECTORY.exists():
        return results
    for cancer_folder in OUTPUT_DIRECTORY.iterdir():
        if not cancer_folder.is_dir() or cancer_folder.name == "__pycache__":
            continue
        for json_file in cancer_folder.glob("*.json"):
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                results.append(data)
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(f"Skipping malformed result: {json_file} - {e}")
    return results
