# Pipeline: Core Annotation Workflow

This directory contains the three-step annotation pipeline that processes a genomic variant and produces a structured clinical summary.

---

## Pipeline Steps

```
variants.csv
     │
     ▼
[Step 1] main.py
     │   Queries ClinVar, CIViC, OncoKB, PubMed/PMC
     │   Outputs: clinvar_output/, civic_output/, oncokb_output/, pubmed_output/
     ▼
[Step 2] script3_filter.py
     │   LLM reads each retrieved paper and classifies relevance
     │   Outputs: output-filter_treatment_info/
     ▼
[Step 3] generate_summary.py
         LLM synthesizes all retained evidence into a clinical report
         Outputs: summary/
```

---

## Step 1: Database Retrieval (`main.py`)

**Input**: `variants.csv` (one row per variant) + job directory path as CLI argument

**Variant CSV columns**:

| Column | Description |
|---|---|
| `gene` | HGNC gene symbol (e.g., `EGFR`) |
| `coding_change` | HGVS coding change (e.g., `c.2573T>G`); may be empty |
| `protein_change` | Protein change (e.g., `p.L858R`); may be empty |
| `variant_type` | One of: `Missense_Mutation`, `Nonsense_Mutation`, `Frame_Shift_Del`, `Frame_Shift_Ins`, `In_Frame_Del`, `In_Frame_Ins`, `Splice_Site`, `CNV`, `Fusion` |
| `cnv_type` | `Amplification` or `Deletion` (CNV only) |
| `copy_number` | Integer copy number (CNV only, optional) |
| `gene_5prime` | 5' fusion partner gene (Fusion only) |
| `gene_3prime` | 3' fusion partner gene (Fusion only) |
| `fusion_name` | Fusion name string (Fusion only) |
| `cancer_type` | Free-text cancer type (e.g., `Non-Small Cell Lung Cancer`) |
| `variant_classification` | Pathogenicity call; rows with `synonymous` or `Benign` are skipped |

**Databases queried per variant type**:

| Variant Type | ClinVar | CIViC | OncoKB | PubMed/PMC |
|---|---|---|---|---|
| SNV / Indel | ✓ | ✓ | ✓ | ✓ |
| CNV | ✓ | ✓ | ✓ | ✓ |
| Fusion | — | ✓ | ✓ | ✓ |

**Output files** (per variant, written to `{job_dir}/`):

| Directory | File pattern | Contents |
|---|---|---|
| `clinvar_output/` | `{gene}_{change}_clinvar.json` | ClinVar variant records, classifications, allele frequencies, cited PMIDs |
| `civic_output/` | `{gene}_{change}_civic.json` | CIViC evidence items, therapy names, evidence levels, source PMIDs |
| `oncokb_output/` | `{gene}_{change}_oncokb.json` | OncoKB annotation: oncogenicity, mutation effect, treatments with levels, PMIDs |
| `pubmed_output/` | `{gene}_{change}_extracted_FrompubmedAndPMC.json` | Top-scored papers with title, abstract, full text (PMC), relevance score |

**Idempotency**: All output files are checked before running; existing files are skipped.

**Usage**:
```bash
# Copy variants.csv to ngs_report_summary.csv (pipeline reads from this path)
cp {job_dir}/variants.csv ngs_report_summary.csv
python main.py {job_dir}
```

---

## Step 2: Literature Filtering (`script3_filter.py`)

**Input**: `{job_dir}/pubmed_output/*_extracted_FrompubmedAndPMC.json`

**What it does**: For each paper retrieved in Step 1, calls an LLM to determine whether the paper contains clinically relevant information. Papers are classified into three categories:

| Category | Description |
|---|---|
| `direct_treatment` | Targeted therapies, drug responses, clinical trial results for this variant |
| `indirect_treatment` | Resistance mechanisms, prognostic information, co-mutation treatment implications |
| `functional_mechanistic` | Biological characterization of the variant (pathway effects, gain/loss of function) |

Papers not matching any category are discarded.

**Batching strategy**:
- Abstract-only papers (no PMC full text): batched in groups of 5 per LLM call
- PMC full-text papers: one LLM call per paper

**LLM**: Claude Sonnet 4.5 (`global.anthropic.claude-sonnet-4-5-20250929-v1:0`) via AWS Bedrock  
**Max tokens**: 6000  
**Concurrency**: ThreadPoolExecutor, max_workers=5

**Output**: `{job_dir}/output-filter_treatment_info/{variant}_extracted_FrompubmedAndPMC_filtered.json`

The filtered JSON retains the same structure as the input but with `literature_summaries` reduced to only relevant papers, each annotated with `drug_treatment_used`, `treatment_info`, and `relevance_category`.

**Usage**:
```bash
python script3_filter.py {job_dir}
```

---

## Step 3: Clinical Summary Generation (`generate_summary.py`)

**Input**: All files in `{job_dir}/clinvar_output/`, `civic_output/`, `oncokb_output/`, `output-filter_treatment_info/`

**What it does**: Loads all database outputs for a variant, constructs a single JSON evidence bundle, and calls an LLM to produce a structured clinical summary.

**LLM**: Claude Opus 4.5 (`global.anthropic.claude-opus-4-5-20251101-v1:0`) via AWS Bedrock  
**Max tokens**: 4000

**Output structure** (`{job_dir}/summary/{variant}_summary.json`):
```json
{
  "variant": "EGFR p.L858R",
  "summary": "## 1. Variant Overview\n...",
  "sources": ["clinvar", "civic", "oncokb", "pubmed"]
}
```

**Summary sections** (as instructed in the prompt):
1. Variant Overview
2. Clinical Significance
3. Therapeutic Implications
4. Functional Consequences
5. Evidence from Other Cancer Types
6. Evidence Level
7. Key Findings

See `../prompts/clinical_summary_prompt.md` for the exact prompt.

**Usage**:
```bash
python generate_summary.py {job_dir}
```

---

## Variant Normalization (`helper_scripts/`)

Before querying each database, variants are normalized to all equivalent representations. This is critical because databases use inconsistent notation.

### Protein change normalization (`allVar.py`)

Given any protein change string, `convert_any_variant()` returns a dictionary of equivalent formats:

| Key | Example (input: `p.L858R`) |
|---|---|
| `HGVS_3letter` | `p.Leu858Arg` |
| `1L` | `L858R` |
| `arrow` | `L858R>` |
| `p_style` | `p.L858R` |

Supported variant types: substitution, deletion, insertion, delins, frameshift.

All formats are tried when querying ClinVar and CIViC to maximize recall.

### Coding change normalization (`allCChange.py`)

Generates equivalent coding change representations (e.g., `c.2573T>G` → multiple HGVS forms).

### DNA ↔ Protein conversion (`mutalyzer.py`)

When only one of `coding_change` or `protein_change` is provided:
- Missing protein change → derived via Mutalyzer normalize API
- Missing coding change → back-translated via Mutalyzer

Reference transcripts: **MANE Select v1.5** (`MANE.GRCh38.v1.5.summary.txt`), GRCh38.

### CNV normalization

Input values are normalized:
- `gain`, `amplification`, `duplication` → `amplification`
- `loss`, `deletion` → `deletion`

### Fusion notation

Fusions are queried using `GENE1::GENE2` notation (HGVS standard) in PubMed and CIViC.

---

## PubMed Search Strategy (Full Detail)

Implemented in `helper_scripts/pubmedSearchBase.py` (SNV/CNV) and `helper_scripts/pubmedSearchFusion.py` (Fusions).

### Query tiers (SNV/CNV)

**Tier 1 — Variant-specific clinical articles** (retmax=100 per variant format):
```
{gene} AND {variant_format} AND cancer
AND (treatment OR therapy OR response OR resistance OR drug OR clinical OR outcome OR efficacy OR prognosis)
AND ("Clinical Trial"[PT] OR "Clinical Study"[PT] OR "Observational Study"[PT] OR "Case Reports"[PT])
AND ("2010"[DP] : "3000"[DP]) AND English[LA] AND Humans[MeSH]
```

**Tier 2 — Variant-specific reviews** (retmax=50):
```
{gene} AND {variant_format} AND cancer AND (clinical keywords) AND "Review"[PT] AND (filters)
```

**Tier 3 — Gene-level clinical articles** (retmax=50):
```
{gene} AND (mutation OR variant) AND cancer AND (clinical keywords) AND (clinical article types) AND (filters)
```

**Tier 4 — Gene-level reviews** (retmax=30):
```
{gene} AND (mutation OR variant) AND cancer AND (clinical keywords) AND "Review"[PT] AND (filters)
```

For CNVs, Tier 3/4 use `(amplification OR deletion OR copy number OR gain OR loss)` instead of `(mutation OR variant)`.

Multiple variant format strings (from `allVar.py`) are each submitted as separate Tier 1/2 queries.

### Deduplication

PMIDs appearing in multiple tiers are deduplicated; variant-specific types (`clinical`, `review`) take priority over `gene_level` types.

### Relevance scoring

After fetching metadata for all retrieved PMIDs, each paper is scored:

| Signal | Points |
|---|---|
| Exact variant string match in title+abstract | +3 |
| Gene name in title+abstract | +1 |
| Clinical keyword in title+abstract | +1 |
| Patient cancer type in title+abstract | +3 |
| Review article | −1 |

Top 50 papers by score are passed to Step 2.

### PMC full-text retrieval

For each of the top 50 papers, the pipeline checks for a free PMC full-text version via the NCBI elink API. Papers with PMC full text are fetched via the PMC efetch API (XML). The `<methods>` section is excluded from extracted text to reduce noise.

### API key

A registered NCBI API key is used (allows 10 requests/second vs. 3 without). The key in the source code should be replaced with your own from https://www.ncbi.nlm.nih.gov/account/.

---

## Requirements

```
boto3
requests
biopython
pandas
```

Install: `pip install boto3 requests biopython pandas`

AWS credentials must be configured with Bedrock access to `us-east-1`.
