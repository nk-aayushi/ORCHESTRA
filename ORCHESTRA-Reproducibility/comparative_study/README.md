# Comparative Study

This directory contains the scripts used to compare ORCHESTRA's therapy recommendations against the MOAlmanac ground truth and against direct LLM baselines (GPT-4o, Claude Opus 4.5).

---

## Study Design

The comparative study evaluates whether ORCHESTRA's evidence-grounded therapy recommendations agree with the MOAlmanac (Molecular Oncology Almanac) curated ground truth.

**Ground truth source**: MOAlmanac — a manually curated database of variant-to-therapy associations with evidence levels. The study cohort was drawn from MOAlmanac entries covering the cancer types represented in the clinical cases.

**Comparison systems**:

| System | Description |
|---|---|
| ORCHESTRA | Full pipeline (database retrieval → LLM filtering → summary → therapy extraction) |
| GPT-4o baseline | Direct query to GPT-4o with variant + cancer type, no retrieved evidence |
| Claude Opus 4.5 baseline | Same direct query, Claude Opus 4.5 via AWS Bedrock |

The baseline systems represent what LLMs know from parametric knowledge alone, without any retrieval augmentation.

---

## Files

| File | Description |
|---|---|
| `run_baseline_gpt4o.py` | Queries GPT-4o for each unique (gene, protein_change, cancer_type) in the study cohort |
| `run_claude_batch_benchmark.py` | Submits Claude Opus 4.5 and Sonnet 4 as AWS Bedrock batch inference jobs |
| `classify_therapies.py` | Classifies each system's therapy output against MOAlmanac ground truth |

---

## Input Data

All scripts read from `batch_results_comparison.csv`, which has the following columns:

| Column | Description |
|---|---|
| `Biomarker` | Variant string, e.g. `EGFR p.L858R` |
| `Gene` | Gene symbol |
| `Protein_Change` | Protein change |
| `Cancer Type` | Cancer type string |
| `Therapies` | MOAlmanac ground-truth therapies (comma-separated) |
| `Our_Therapies` | ORCHESTRA therapy output (comma-separated, with level labels) |

This file is produced by `run_batch.py` in the main pipeline directory (not included here due to patient data considerations; available upon request).

---

## Running the GPT-4o Baseline (`run_baseline_gpt4o.py`)

**Requirements**: OpenAI API key, `openai` Python package

```bash
# Set your API key in the script (API_KEY variable) or via environment variable
python run_baseline_gpt4o.py
```

**Input**: `batch_results_comparison.csv`  
**Output**: `baseline_chatgpt_results.csv`

The script deduplicates by (Gene, Protein_Change, Cancer Type) and queries GPT-4o once per unique variant. A 1-second sleep is applied between calls for rate limiting.

**Model settings**:
- Model: `gpt-4o`
- Temperature: 0
- No system prompt

---

## Running the Claude Batch Benchmark (`run_claude_batch_benchmark.py`)

Uses AWS Bedrock Batch Inference (minimum 100 records per job).

```bash
# Step 1: Generate JSONL input files and upload to S3
python run_claude_batch_benchmark.py --generate

# Step 2: Submit batch inference jobs
python run_claude_batch_benchmark.py --submit

# Step 3: Check job status
python run_claude_batch_benchmark.py --status

# Step 4: Download results and parse into CSV
python run_claude_batch_benchmark.py --parse
```

**Models submitted**:
- Claude Opus 4.5: `global.anthropic.claude-opus-4-5-20251101-v1:0`
- Claude Sonnet 4: `global.anthropic.claude-sonnet-4-6`

**S3 bucket**: `orchestra-claude-benchmark`  
**IAM role**: Must have S3 read/write and Bedrock InvokeModel permissions

**Model settings** (both models):
- Temperature: 0
- Max tokens: 4000
- `anthropic_version`: `bedrock-2023-05-31`

**Output**: `claude_batch/claude_benchmark_results.csv`

---

## Classifying Therapies (`classify_therapies.py`)

After generating therapy lists from any system, classify each against the MOAlmanac ground truth:

```bash
# Edit INPUT and OUTPUT variables at top of script, then:
python classify_therapies.py
```

**Input**: CSV with `Therapies` (ground truth) and `Our_Therapies` (system output) columns  
**Output**: CSV with added classification columns

**Classification logic**:

ORCHESTRA therapy output uses the format:
```
Osimertinib, Erlotinib (Level 2), Afatinib (Level 2)
```

Therapies without a level label are treated as Tier 1 (FDA-approved). Therapies with `(Level N)` are treated as other-tier.

Each ground-truth therapy is then looked up in the system output:

| Result | Meaning |
|---|---|
| Found in Tier 1 set | Therapy present and classified as FDA-approved |
| Found in other-tier set | Therapy present but at a lower evidence level |
| Not found | Therapy absent from system output |

**Output columns added**:

| Column | Description |
|---|---|
| `Our_Tier1_Therapies` | Therapies ORCHESTRA classified as Tier 1 |
| `Our_Other_Tier_Therapies` | Therapies ORCHESTRA classified as Level 2/3/4 |
| `Match_Category` | One of: `All Present as Tier 1`, `All Present as Different Tier`, `All Absent`, `Partially Present`, `No Therapies Listed` |
| `Matched_Tier1` | Ground-truth therapies found in Tier 1 |
| `Matched_Other_Tier` | Ground-truth therapies found at other tiers |
| `Not_Found` | Ground-truth therapies absent from output |

---

## Rare Variant Sub-Study

The `rare/` directory in the main repository contains a separate analysis of 12 rare/atypical variants not well-represented in MOAlmanac. For each variant, ORCHESTRA summaries were generated and therapy recommendations were compared against Claude Opus 4.5, Claude Sonnet 4, and GPT-4o using the same Prompt B (direct query). See `rare/run_rare_benchmark.py` in the main repository.
