"""Loader module for discovering and loading evaluation cases."""

import json
import logging
from dataclasses import dataclass
from pathlib import Path

from config import ROOT_EVALUATION_DIRECTORY

logger = logging.getLogger(__name__)

EVIDENCE_FOLDERS: dict[str, str] = {
    "civic_output": "CIVIC",
    "clinvar_output": "CLINVAR",
    "oncokb_output": "ONCOKB",
    "output-filter_treatment_info": "FILTERED TREATMENT INFO",
}


@dataclass
class Case:
    """Represents a single evaluation case."""
    cancer_type: str
    case_id: str
    report: str
    evidence: str


def _load_single_json(folder: Path) -> dict | list | None:
    """Load the first JSON file found in a folder."""
    json_files = list(folder.glob("*.json"))
    if not json_files:
        logger.warning(f"No JSON file found in {folder}")
        return None
    with open(json_files[0], "r", encoding="utf-8") as f:
        return json.load(f)


def _format_report(data: dict | list | None) -> str:
    """Extract and format the report text from summary JSON."""
    if data is None:
        return ""
    if isinstance(data, dict) and "summary" in data:
        return data["summary"]
    return json.dumps(data, indent=2, ensure_ascii=False)


def _format_evidence(case_folder: Path) -> str:
    """Load and format all evidence sources into a readable document."""
    sections: list[str] = []
    for folder_name, label in EVIDENCE_FOLDERS.items():
        folder_path = case_folder / folder_name
        if not folder_path.exists():
            logger.debug(f"Evidence folder missing: {folder_path}")
            continue
        data = _load_single_json(folder_path)
        if data is None:
            continue
        pretty = json.dumps(data, indent=2, ensure_ascii=False)
        sections.append(f"{'=' * 16} {label} {'=' * 16}\n\n{pretty}")
    return "\n\n".join(sections)


def discover_cases(root: Path | None = None) -> list[Case]:
    """Discover all evaluation cases in the directory structure."""
    root = root or ROOT_EVALUATION_DIRECTORY
    cases: list[Case] = []

    if not root.exists():
        logger.error(f"Root evaluation directory does not exist: {root}")
        return cases

    for cancer_folder in sorted(root.iterdir()):
        if not cancer_folder.is_dir():
            continue
        cancer_type = cancer_folder.name

        for case_folder in sorted(cancer_folder.iterdir(), key=lambda p: int(p.name) if p.name.isdigit() else 0):
            if not case_folder.is_dir() or not case_folder.name.isdigit():
                continue
            case_id = case_folder.name
            summary_folder = case_folder / "summary"

            if not summary_folder.exists():
                logger.warning(f"No summary folder for {cancer_type}/{case_id}")
                continue

            report_data = _load_single_json(summary_folder)
            report_text = _format_report(report_data)

            if not report_text:
                logger.warning(f"Empty report for {cancer_type}/{case_id}")
                continue

            evidence_text = _format_evidence(case_folder)

            cases.append(Case(
                cancer_type=cancer_type,
                case_id=case_id,
                report=report_text,
                evidence=evidence_text,
            ))
            logger.info(f"Loaded case: {cancer_type}/{case_id}")

    logger.info(f"Discovered {len(cases)} total cases")
    return cases
