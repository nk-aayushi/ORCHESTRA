# Literature Filtering Prompt

**Pipeline step**: Step 2 (`script3_filter.py`)  
**Model**: Claude Sonnet 4.5 (`global.anthropic.claude-sonnet-4-5-20250929-v1:0`)  
**Max tokens**: 6000  
**Temperature**: Bedrock default (not set)

This step reads each paper retrieved from PubMed/PMC and decides whether it contains clinically relevant information for the variant. Two prompt variants are used depending on whether the paper has only an abstract or a full PMC text.

---

## Prompt Variant A: Abstract Batch

Used when processing abstract-only papers. Up to 5 abstracts are batched into a single call.

The `{variant}`, `{gene}`, `{len(papers)}`, `{cancer_context}`, and `{papers_text}` fields are filled at runtime.

```
Analyze these {N} papers for variant {variant} (gene: {gene}).
{cancer_context}
For each paper, determine if it contains ANY of the following (in priority order):

1. DIRECT treatment information for {variant} or {gene} (HIGHEST PRIORITY)
   - Targeted therapies, drug responses, treatment outcomes
   - Clinical trial results, efficacy data

2. INDIRECT treatment implications (HIGH PRIORITY)
   - How this variant affects response to treatments for OTHER mutations
   - Resistance mechanisms or sensitivity patterns
   - Prognostic information that guides treatment decisions
   - Co-occurring mutations and their treatment implications
   - Biomarker status affecting therapy selection

3. FUNCTIONAL / MECHANISTIC information about the variant (KEEP — lower priority but valuable)
   - What goes wrong biologically when this mutation occurs
   - Protein function disruption, signaling pathway effects
   - Gain-of-function or loss-of-function characterization
   - Downstream molecular consequences
   - Evidence from other cancer types about this variant's behavior

Mark a paper as relevant if it matches ANY of the above categories.

If relevant, extract:
- Drug/Treatment Used (or "None - functional/mechanistic study" if no treatment info)
- Treatment Summary: include treatment data if present, OR functional consequence description
- relevance_category: one of "direct_treatment", "indirect_treatment", or "functional_mechanistic"

Return JSON array:
[
  {
    "pmid": "...",
    "relevant": true/false,
    "drug_treatment_used": "...",
    "treatment_info": "...",
    "relevance_category": "..."
  }
]

Papers:
{papers_text}
```

### Cancer context injection

When a cancer type is known for the case, the following line is injected as `{cancer_context}`:

```
CANCER TYPE CONTEXT: The patient has {cancer_type}. Prioritize information relevant to {cancer_type}.
```

If no cancer type is available, `{cancer_context}` is an empty string.

### Papers text format

Each paper in the batch is formatted as:

```
--- Paper {i} ---
PMID: {pmid}
Title: {title}
Abstract: {abstract}
```

---

## Prompt Variant B: PMC Full-Text (Single Paper)

Used when a paper has a full PMC text available. One call per paper.

```
Analyze this full paper for variant {variant} (gene: {gene}).
{cancer_context}
Determine if it contains ANY of the following (in priority order):

1. DIRECT treatment information for {variant} or {gene} (HIGHEST PRIORITY)
   - Targeted therapies, drug responses, treatment outcomes
   - Clinical trial results, efficacy data

2. INDIRECT treatment implications (HIGH PRIORITY)
   - How this variant affects response to treatments for OTHER mutations
   - Resistance mechanisms or sensitivity patterns
   - Prognostic information that guides treatment decisions
   - Co-occurring mutations and their treatment implications
   - Biomarker status affecting therapy selection

3. FUNCTIONAL / MECHANISTIC information about the variant (KEEP — lower priority but valuable)
   - What goes wrong biologically when this mutation occurs
   - Protein function disruption, signaling pathway effects
   - Gain-of-function or loss-of-function characterization
   - Downstream molecular consequences
   - Evidence from other cancer types about this variant's behavior

Mark as relevant if it matches ANY of the above categories.

If relevant, extract ONLY the relevant sections with:
- Drug/Treatment Used (or "None - functional/mechanistic study" if no treatment info)
- Treatment Summary: include treatment data if present, OR functional consequence description
- relevance_category: one of "direct_treatment", "indirect_treatment", or "functional_mechanistic"

Return JSON:
{
  "pmcid": "{pmcid}",
  "relevant": true/false,
  "drug_treatment_used": "...",
  "treatment_info": "...",
  "relevance_category": "..."
}

Paper:
Title: {title}

Abstract: {abstract}

Full Text: {sections}
```

### Full-text extraction note

The `{sections}` field contains the PMC article body with the `<methods>` section excluded. Methods are excluded to reduce noise and token usage. The exclusion is applied recursively: any `<sec>` element whose `<title>` contains the word "methods" (case-insensitive) is dropped.

---

## Output Schema

### Abstract batch output (JSON array)

```json
[
  {
    "pmid": "12345678",
    "relevant": true,
    "drug_treatment_used": "Osimertinib",
    "treatment_info": "Osimertinib showed 80% ORR in EGFR L858R NSCLC patients...",
    "relevance_category": "direct_treatment"
  },
  {
    "pmid": "87654321",
    "relevant": false,
    "drug_treatment_used": "",
    "treatment_info": "",
    "relevance_category": ""
  }
]
```

### PMC single output (JSON object)

```json
{
  "pmcid": "PMC1234567",
  "relevant": true,
  "drug_treatment_used": "None - functional/mechanistic study",
  "treatment_info": "EGFR L858R activates downstream RAS/MAPK and PI3K/AKT signaling...",
  "relevance_category": "functional_mechanistic"
}
```

---

## Relevance Category Definitions

| Category | Included if |
|---|---|
| `direct_treatment` | Paper reports drug/therapy outcomes specifically for this variant or gene |
| `indirect_treatment` | Paper reports resistance, sensitivity, or prognostic information that informs treatment selection |
| `functional_mechanistic` | Paper characterizes the biological effect of the variant (no treatment data required) |

Papers not matching any category have `"relevant": false` and are excluded from the filtered output.
