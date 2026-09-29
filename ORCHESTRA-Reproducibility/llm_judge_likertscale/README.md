# LLM-as-a-Judge Evaluation Framework

This directory contains the automated evaluation framework used to score ORCHESTRA's generated clinical summaries. An LLM (Claude Sonnet 4) acts as a judge, evaluating each report on four clinical quality criteria.

---

## Overview

For each of the 98 study cases, the judge receives:
1. The generated clinical summary (report)
2. The raw database evidence used to generate it (ClinVar + CIViC + OncoKB + filtered PubMed)

The judge scores the report on four criteria, each on a 1–5 scale, and returns a JSON object with scores and brief reasoning.

---

## Files

| File | Description |
|---|---|
| `main.py` | Entry point — discovers cases, runs evaluation, writes results |
| `judge.py` | Calls Claude via Bedrock, parses and validates the JSON response |
| `evaluator.py` | Per-case evaluation logic (loads report + evidence, calls judge) |
| `loader.py` | Discovers evaluation cases from the study_jobs directory |
| `utils.py` | CSV writing and result loading utilities |
| `prompts.py` | Verbatim system and user prompts |
| `config.py` | Model ID, paths, temperature, token settings |
| `requirements.txt` | Python dependencies |

---

## Model Settings

| Parameter | Value |
|---|---|
| Model | Claude Sonnet 4 |
| Model ID | `global.anthropic.claude-sonnet-4-6` |
| API | AWS Bedrock `bedrock-runtime`, `us-east-1` |
| `temperature` | 0.0 |
| `max_tokens` | 4096 |
| `anthropic_version` | `bedrock-2023-05-31` |
| Max retries | 3 (exponential backoff: 2^attempt seconds) |

---

## Scoring Rubric

### Criterion 1: Hallucination (1–5)

**Question**: Does the report contain statements that are incorrect, fabricated, or inconsistent with either the supplied evidence or well-established oncology knowledge?

> The judge is instructed NOT to penalize medically correct background knowledge simply because it is not explicitly present in the retrieved evidence.

| Score | Meaning |
|---|---|
| 5 | No hallucinations. Medically accurate, no fabricated or clinically misleading statements. |
| 4 | Rare hallucinations. One or two minor unsupported statements that do not affect clinical interpretation. |
| 3 | Occasional hallucinations. Some unsupported or questionable statements that could require clarification. |
| 2 | Frequent hallucinations. Multiple clinically important unsupported or incorrect statements. |
| 1 | Severe hallucinations. Numerous fabricated or medically incorrect claims that could lead to unsafe clinical decisions. |

### Criterion 2: Completeness (1–5)

**Question**: Does the report omit important clinical information necessary for accurate interpretation or clinical decision-making?

> The judge is instructed to focus only on clinically meaningful omissions, not background information or redundant details.

| Score | Meaning |
|---|---|
| 5 | No important clinical information is missing. |
| 4 | Minor omissions that would not change clinical interpretation or treatment decisions. |
| 3 | Moderate omissions. Some clinically relevant information is missing, but interpretation remains possible. |
| 2 | Major omissions that could affect treatment decisions or variant interpretation. |
| 1 | Critical omissions making the report incomplete or potentially misleading. |

### Criterion 3: Clinical Usefulness (1–5)

**Question**: How useful would this report be during a real-world molecular tumor board discussion?

Considers: clarity, organization, interpretation, prioritization, therapeutic recommendations, overall clinical utility.

| Score | Meaning |
|---|---|
| 5 | Extremely useful. Could directly support clinical decision-making. |
| 4 | Very useful. Minor improvements could enhance usability. |
| 3 | Moderately useful. Helpful but additional review would be required before making decisions. |
| 2 | Slightly useful. Important information is missing or poorly organized. |
| 1 | Not useful for clinical decision-making. |

### Criterion 4: Evidence Grounding (1–5)

**Question**: To what extent are the major clinical interpretations and therapeutic recommendations supported by appropriate evidence?

> The judge is instructed NOT to require every medically correct statement to have an explicit citation, and NOT to evaluate citation formatting.

| Score | Meaning |
|---|---|
| 5 | Fully grounded. Major interpretations and recommendations are well supported by the available evidence. |
| 4 | Mostly grounded. Minor claims have weaker support but the important conclusions are evidence-based. |
| 3 | Partially grounded. Some important claims lack sufficient evidence support. |
| 2 | Weak grounding. Several major conclusions are inadequately supported. |
| 1 | Not grounded. Most important conclusions are unsupported by the available evidence. |

---

## Prompts (Verbatim)

The exact prompts are in `prompts.py`. They are reproduced here for reference.

### System Prompt

```
You are a board-certified molecular oncologist with expertise in molecular tumor boards (MTBs), precision oncology, and clinical genomic interpretation.

Your role is to evaluate a molecular interpretation report in the same way an experienced physician would evaluate it during a scientific study.

IMPORTANT PRINCIPLES

• You are ONLY evaluating the report.
• Do NOT rewrite, improve, or suggest edits.
• Use the retrieved evidence as the PRIMARY basis for your evaluation.
• You MAY use well-established oncology knowledge and standard clinical practice when determining whether statements are medically correct.
• Do NOT penalize a report simply because a medically correct statement is not explicitly written in the retrieved evidence.
• Do NOT reward unsupported speculation.
• Evaluate the report exactly as a clinician would: determine whether it is accurate, complete, clinically useful, and appropriately supported by evidence.

When assigning scores:

• Base your decision on the overall quality of the report, not isolated sentences.
• Provide concise but specific reasoning.

[... full rubric definitions for all 4 criteria ...]

Before assigning each score:

1. Consider evidence supporting the report.
2. Consider evidence contradicting the report.
3. Compare the report against the scoring rubric.
4. Assign the single best score.

Do NOT reveal your reasoning process.

Return ONLY a valid JSON object.
```

### User Prompt

```
Evaluate the following molecular interpretation report.

═══════════════════════════════════════════════════════════════
GENERATED REPORT
═══════════════════════════════════════════════════════════════

{report}

═══════════════════════════════════════════════════════════════
RETRIEVED EVIDENCE
═══════════════════════════════════════════════════════════════

{evidence}

═══════════════════════════════════════════════════════════════
INSTRUCTIONS
═══════════════════════════════════════════════════════════════

Evaluate the report as an experienced molecular oncologist.

Use the retrieved evidence as the primary basis for evaluation while allowing well-established oncology knowledge when determining whether statements are medically correct.

Do NOT require every medically correct statement to appear verbatim in the retrieved evidence.

Judge the report according to the four criteria defined in the system prompt.

Return ONLY valid JSON using the following structure.

{
    "hallucination": {
        "score": <integer 1-5>,
        "reason": "<brief explanation>"
    },
    "completeness": {
        "score": <integer 1-5>,
        "reason": "<brief explanation>"
    },
    "usefulness": {
        "score": <integer 1-5>,
        "reason": "<brief explanation>"
    },
    "grounding": {
        "score": <integer 1-5>,
        "reason": "<brief explanation>"
    },
    "overall_comments": "<2-4 sentence overall assessment>"
}

Return ONLY the JSON object.
```

---

## Output Format

The judge returns a JSON object. The pipeline validates that:
- All four score keys are present
- Each score is an integer between 1 and 5
- `overall_comments` is present

If validation fails, the call is retried up to 3 times. On final failure, the case is marked as failed and logged.

**Example output**:
```json
{
    "hallucination": {
        "score": 4,
        "reason": "One minor unsupported claim about resistance mechanism not present in evidence."
    },
    "completeness": {
        "score": 5,
        "reason": "All clinically significant findings from ClinVar, OncoKB, and PubMed are represented."
    },
    "usefulness": {
        "score": 4,
        "reason": "Clear therapeutic recommendations with evidence levels; minor formatting issues."
    },
    "grounding": {
        "score": 4,
        "reason": "Major conclusions cite OncoKB and PubMed; one claim lacks explicit source."
    },
    "overall_comments": "The report is clinically accurate and well-organized..."
}
```

---

## Running the Evaluation

```bash
# 1. Configure paths in config.py:
#    ROOT_EVALUATION_DIRECTORY — path to study_jobs/Evaluation/
#    OUTPUT_DIRECTORY          — where to write results

# 2. Run
cd llm_judge/
python main.py
```

Results are written to `{OUTPUT_DIRECTORY}/` as individual JSON files per case and a master `all_evaluations.csv`.

**Idempotency**: Cases with existing result files are skipped automatically.

---

## Human Evaluation

In addition to the automated LLM judge, human expert evaluation was collected via `study_app.py` (in the main repository). Human evaluators used the same four criteria and the same 1–5 scale, presented through a Streamlit interface. Human responses are stored in `study_responses/all_evaluations.csv`.

The human evaluation rubric (presented to evaluators) mirrors the LLM judge rubric exactly, ensuring comparability between automated and human scores.
