"""Judge module for calling Claude through AWS Bedrock and parsing responses."""

import json
import logging
import re
import time
from typing import Any

import boto3

from config import AWS_REGION, MAX_RETRIES, MAX_TOKENS, MODEL_ID, TEMPERATURE
from prompts import SYSTEM_PROMPT, USER_PROMPT

logger = logging.getLogger(__name__)

REQUIRED_KEYS = {"hallucination", "completeness", "usefulness", "grounding", "overall_comments"}
SCORE_KEYS = {"hallucination", "completeness", "usefulness", "grounding"}


class JudgeError(Exception):
    """Raised when the judge fails to produce a valid evaluation."""
    pass


def _create_client() -> Any:
    """Create a Bedrock Runtime client."""
    return boto3.client("bedrock-runtime", region_name=AWS_REGION)


def _extract_json(text: str) -> str:
    """Extract JSON from response text, handling markdown code blocks."""
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        return match.group(1)
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        return match.group(0)
    return text


def _validate_scores(result: dict) -> dict:
    """Validate that the parsed result has the correct structure and score ranges."""
    for key in REQUIRED_KEYS:
        if key not in result:
            raise JudgeError(f"Missing required key: {key}")

    for key in SCORE_KEYS:
        entry = result[key]
        if not isinstance(entry, dict):
            raise JudgeError(f"'{key}' must be a dict with 'score' and 'reason'")
        if "score" not in entry or "reason" not in entry:
            raise JudgeError(f"'{key}' must contain 'score' and 'reason'")
        score = entry["score"]
        if not isinstance(score, (int, float)) or not (1 <= score <= 5):
            raise JudgeError(f"'{key}' score must be 1-5, got {score}")
        entry["score"] = int(score)

    return result


def _parse_response(text: str) -> dict:
    """Parse and validate the LLM response into structured scores."""
    json_str = _extract_json(text)
    try:
        result = json.loads(json_str)
    except json.JSONDecodeError as e:
        cleaned = re.sub(r",\s*([}\]])", r"\1", json_str)
        try:
            result = json.loads(cleaned)
        except json.JSONDecodeError:
            raise JudgeError(f"Failed to parse JSON: {e}\nRaw text: {text[:500]}")

    return _validate_scores(result)


def evaluate_case(report: str, evidence: str) -> dict:
    """Send a report and evidence to the LLM judge and return structured scores."""
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
            logger.info(f"Judge evaluation successful on attempt {attempt}")
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
