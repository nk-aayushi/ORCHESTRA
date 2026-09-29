# LLM-as-a-Judge: 12-Criterion Clinical Quality Evaluation

This directory contains the evaluation framework used to compare ORCHESTRA's generated reports across all 98 study cases on 12 structured clinical criteria. This is the framework behind the model comparison results reported in the paper (variant identification, biological interpretation, clinical significance, etc.).

This is distinct from `llm_judge/`, which contains a separate 4-score rubric used for the human-vs-LLM agreement analysis. This framework produces per-criterion PASS / minor issues / major issues verdicts plus an overall quality rating.

---

## Files

| File | Description |
|---|---|
| `main.py` | Entry point — discovers all 98 cases, runs evaluation, writes per-case JSON and master CSV |
| `judge.py` | Calls Claude via Bedrock, validates the 12-criterion JSON response |
| `loader.py` | Discovers cases from `concordant-new/` and `discordant-new/` directories |
| `prompts.py` | Verbatim system and user prompts |
| `config.py` | Model ID, directory paths, temperature, token settings |
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

## Study Cohort

- **98 total cases**: drawn from `study_jobs/concordant-new/` (cases where ORCHESTRA and the reference agreed) and `study_jobs/discordant-new/` (cases where they disagreed)
- Each case contains: a generated clinical summary (`summary/`) + raw database evidence (`clinvar_output/`, `civic_output/`, `oncokb_output/`, `output-filter_treatment_info/`)
- The judge receives both the report and the evidence bundle for each case

---

## The 12 Criteria

Each criterion is scored as one of: `PASS` | `minor issues` | `major issues` | `NOT_APPLICABLE`

For analysis, verdicts are mapped to numeric scores: PASS=3, minor issues=2, major issues=1, NOT_APPLICABLE=excluded from denominator.

| # | Criterion Key | Question asked to the judge |
|---|---|---|
| 1 | `variant_identification` | Does the report correctly identify and describe the genomic alteration? |
| 2 | `biological_interpretation` | Does the report correctly interpret the biological significance of the alteration? |
| 3 | `clinical_significance` | Does the report appropriately explain the clinical relevance of the alteration? |
| 4 | `therapeutic_recommendations` | Are the therapeutic recommendations medically appropriate? |
| 5 | `evidence_integration` | Does the report appropriately integrate evidence from databases and literature into a coherent interpretation? |
| 6 | `clinical_reasoning` | Does the report logically connect molecular findings to therapeutic conclusions? |
| 7 | `resistance_interpretation` | If resistance mechanisms are relevant for this alteration, are they correctly discussed? *(NOT_APPLICABLE if irrelevant)* |
| 8 | `clinical_trials` | If relevant clinical trials exist in the supplied evidence, are they appropriately discussed? *(NOT_APPLICABLE if irrelevant)* |
| 9 | `evidence_levels` | Are evidence levels correctly interpreted? *(NOT_APPLICABLE if evidence levels are unavailable)* |
| 10 | `safety` | Does the report avoid medically incorrect or potentially unsafe recommendations? |
| 11 | `hallucinations` | Does the report avoid fabricated facts, fabricated therapies, fabricated biomarkers, or unsupported conclusions? |
| 12 | `report_organization` | Is the report clear, concise, logically organized, and suitable for presentation during a molecular tumor board? |

**Overall quality** is rated as one of: `Excellent` | `Good` | `Acceptable` | `Poor` | `Unsafe`

Mapped to numeric scores: Excellent=5, Good=4, Acceptable=3, Poor=2, Unsafe=1.

---

## Prompts (Verbatim)

The exact prompts are in `prompts.py`. They are reproduced here in full.

### System Prompt

```
You are a board-certified molecular oncologist serving as an independent reviewer for a scientific benchmark evaluating AI-generated molecular interpretation reports.

Your task is NOT to rewrite the report.

Your task is NOT to improve the report.

Your task is ONLY to evaluate whether the report satisfies a series of objective clinical criteria.

The report should be evaluated exactly as it would be during a molecular tumor board.

General principles:

• Evaluate only what is written in the report.
• Use your oncology expertise together with the supplied evidence.
• Do not expect every medically correct statement to appear verbatim in the evidence.
• If a criterion is not applicable to this variant, answer "NOT_APPLICABLE".
• Do not infer information that is not present.
• Judge conservatively.

For every criterion:

Return

PASS

minor issues
major issues

or

NOT_APPLICABLE

followed by a brief explanation.

Finally provide

Overall Clinical Quality

rated as

Excellent
Good
Acceptable
Poor
Unsafe

Return ONLY valid JSON.
```

### User Prompt

```
Evaluate the following AI-generated molecular interpretation report.

====================================================
GENERATED REPORT
====================================================

{report}

====================================================
SUPPORTING EVIDENCE
====================================================

{evidence}

====================================================
EVALUATION RUBRIC
====================================================

Evaluate every criterion independently.

Criterion 1
Variant Identification

Question

Does the report correctly identify and describe the genomic alteration?

------------------------------------------------------------

Criterion 2
Biological Interpretation

Question

Does the report correctly interpret the biological significance of the alteration?

------------------------------------------------------------

Criterion 3
Clinical Significance

Question

Does the report appropriately explain the clinical relevance of the alteration?

------------------------------------------------------------

Criterion 4
Therapeutic Recommendations

Question

Are the therapeutic recommendations medically appropriate?

------------------------------------------------------------

Criterion 5
Evidence Integration

Question

Does the report appropriately integrate evidence from databases and literature into a coherent interpretation?

------------------------------------------------------------

Criterion 6
Clinical Reasoning

Question

Does the report logically connect molecular findings to therapeutic conclusions?

------------------------------------------------------------

Criterion 7
Resistance Interpretation

Question

If resistance mechanisms are relevant for this alteration, are they correctly discussed?

Return NOT_APPLICABLE if irrelevant.

------------------------------------------------------------

Criterion 8
Clinical Trials

Question

If relevant clinical trials exist in the supplied evidence, are they appropriately discussed?

Return NOT_APPLICABLE if irrelevant.

------------------------------------------------------------

Criterion 9
Evidence Levels

Question

Are evidence levels correctly interpreted?

Return NOT_APPLICABLE if evidence levels are unavailable.

------------------------------------------------------------

Criterion 10
Safety

Question

Does the report avoid medically incorrect or potentially unsafe recommendations?

------------------------------------------------------------

Criterion 11
Hallucinations

Question

Does the report avoid fabricated facts, fabricated therapies, fabricated biomarkers, or unsupported conclusions?

------------------------------------------------------------

Criterion 12
Report Organization

Question

Is the report clear, concise, logically organized, and suitable for presentation during a molecular tumor board?

====================================================
OUTPUT FORMAT
====================================================

Return ONLY JSON.

{
  "variant_identification":{"verdict":"PASS","reason":"..."},
  "biological_interpretation":{"verdict":"PASS","reason":"..."},
  "clinical_significance":{"verdict":"PASS","reason":"..."},
  "therapeutic_recommendations":{"verdict":"PASS","reason":"..."},
  "evidence_integration":{"verdict":"PASS","reason":"..."},
  "clinical_reasoning":{"verdict":"PASS","reason":"..."},
  "resistance_interpretation":{"verdict":"NOT_APPLICABLE","reason":"..."},
  "clinical_trials":{"verdict":"PASS","reason":"..."},
  "evidence_levels":{"verdict":"PASS","reason":"..."},
  "safety":{"verdict":"PASS","reason":"..."},
  "hallucinations":{"verdict":"PASS","reason":"..."},
  "report_organization":{"verdict":"PASS","reason":"..."},
  "overall_quality":"Excellent",
  "overall_summary":"2-4 sentence summary."
}
```

---

## Evidence Bundle Format

For each case, the judge receives all four database outputs concatenated into a single evidence document:

```
================ CIVIC ================

{ ... CIViC JSON ... }

================ CLINVAR ================

{ ... ClinVar JSON ... }

================ ONCOKB ================

{ ... OncoKB JSON ... }

================ FILTERED TREATMENT INFO ================

{ ... filtered PubMed JSON ... }
```

---

## Output

### Per-case JSON (`results/{CancerType}/{variant}.json`)

```json
{
  "variant_identification": {"verdict": "PASS", "reason": "..."},
  "biological_interpretation": {"verdict": "PASS", "reason": "..."},
  "clinical_significance": {"verdict": "minor issues", "reason": "..."},
  "therapeutic_recommendations": {"verdict": "PASS", "reason": "..."},
  "evidence_integration": {"verdict": "PASS", "reason": "..."},
  "clinical_reasoning": {"verdict": "PASS", "reason": "..."},
  "resistance_interpretation": {"verdict": "NOT_APPLICABLE", "reason": "..."},
  "clinical_trials": {"verdict": "PASS", "reason": "..."},
  "evidence_levels": {"verdict": "PASS", "reason": "..."},
  "safety": {"verdict": "PASS", "reason": "..."},
  "hallucinations": {"verdict": "PASS", "reason": "..."},
  "report_organization": {"verdict": "PASS", "reason": "..."},
  "overall_quality": "Good",
  "overall_quality_label": "Good",
  "overall_quality_score": 4,
  "overall_summary": "...",
  "cancer_type": "Non-Small_Cell_Lung_Cancer",
  "case_id": "9",
  "variant": "EGFR_p.L858R",
  "source_dir": "concordant-new"
}
```

### Master CSV (`results/master_scores.csv`)

One row per case with columns: `CancerType`, `Variant`, `CaseID`, `SourceDir`, one column per criterion (verdict string), `OverallQualityLabel`, `OverallQualityScore`, `OverallSummary`, `JudgeModel`.

---

## Running the Evaluation

```bash
# 1. Edit config.py to set CONCORDANT_NEW_DIR and DISCORDANT_NEW_DIR
#    to point to your study_jobs/ directories

# 2. Run
cd llm_judge_criteria/
python main.py
```

Idempotent: cases with existing result files are skipped. Re-run safely after interruption.

---

## Verdict Normalization

The judge module normalizes verdict strings case-insensitively before validation:

| Raw LLM output | Normalized to |
|---|---|
| `"PASS"`, `"pass"`, `"Pass"` | `"PASS"` |
| `"NOT_APPLICABLE"`, `"Not Applicable"`, `"not applicable"` | `"NOT_APPLICABLE"` |
| Any string containing `"minor"` | `"minor issues"` |
| Any string containing `"major"` | `"major issues"` |

Any other verdict causes a `JudgeError` and triggers a retry.
