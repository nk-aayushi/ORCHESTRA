# Prompts: All LLM Prompts and Settings

This directory contains the exact prompts used at every LLM call in ORCHESTRA, along with model IDs, temperature, and token settings. No prompt has been paraphrased or summarized — these are the verbatim strings passed to the models.

---

## Prompt Index

| File | Pipeline Step | Model | Purpose |
|---|---|---|---|
| `literature_filtering_prompt.md` | Step 2 (`script3_filter.py`) | Claude Sonnet 4.5 | Classify each retrieved paper as relevant or not; extract treatment information |
| `clinical_summary_prompt.md` | Step 3 (`generate_summary.py`) | Claude Opus 4.5 | Synthesize all database evidence into a structured clinical report |
| `therapy_extraction_prompt.md` | Comparative study (`run_batch.py`) | Claude Sonnet 4 | Extract a tier-labeled therapy list from a generated summary |

The LLM-as-a-Judge prompts are documented in their respective directories:

| Directory | Prompt file | Purpose |
|---|---|---|
| `../llm_judge_criteria/prompts.py` | 12-criterion rubric | Model comparison across 98 cases (variant identification, biological interpretation, clinical significance, therapeutic recommendations, evidence integration, clinical reasoning, resistance interpretation, clinical trials, evidence levels, safety, hallucinations, report organization) |
| `../llm_judge/prompts.py` | 4-score rubric | Human-vs-LLM agreement analysis (hallucination, completeness, usefulness, grounding) |

---

## Model Settings Summary

### Literature Filtering (Step 2)

| Parameter | Value |
|---|---|
| Model | Claude Sonnet 4.5 |
| Model ID | `global.anthropic.claude-sonnet-4-5-20250929-v1:0` |
| API | AWS Bedrock `bedrock-runtime`, `us-east-1` |
| `max_tokens` | 6000 |
| `temperature` | not set (Bedrock default) |
| `anthropic_version` | `bedrock-2023-05-31` |
| Concurrency | ThreadPoolExecutor, max_workers=5 |
| Rate limiting | Custom token-bucket limiter (max 9999 calls / 60 s window) |

Two prompt variants are used depending on paper type:
- **Abstract batch prompt**: processes up to 5 abstracts in a single call, returns a JSON array
- **PMC full-text prompt**: processes one full paper per call, returns a JSON object

### Clinical Summary (Step 3)

| Parameter | Value |
|---|---|
| Model | Claude Opus 4.5 |
| Model ID | `global.anthropic.claude-opus-4-5-20251101-v1:0` |
| API | AWS Bedrock `bedrock-runtime`, `us-east-1` |
| `max_tokens` | 4000 |
| `temperature` | not set (Bedrock default) |
| `anthropic_version` | `bedrock-2023-05-31` |

### Therapy Extraction (Comparative Study)

| Parameter | Value |
|---|---|
| Model | Claude Sonnet 4 |
| Model ID | `global.anthropic.claude-sonnet-4-6` |
| API | AWS Bedrock `bedrock-runtime`, `us-east-1` |
| `max_tokens` | 2000 |
| `temperature` | 0 |
| `anthropic_version` | `bedrock-2023-05-31` |

---

## Output Format Notes

### Literature Filtering

The LLM is instructed to return **only valid JSON** — either an array (abstract batch) or an object (PMC single). The pipeline uses a JSON extractor that strips markdown code fences and HTML entities before parsing.

If the LLM returns malformed JSON, the paper is treated as not relevant (conservative fallback).

### Clinical Summary

The LLM returns free-text markdown. No JSON parsing is applied. The full text is stored verbatim in the `summary` field of the output JSON.

### Therapy Extraction

The LLM returns a free-text explanation followed by a structured last line:
```
THERAPIES: DrugA (Level 1), DrugB (Level 3), DrugC
```
The pipeline extracts only the last line starting with `THERAPIES:`.
