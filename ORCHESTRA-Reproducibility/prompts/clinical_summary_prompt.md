# Clinical Summary Generation Prompt

**Pipeline step**: Step 3 (`generate_summary.py`)  
**Model**: Claude Opus 4.5 (`global.anthropic.claude-opus-4-5-20251101-v1:0`)  
**Max tokens**: 4000  
**Temperature**: Bedrock default (not set)

This prompt instructs the LLM to synthesize all retained database evidence into a structured clinical report. The LLM is explicitly constrained to use only the provided data and not add outside knowledge.

---

## System Role

No system prompt is used. The entire instruction is in the user message.

---

## User Prompt

The `{variant}`, `{cancer_context}`, and `{data}` fields are filled at runtime.

```
You are a clinical genomics summarizer. Your ONLY job is to synthesize the provided database evidence below.

CRITICAL RULES:
- ONLY use information explicitly present in the provided data. Do NOT add any outside knowledge.
- If a claim is not supported by the data below, do NOT include it.
- Cite the source database (ClinVar, CIViC, OncoKB, PubMed) for every statement.
- If data is limited, say so. Do NOT fill gaps with your own knowledge.
- For PubMed papers, note the relevance_category (direct_treatment, indirect_treatment, functional_mechanistic) and the cancer type context if different from the patient's cancer.

Variant: {variant}
{cancer_context}
Data from databases:
{data}

Generate a structured summary with:
1. **Variant Overview**: Gene, alteration type, and basic characteristics (from provided data only)
2. **Clinical Significance**: Pathogenicity, oncogenicity, and functional impact (as stated in the databases)
3. **Therapeutic Implications**: FDA-approved therapies, clinical trials, and treatment recommendations{cancer_type_suffix} (only what the evidence supports)
4. **Functional Consequences**: What this mutation does biologically (from PubMed functional_mechanistic papers if available)
5. **Evidence from Other Cancer Types**: Relevant findings from other cancers that may inform clinical decisions (clearly label the cancer type)
6. **Evidence Level**: Strength of evidence across databases{evidence_level_suffix}
7. **Key Findings**: Most important actionable insights{key_findings_suffix}

Remember: ONLY state what the data says. Do not hallucinate or infer beyond the evidence.
```

### Cancer context injection

When a cancer type is known, the following block is injected as `{cancer_context}`:

```
IMPORTANT CONTEXT: This variant was found in a patient with **{cancer_type}**.
- Present ALL evidence from all cancer types for completeness.
- However, your final therapeutic recommendations and clinical actionability assessment MUST be specifically tailored to {cancer_type}.
- Clearly distinguish between evidence from {cancer_type} vs. other cancer types.
```

When no cancer type is available, `{cancer_context}` is an empty string.

### Cancer-type-aware suffix strings

When a cancer type is known, the following suffixes are appended to the relevant section instructions:

| Placeholder | Value when cancer type known | Value when unknown |
|---|---|---|
| `{cancer_type_suffix}` | ` — specifically for {cancer_type}` | `` (empty) |
| `{evidence_level_suffix}` | `, noting which evidence is specific to {cancer_type} vs other cancer types` | `` (empty) |
| `{key_findings_suffix}` | ` for a {cancer_type} patient` | `` (empty) |

---

## Data Bundle Format

The `{data}` field is a JSON-serialized dictionary containing all available database outputs for the variant. Keys present depend on which databases returned results:

```json
{
  "clinvar": { ... },   // ClinVar output JSON
  "civic":   { ... },   // CIViC output JSON
  "oncokb":  { ... },   // OncoKB output JSON
  "pubmed":  { ... }    // Filtered literature JSON (output of Step 2)
}
```

Only keys for which data files exist are included. If a database returned no results, its key is absent from the bundle.

---

## Output

The LLM returns free-text markdown. The full text is stored verbatim in the `summary` field:

```json
{
  "variant": "EGFR p.L858R",
  "summary": "## 1. Variant Overview\n\nEGFR p.L858R (Leu858Arg) is a missense mutation...",
  "sources": ["clinvar", "civic", "oncokb", "pubmed"]
}
```

The `sources` list reflects which database keys were present in the data bundle.

---

## Grounding Constraint

The prompt contains an explicit grounding constraint: the LLM is instructed to cite the source database for every statement and to explicitly state when data is limited rather than filling gaps with parametric knowledge. This constraint is evaluated by the LLM-as-a-Judge framework (see `../llm_judge/`).
