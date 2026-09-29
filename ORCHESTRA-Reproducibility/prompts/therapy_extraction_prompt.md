# Therapy Extraction Prompt

**Pipeline step**: Comparative study (`run_batch.py`, `comparative_study/run_baseline_gpt4o.py`, `comparative_study/run_claude_batch_benchmark.py`)  
**Model**: Claude Sonnet 4 (`global.anthropic.claude-sonnet-4-6`) for ORCHESTRA extraction; GPT-4o (`gpt-4o`) for baseline  
**Max tokens**: 2000 (ORCHESTRA extraction), 4000 (baseline benchmark)  
**Temperature**: 0

This prompt is used in two contexts:

1. **ORCHESTRA therapy extraction**: applied to the generated clinical summary to produce a structured therapy list for comparison against MOAlmanac ground truth
2. **Baseline benchmark**: applied directly to the variant (gene + protein change + cancer type) without any retrieved evidence, to test what GPT-4o and Claude models know from parametric knowledge alone

---

## Prompt A: ORCHESTRA Therapy Extraction

Applied to the generated clinical summary. The `{gene}`, `{protein_change}`, `{cancer_type}`, and `{summary_text}` fields are filled at runtime.

```
You are a clinical genomics expert. Based on the following clinical summary for variant {gene} {protein_change} in the context of {cancer_type}, provide ONLY a comma-separated list of therapies.

Tiering rules — assign exactly one level to each therapy:
- Level 1: FDA-approved specifically for this variant AND this cancer type. No label suffix needed — list the drug name only.
- Level 2: Strong clinical evidence but NOT FDA-approved for this exact variant+cancer combination. This includes:
  * FDA-approved for this variant in a DIFFERENT cancer type (i.e., tumor-agnostic or other-indication approval)
  * Phase II or Phase III trial data showing meaningful clinical benefit
  * NCCN Category 1 or 2A recommendation for this variant in this cancer type
  Append "(Level 2)" after the drug name.
- Level 3: Investigational or emerging evidence only. This includes:
  * Phase I trials or early-phase basket trials
  * Retrospective case series (≥3 patients)
  * Expert consensus or NCCN Category 2B/3 recommendation
  Append "(Level 3)" after the drug name.
- Level 4: Preclinical or anecdotal evidence only. This includes:
  * In vitro or in vivo (animal) studies only
  * Single case reports (1–2 patients)
  * Mechanistic inference without clinical data
  Append "(Level 4)" after the drug name.

Additional rules:
- Do NOT include any therapy that has no evidence of benefit for this specific variant
- If a combination therapy is used, list it as "Drug1 + Drug2" with the appropriate level
- When the same drug qualifies under multiple tiers, assign the highest (lowest-numbered) tier supported by the evidence
- Return ONLY the comma-separated list, nothing else

Clinical Summary:
{summary_text}

Therapy list:
```

**Output format**: A single comma-separated line, e.g.:
```
Osimertinib, Erlotinib (Level 2), Afatinib (Level 2), Gefitinib (Level 2)
```

---

## Prompt B: Baseline Benchmark (GPT-4o / Claude)

Applied directly to the variant without any retrieved evidence. This is the same prompt used for both the GPT-4o baseline and the Claude batch benchmark. The `{gene}`, `{protein_change}`, and `{cancer_type}` fields are filled at runtime.

```
For the variant {gene} {protein_change} in {cancer_type}, what are the recommended targeted therapies or treatments? For each therapy, include the level of evidence in brackets (e.g. Level 1, Level 2, Level 3, Level 4) based on FDA approval, clinical guidelines, and clinical evidence strength. First provide a detailed explanation, then on the last line write 'THERAPIES: ' followed by a comma-separated list of therapy names each with their level in brackets, e.g. 'DrugA (Level 1), DrugB (Level 3)'.
```

**Output format**: Free-text explanation followed by a structured last line:
```
THERAPIES: Osimertinib (Level 1), Erlotinib (Level 2), Afatinib (Level 2)
```

The pipeline extracts only the last line starting with `THERAPIES:` (case-insensitive match).

---

## Tiering Rules

Both prompts use the same four-tier evidence classification:

| Tier | Label in output | Definition |
|---|---|---|
| 1 | No label (drug name only) | FDA-approved specifically for this variant AND this cancer type |
| 2 | `(Level 2)` | FDA-approved for this variant in a different cancer type, OR Phase II/III trial data, OR NCCN Category 1/2A recommendation |
| 3 | `(Level 3)` | Phase I / early-phase basket trials, retrospective case series (≥3 patients), or NCCN Category 2B/3 |
| 4 | `(Level 4)` | Preclinical (in vitro/in vivo) data only, or single case reports (1–2 patients) |

When the same drug qualifies under multiple tiers, assign the highest (lowest-numbered) tier supported by the evidence.

---

## Therapy Classification Against MOAlmanac Ground Truth

After therapy lists are generated, they are classified against the MOAlmanac ground truth using `comparative_study/classify_therapies.py`.

Each therapy in the ground truth is categorized as:

| Category | Definition |
|---|---|
| `All Present as Tier 1` | All ground-truth therapies appear in ORCHESTRA output without a level label (i.e., classified as FDA-approved) |
| `All Present as Different Tier` | All ground-truth therapies appear but with a level label (Level 2/3/4) |
| `All Absent` | No ground-truth therapies appear in ORCHESTRA output |
| `Partially Present` | Some ground-truth therapies present, some absent |
| `No Therapies Listed` | ORCHESTRA output is empty |

Matching is case-insensitive on individual drug name tokens.

---

## Models Used in Comparative Study

| System | Model | Prompt Used |
|---|---|---|
| ORCHESTRA | Claude Sonnet 4 (`global.anthropic.claude-sonnet-4-6`) | Prompt A (applied to generated summary) |
| GPT-4o baseline | GPT-4o (`gpt-4o`) via OpenAI API | Prompt B (direct variant query) |
| Claude Opus 4.5 baseline | `global.anthropic.claude-opus-4-5-20251101-v1:0` | Prompt B |
| Claude Sonnet 4 baseline | `global.anthropic.claude-sonnet-4-6` | Prompt B |
