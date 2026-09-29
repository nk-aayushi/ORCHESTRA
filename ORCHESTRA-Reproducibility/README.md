# ORCHESTRA: Reproducibility Package

**Oncology Research Characterization and Harmonization for Evidence-Supported Treatment Recommendations and Annotation**

This repository accompanies the manuscript submitted to *JCO Clinical Cancer Informatics* and provides all code, prompts, and configuration details needed to reproduce the system described in the paper.

---

## Repository Structure

```
ORCHESTRA-Reproducibility/
├── pipeline/                   # Core annotation workflow (Section 2.1–2.4)
│   ├── helper_scripts/         # Database query modules (ClinVar, CIViC, OncoKB, PubMed)
│   ├── main.py                 # Step 1: Database retrieval orchestrator
│   ├── script3_filter.py       # Step 2: LLM-based literature filtering
│   ├── generate_summary.py     # Step 3: Clinical summary generation
│   └── variant_normalization.py # Variant format normalization utilities
│
├── prompts/                    # All LLM prompts with exact settings (Section 2.3–2.4)
│   ├── README.md               # Prompt documentation index
│   ├── literature_filtering_prompt.md
│   ├── clinical_summary_prompt.md
│   └── therapy_extraction_prompt.md
│
├── comparative_study/          # Comparative evaluation vs. MOAlmanac + LLMs (Section 2.6)
│   ├── README.md
│   ├── run_baseline_gpt4o.py
│   ├── run_claude_batch_benchmark.py
│   └── classify_therapies.py
│
├── llm_judge_criteria/         # 12-criterion LLM judge: model comparison across 98 cases (Section 2.5)
│   ├── README.md               # Full rubric, prompts, verdict definitions
│   ├── main.py
│   ├── judge.py
│   ├── loader.py
│   ├── prompts.py
│   ├── config.py
│   └── requirements.txt
│
└── llm_judge/                  # 4-score LLM judge: human-vs-LLM agreement analysis (Section 2.5)
    ├── README.md
    ├── judge.py
    ├── evaluator.py
    ├── loader.py
    ├── utils.py
    ├── config.py
    ├── prompts.py
    └── requirements.txt
```

---

## Two Evaluation Frameworks

The paper uses two complementary LLM-as-a-Judge frameworks:

| Directory | Purpose | Criteria | Output |
|---|---|---|---|
| `llm_judge_criteria/` | Model comparison across all 98 cases — reports PASS/minor/major rates per clinical dimension | 12 criteria (variant identification, biological interpretation, clinical significance, therapeutic recommendations, evidence integration, clinical reasoning, resistance interpretation, clinical trials, evidence levels, safety, hallucinations, report organization) + overall quality (Excellent/Good/Acceptable/Poor/Unsafe) | Per-case JSON + master CSV |
| `llm_judge/` | Human-vs-LLM agreement analysis — compares automated scores to human expert ratings | 4 numeric scores (hallucination, completeness, usefulness, grounding), each 1–5 | Per-case JSON + master CSV |

---

## System Overview

ORCHESTRA is a three-step pipeline:

1. **Database Retrieval** (`pipeline/main.py`): For each variant, queries ClinVar, CIViC, OncoKB, and PubMed/PMC in parallel.
2. **Literature Filtering** (`pipeline/script3_filter.py`): An LLM (Claude Sonnet) reads each retrieved abstract/full-text and classifies it as `direct_treatment`, `indirect_treatment`, or `functional_mechanistic`. Irrelevant papers are discarded.
3. **Clinical Summary Generation** (`pipeline/generate_summary.py`): An LLM (Claude Opus) synthesizes all retained evidence into a structured clinical report.

---

## Database Versions and Access Dates

| Database | Version / Access Date | API Endpoint |
|---|---|---|
| ClinVar | Accessed via NCBI E-utilities; no fixed release — queries reflect live database state at time of run. Study cohort queried **November–December 2024**. | `https://eutils.ncbi.nlm.nih.gov/entrez/eutils/` |
| CIViC | Accessed via GraphQL API; no versioned releases — queries reflect live database state. Study cohort queried **November–December 2024**. | `https://civicdb.org/api/graphql` |
| OncoKB | Accessed via REST API. Data version returned per-query in the `dataVersion` field of each JSON response. Study cohort queried **November–December 2024**. | `https://www.oncokb.org/api/v1/` |
| PubMed / PMC | Accessed via NCBI E-utilities. No fixed snapshot — reflects PubMed index at time of query. Study cohort queried **November–December 2024**. | `https://eutils.ncbi.nlm.nih.gov/entrez/eutils/` |
| Mutalyzer | Used for HGVS normalization (DNA ↔ protein conversion). Accessed via REST API. | `https://mutalyzer.nl/api/` |
| MANE Select | MANE.GRCh38.v1.5 (used as reference transcript source for Mutalyzer queries). | Bundled in `pipeline/helper_scripts/` |

> **Note on reproducibility**: Because ClinVar, CIViC, and PubMed are live databases, re-running the pipeline on the same variants today may return slightly different results than those in the paper. The raw database outputs for all 98 study cases are available in `study_jobs/` (not included in this repository due to size; available upon request).

---

## LLM Models and Settings

| Step | Model | Model ID (AWS Bedrock) | Temperature | Max Tokens |
|---|---|---|---|---|
| Literature Filtering (Step 2) | Claude Sonnet 4.5 | `global.anthropic.claude-sonnet-4-5-20250929-v1:0` | default | 6000 |
| Clinical Summary (Step 3) | Claude Opus 4.5 | `global.anthropic.claude-opus-4-5-20251101-v1:0` | default | 4000 |
| Therapy Extraction (Comparative) | Claude Sonnet 4 | `global.anthropic.claude-sonnet-4-6` | 0 | 2000 |
| LLM-as-a-Judge | Claude Sonnet 4 | `global.anthropic.claude-sonnet-4-6` | 0.0 | 4096 |

All models accessed via **AWS Bedrock** (`us-east-1` region) using the `bedrock-runtime` API.

---

## PubMed Literature Search Strategy

Full details are documented in `prompts/README.md`. In brief, for each variant the pipeline runs four query tiers against PubMed:

1. **Variant-specific clinical articles** — `{gene} AND {variant} AND cancer AND (treatment OR therapy ...) AND (Clinical Trial OR Case Reports ...) AND [2010–present] AND English AND Humans`
2. **Variant-specific reviews** — same terms, `Review` publication type, retmax=50
3. **Gene-level clinical articles** — `{gene} AND (mutation OR variant) AND cancer AND ...`, retmax=50
4. **Gene-level reviews** — same, retmax=30

Papers are then scored and the top 50 are passed to the LLM filtering step. Full scoring weights are documented in `prompts/README.md`.

---

## Variant Normalization

Variants are normalized before querying each database. Full details in `pipeline/variant_normalization.py` and `pipeline/helper_scripts/`. In brief:

- Protein changes are converted between 1-letter, 3-letter HGVS, and shorthand formats using `allVar.py`
- Coding changes are normalized via the Mutalyzer API using MANE Select v1.5 reference transcripts
- When only a protein change is provided, the coding change is back-translated via Mutalyzer; when only a coding change is provided, the protein change is derived via Mutalyzer
- CNV types are normalized to `amplification` / `deletion`
- Fusion queries use the `GENE1::GENE2` HGVS fusion notation

---

## Tiering Rules

Therapy tiers are assigned by the LLM during the therapy extraction step (see `prompts/therapy_extraction_prompt.md`):

- **Tier 1 (no label)**: FDA-approved for this specific variant and cancer type indication
- **Level 2**: Strong clinical evidence (Phase II/III trials, NCCN guidelines) but not FDA-approved for this exact indication
- **Level 3**: Investigational (early-phase trials, basket trials, case series)
- **Level 4**: Preclinical or case-report-only evidence

The LLM is instructed to assign tiers based solely on the evidence present in the generated clinical summary, which itself is grounded only in the retrieved database evidence.

---

## Relevance Scoring Weights (PubMed Retrieval)

| Signal | Score |
|---|---|
| Exact variant match in title/abstract | +3 |
| Gene name mentioned | +1 |
| Clinical keywords present (treatment, therapy, response, resistance, drug, efficacy, outcome) | +1 |
| Patient cancer type mentioned | +3 |
| Review article penalty | −1 |

Papers are ranked by this score; the top 50 are passed to the LLM filtering step.

---

## Requirements

See `pipeline/requirements.txt` and `llm_judge/requirements.txt`.

Key dependencies:
- Python ≥ 3.10
- `boto3` (AWS Bedrock access)
- `requests` (database API calls)
- `biopython` (amino acid code conversion)
- `pandas`
- `streamlit` (UI only, not required for pipeline)

AWS credentials with Bedrock access to `us-east-1` are required to run the LLM steps.

---

## Citation

> [Authors]. ORCHESTRA: An AI-Assisted Variant Annotation System for Molecular Tumor Boards. *JCO Clinical Cancer Informatics*, 2025.
