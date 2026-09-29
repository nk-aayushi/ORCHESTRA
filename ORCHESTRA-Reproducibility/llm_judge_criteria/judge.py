"""Judge module for calling Claude through AWS Bedrock with criteria-based evaluation."""

import json
import logging
import re
import time
from typing import Any

import boto3

from config import AWS_REGION, MAX_RETRIES, MAX_TOKENS, MODEL_ID, TEMPERATURE, QUALITY_TO_SCORE
from prompts import SYSTEM_PROMPT, USER_PROMPT

logger = logging.getLogger(__name__)

CRITERIA_KEYS = [
    "variant_identification",
    "biological_interpretation",
    "clinical_significance",
    "therapeutic_recommendations",
    "evidence_integration",
    "clinical_reasoning",
    "resistance_interpretation",
    "clinical_trials",
    "evidence_levels",
    "safety",
    "hallucinations",
    "report_organization",
]

VALID_VERDICTS = {"PASS", "minor issues", "major issues", "NOT_APPLICABLE"}


class JudgeError(Exception):
    """Raised when the judge fails to produce a valid evaluation."""
    pass


def _create_client() -> Any:
    """Create a Bedrock Runtime client."""
    return boto3.client("bedrock-runtime", region_name=AWS_REGION)


def _extract_json(text: str) -> str:
    """Extract JSON from response text."""
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        return match.group(1)
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        return match.group(0)
    return text


def _validate_result(result: dict) -> dict:
    """Validate the criteria-based result structure."""
    for key in CRITERIA_KEYS:
        if key not in result:
            raise JudgeError(f"Missing criterion: {key}")
        entry = result[key]
        if not isinstance(entry, dict):
            raise JudgeError(f"'{key}' must be a dict with 'verdict' and 'reason'")
        if "verdict" not in entry or "reason" not in entry:
            raise JudgeError(f"'{key}' must contain 'verdict' and 'reason'")
        # Normalize verdict
        verdict = entry["verdict"].strip()
        # Handle case variations
        verdict_lower = verdict.lower()
        if verdict_lower == "pass":
            entry["verdict"] = "PASS"
        elif verdict_lower == "not_applicable" or verdict_lower == "not applicable":
            entry["verdict"] = "NOT_APPLICABLE"
        elif "minor" in verdict_lower:
            entry["verdict"] = "minor issues"
        elif "major" in verdict_lower:
            entry["verdict"] = "major issues"
        else:
            raise JudgeError(f"Invalid verdict for '{key}': {verdict}")

    if "overall_quality" not in result:
        raise JudgeError("Missing 'overall_quality'")

    # Normalize and convert overall_quality to numeric score
    quality = result["overall_quality"].strip().lower()
    if quality not in QUALITY_TO_SCORE:
        raise JudgeError(f"Invalid overall_quality: {result['overall_quality']}")
    result["overall_quality_label"] = result["overall_quality"].strip()
    result["overall_quality_score"] = QUALITY_TO_SCORE[quality]

    return result


def _parse_response(text: str) -> dict:
    """Parse and validate the LLM response."""
    json_str = _extract_json(text)
    try:
        result = json.loads(json_str)
    except json.JSONDecodeError as e:
        cleaned = re.sub(r",\s*([}\]])", r"\1", json_str)
        try:
            result = json.loads(cleaned)
        except json.JSONDecodeError:
            raise JudgeError(f"Failed to parse JSON: {e}\nRaw: {text[:500]}")
    return _validate_result(result)


def evaluate_case(report: str, evidence: str) -> dict:
    """Send report and evidence to the LLM judge, return criteria-based scores."""
    client = _create_client()
    user_message = USER_PROMPT.format(report=report, evidence=evidence)

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = client.invoke_model(
                modelId=MODEL_ID,
                contentType="application/json",
                accept="application/json",
                body=json.dumps({
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": MAX_TOKENS,
                    "temperature": TEMPERATURE,
                    "system": SYSTEM_PROMPT,
                    "messages": [
                        {"role": "user", "content": user_message}
                    ],
                }),
            )
            body = json.loads(response["body"].read())
            text = body["content"][0]["text"]
            result = _parse_response(text)
            logger.info(f"Judge successful on attempt {attempt}")
            return result

        except JudgeError as e:
            logger.warning(f"Attempt {attempt}/{MAX_RETRIES} - validation error: {e}")
            if attempt == MAX_RETRIES:
                raise
        except Exception as e:
            logger.warning(f"Attempt {attempt}/{MAX_RETRIES} - API error: {e}")
            if attempt == MAX_RETRIES:
                raise JudgeError(f"Failed after {MAX_RETRIES} attempts: {e}")
            time.sleep(2 ** attempt)

    raise JudgeError("Exhausted all retries")
