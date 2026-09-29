"""Loader module for discovering and loading all 98 evaluation cases."""

import json
import logging
from dataclasses import dataclass
from pathlib import Path

from config import CONCORDANT_NEW_DIR, DISCORDANT_NEW_DIR

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
    variant: str
    report: str
    evidence: str
    source_dir: str  # "concordant-new" or "discordant-new"


def _load_single_json(folder: Path) -> dict | list | None:
    """Load the first JSON file found in a folder."""
    json_files = list(folder.glob("*.json"))
    if not json_files:
        return None
    with open(json_files[0], "r", encoding="utf-8") as f:
        return json.load(f)


def _get_variant_name(summary_dir: Path) -> str:
    """Extract variant name from the summary filename."""
    for f in summary_dir.glob("*.json"):
        return f.stem.replace("_summary", "")
    return ""


def _format_report(data: dict | list | None) -> str:
    """Extract report text from summary JSON."""
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
            continue
        data = _load_single_json(folder_path)
        if data is None:
            continue
        pretty = json.dumps(data, indent=2, ensure_ascii=False)
        sections.append(f"{'=' * 16} {label} {'=' * 16}\n\n{pretty}")
    return "\n\n".join(sections)


def _discover_from_dir(root: Path, source_label: str) -> list[Case]:
    """Discover cases from a single source directory."""
    cases: list[Case] = []
    if not root.exists():
        logger.error(f"Directory does not exist: {root}")
        return cases

    for cancer_folder in sorted(root.iterdir()):
        if not cancer_folder.is_dir():
            continue
        cancer_type = cancer_folder.name

        for case_folder in sorted(cancer_folder.iterdir(), key=lambda p: int(p.name) if p.name.isdigit() else 0):
            if not case_folder.is_dir() or not case_folder.name.isdigit():
                continue

            summary_dir = case_folder / "summary"
            if not summary_dir.exists():
                continue

            variant = _get_variant_name(summary_dir)
            if not variant:
                logger.warning(f"No variant found for {cancer_type}/{case_folder.name}")
                continue

            report_data = _load_single_json(summary_dir)
            report_text = _format_report(report_data)
            if not report_text:
                logger.warning(f"Empty report for {cancer_type}/{case_folder.name}")
                continue

            evidence_text = _format_evidence(case_folder)

            cases.append(Case(
                cancer_type=cancer_type,
                case_id=case_folder.name,
                variant=variant,
                report=report_text,
                evidence=evidence_text,
                source_dir=source_label,
            ))

    return cases


def discover_all_cases() -> list[Case]:
    """Discover all 98 cases from concordant-new and discordant-new."""
    concordant = _discover_from_dir(CONCORDANT_NEW_DIR, "concordant-new")
    discordant = _discover_from_dir(DISCORDANT_NEW_DIR, "discordant-new")
    all_cases = concordant + discordant
    logger.info(f"Discovered {len(concordant)} concordant + {len(discordant)} discordant = {len(all_cases)} total")
    return all_cases
