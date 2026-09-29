import json
import os
import glob
import boto3

from botocore.config import Config
bedrock = boto3.client("bedrock-runtime", region_name="us-east-1", config=Config(read_timeout=120))

def call_claude(prompt: str) -> str:
    payload = {
        "messages": [{"role": "user", "content": [{"type": "text", "text": prompt}]}],
        "max_tokens": 4000,
        "anthropic_version": "bedrock-2023-05-31"
    }
    response = bedrock.invoke_model(
        modelId="global.anthropic.claude-opus-4-5-20251101-v1:0",
        contentType="application/json",
        accept="application/json",
        body=json.dumps(payload)
    )
    response_body = json.loads(response["body"].read().decode("utf-8"))
    content = response_body.get("content", [])
    return content[0].get("text", "") if content else ""

def load_annotation_data(variant, job_path=None):
    data = {}
    
    base_path = job_path if job_path else ""
    
    # Load GenomeNexus
    # gn_path = f"{base_path}/genomenexus_output/{variant}_genomenexus.json" if base_path else f"genomenexus_output/{variant}_genomenexus.json"
    # if os.path.exists(gn_path):
    #     with open(gn_path, 'r') as f:
    #         data['genomenexus'] = json.load(f)
    
    # Load ClinVar
    cv_path = f"{base_path}/clinvar_output/{variant}_clinvar.json" if base_path else f"clinvar_output/{variant}_clinvar.json"
    if os.path.exists(cv_path):
        with open(cv_path, 'r') as f:
            data['clinvar'] = json.load(f)
    
    # Load CIViC
    civic_path = f"{base_path}/civic_output/{variant}_civic.json" if base_path else f"civic_output/{variant}_civic.json"
    if os.path.exists(civic_path):
        with open(civic_path, 'r') as f:
            data['civic'] = json.load(f)
    
    # Load OncoKB
    oncokb_path = f"{base_path}/oncokb_output/{variant}_oncokb.json" if base_path else f"oncokb_output/{variant}_oncokb.json"
    if os.path.exists(oncokb_path):
        with open(oncokb_path, 'r') as f:
            data['oncokb'] = json.load(f)
    
    # Load PubMed filtered data
    pubmed_path = f"{base_path}/output-filter_treatment_info/{variant}_extracted_FrompubmedAndPMC_filtered.json" if base_path else f"output-filter_treatment_info/{variant}_extracted_FrompubmedAndPMC_filtered.json"
    if os.path.exists(pubmed_path):
        with open(pubmed_path, 'r') as f:
            data['pubmed'] = json.load(f)
    
    return data

def generate_variant_summary(variant, data, cancer_type=None):
    cancer_context = ""
    if cancer_type:
        cancer_context = f"""

IMPORTANT CONTEXT: This variant was found in a patient with **{cancer_type}**.
- Present ALL evidence from all cancer types for completeness.
- However, your final therapeutic recommendations and clinical actionability assessment MUST be specifically tailored to {cancer_type}.
- Clearly distinguish between evidence from {cancer_type} vs. other cancer types.
"""
    
    prompt = f"""
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
{json.dumps(data, indent=2)}

Generate a structured summary with:
1. **Variant Overview**: Gene, alteration type, and basic characteristics (from provided data only)
2. **Clinical Significance**: Pathogenicity, oncogenicity, and functional impact (as stated in the databases)
3. **Therapeutic Implications**: FDA-approved therapies, clinical trials, and treatment recommendations{f' — specifically for {cancer_type}' if cancer_type else ''} (only what the evidence supports)
4. **Functional Consequences**: What this mutation does biologically (from PubMed functional_mechanistic papers if available)
5. **Evidence from Other Cancer Types**: Relevant findings from other cancers that may inform clinical decisions (clearly label the cancer type)
6. **Evidence Level**: Strength of evidence across databases{f', noting which evidence is specific to {cancer_type} vs other cancer types' if cancer_type else ''}
7. **Key Findings**: Most important actionable insights{f' for a {cancer_type} patient' if cancer_type else ''}

Remember: ONLY state what the data says. Do not hallucinate or infer beyond the evidence.
"""
    
    summary = call_claude(prompt)
    return summary

def generate_all_summaries(job_path=None):
    base_path = job_path if job_path else ""
    summary_dir = f"{base_path}/summary" if base_path else "summary"
    os.makedirs(summary_dir, exist_ok=True)
    
    # Read cancer_type from job CSV
    cancer_type = None
    if base_path:
        csv_path = f"{base_path}/variants.csv"
        if os.path.exists(csv_path):
            import pandas as pd
            _df = pd.read_csv(csv_path)
            if 'cancer_type' in _df.columns and len(_df) > 0 and pd.notna(_df['cancer_type'].iloc[0]):
                cancer_type = str(_df['cancer_type'].iloc[0]).strip()
    
    # Get all variants
    variants = set()
    # for f in glob.glob(f"{base_path}/genomenexus_output/*.json" if base_path else "genomenexus_output/*.json"):
    #     basename = os.path.basename(f).replace("_genomenexus.json", "")
    #     variants.add(basename)
    for f in glob.glob(f"{base_path}/clinvar_output/*.json" if base_path else "clinvar_output/*.json"):
        basename = os.path.basename(f).replace("_clinvar.json", "")
        variants.add(basename)
    for f in glob.glob(f"{base_path}/civic_output/*.json" if base_path else "civic_output/*.json"):
        basename = os.path.basename(f).replace("_civic.json", "")
        variants.add(basename)
    for f in glob.glob(f"{base_path}/oncokb_output/*.json" if base_path else "oncokb_output/*.json"):
        basename = os.path.basename(f).replace("_oncokb.json", "")
        variants.add(basename)
    
    for variant in sorted(variants):
        summary_path = f"{summary_dir}/{variant}_summary.json"
        
        if os.path.exists(summary_path):
            print(f"Skipping {variant} - summary already exists")
            continue
        
        print(f"Generating summary for {variant}...")
        data = load_annotation_data(variant, job_path)
        
        if data:
            summary = generate_variant_summary(variant, data, cancer_type=cancer_type)
            
            summary_data = {
                "variant": variant,
                "summary": summary,
                "sources": list(data.keys())
            }
            
            with open(summary_path, 'w') as f:
                json.dump(summary_data, f, indent=2)
            
            print(f"Summary saved for {variant}")
        else:
            print(f"No data found for {variant}")

if __name__ == "__main__":
    import sys
    job_path = sys.argv[1] if len(sys.argv) > 1 else None
    generate_all_summaries(job_path)
