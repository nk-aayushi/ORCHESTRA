"""Evaluator module that orchestrates the evaluation pipeline for all cases."""

import logging
from dataclasses import dataclass

from loader import Case
from judge import evaluate_case, JudgeError
from utils import is_already_evaluated, save_result

logger = logging.getLogger(__name__)


@dataclass
class EvaluationResult:
    """Result of evaluating a single case."""
    cancer_type: str
    case_id: str
    success: bool
    scores: dict | None = None
    error: str | None = None


def evaluate_single_case(case: Case) -> EvaluationResult:
    """Evaluate a single case and save the result."""
    try:
        scores = evaluate_case(report=case.report, evidence=case.evidence)
        scores["cancer_type"] = case.cancer_type
        scores["case_id"] = case.case_id
        save_result(case.cancer_type, case.case_id, scores)
        return EvaluationResult(
            cancer_type=case.cancer_type,
            case_id=case.case_id,
            success=True,
            scores=scores,
        )
    except (JudgeError, Exception) as e:
        logger.error(f"Failed to evaluate {case.cancer_type}/{case.case_id}: {e}")
        return EvaluationResult(
            cancer_type=case.cancer_type,
            case_id=case.case_id,
            success=False,
            error=str(e),
        )


def should_skip(case: Case) -> bool:
    """Check if a case should be skipped (already evaluated)."""
    return is_already_evaluated(case.cancer_type, case.case_id)
