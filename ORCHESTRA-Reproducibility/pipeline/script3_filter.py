import json
import os
import glob
import boto3
import time
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

# Accept full job directory path (e.g. study_jobs/Lung_Cancer/1)
JOB_PATH = sys.argv[1] if len(sys.argv) > 1 else None

if JOB_PATH:
    input_dir = f"{JOB_PATH}/pubmed_output"
    output_dir = f"{JOB_PATH}/output-filter_treatment_info"
    # Read cancer_type from job CSV
    _csv_path = f"{JOB_PATH}/variants.csv"
    if os.path.exists(_csv_path):
        import pandas as pd
        _df = pd.read_csv(_csv_path)
        cancer_type = str(_df['cancer_type'].iloc[0]).strip() if 'cancer_type' in _df.columns and pd.notna(_df['cancer_type'].iloc[0]) else None
    else:
        cancer_type = None
else:
    input_dir = "pubmed_output"
    output_dir = "output-filter_treatment_info"
    cancer_type = None

os.makedirs(output_dir, exist_ok=True)

class RateLimiter:
    def __init__(self, max_calls=9999, time_window=60):
        self.max_calls = max_calls
        self.time_window = time_window
        self.calls = []
        import threading
        self._lock = threading.Lock()
    
    def wait_if_needed(self):
        with self._lock:
            now = time.time()
            self.calls = [call_time for call_time in self.calls if now - call_time < self.time_window]
            
            if len(self.calls) >= self.max_calls:
                sleep_time = self.time_window - (now - self.calls[0]) + 1
                print(f"Rate limit reached, sleeping for {sleep_time:.1f} seconds...")
                time.sleep(sleep_time)
                self.calls = []
            
            self.calls.append(time.time())

rate_limiter = RateLimiter()

bedrock_client = boto3.client("bedrock-runtime", region_name="us-east-1")

class ClaudeBedrockLLM:
    @staticmethod
    def call(prompt: str, max_tokens: int = 4000) -> str:
        payload = {
            "messages": [{"role": "user", "content": [{"type": "text", "text": prompt}]}],
            "max_tokens": max_tokens,
            "anthropic_version": "bedrock-2023-05-31"
        }
        response = bedrock_client.invoke_model(
            modelId="global.anthropic.claude-sonnet-4-5-20250929-v1:0",
            contentType="application/json",
            accept="application/json",
            body=json.dumps(payload)
        )
        response_body = response["body"].read().decode("utf-8")
        response_json = json.loads(response_body)
        content = response_json.get("content", [])
        if content and len(content) > 0:
            return content[0].get("text", "")
        return ""

def extract_json_from_response(text):
    import html
    
    # Remove markdown code blocks
    text = text.replace('```json', '').replace('```', '').strip()
    
    # Decode HTML entities
    text = html.unescape(text)
    
    # Find JSON array or object
    start = text.find('[')
    if start == -1:
        start = text.find('{')
    end = text.rfind(']')
    if end == -1:
        end = text.rfind('}')
    
    if start == -1 or end == -1:
        return None
    
    try:
        return json.loads(text[start:end + 1])
    except Exception as e:
        print(f"JSON parse error: {e}")
        return None

def process_three_abstracts(variant, papers):
    # Extract gene name from variant (e.g., "ESR1 p.Tyr537Ser" -> "ESR1")
    gene = variant.split()[0] if ' ' in variant else variant
    
    cancer_context = f"\nCANCER TYPE CONTEXT: The patient has {cancer_type}. Prioritize information relevant to {cancer_type}.\n" if cancer_type else ""
    
    papers_text = ""
    for i, paper in enumerate(papers, 1):
        papers_text += f"\n--- Paper {i} ---\n"
        papers_text += f"PMID: {paper.get('pmid', '')}\n"
        papers_text += f"Title: {paper.get('title', '')}\n"
        papers_text += f"Abstract: {paper.get('abstract', '')}\n"
    
    prompt = f"""
Analyze these {len(papers)} papers for variant {variant} (gene: {gene}).
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
  {{
    "pmid": "...",
    "relevant": true/false,
    "drug_treatment_used": "...",
    "treatment_info": "...",
    "relevance_category": "..."
  }}
]

Papers:
{papers_text}
"""
    
    try:
        rate_limiter.wait_if_needed()
        response = ClaudeBedrockLLM.call(prompt, max_tokens=6000)
        print(f"\n=== ABSTRACTS BATCH RESPONSE ===")
        print(f"Variant: {variant}")
        print(f"Raw response: {response}")
        print("=" * 50)
        
        result = extract_json_from_response(response)
        if result and isinstance(result, list):
            print(f"Parsed result: {json.dumps(result, indent=2)}")
            return result
        print(f"Failed to parse JSON from response")
        return []
    except Exception as e:
        print(f"Error processing abstracts: {e}")
        return []

def process_single_pmc(variant, paper):
    # Extract gene name from variant
    gene = variant.split()[0] if ' ' in variant else variant
    
    cancer_context = f"\nCANCER TYPE CONTEXT: The patient has {cancer_type}. Prioritize information relevant to {cancer_type}.\n" if cancer_type else ""
    
    content = f"Title: {paper.get('title', '')}\n\nAbstract: {paper.get('abstract', '')}\n\nFull Text: {paper.get('sections', '')}"
    
    prompt = f"""
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
{{
  "pmcid": "{paper.get('pmcid', '')}",
  "relevant": true/false,
  "drug_treatment_used": "...",
  "treatment_info": "...",
  "relevance_category": "..."
}}

Paper:
{content}
"""
    
    try:
        rate_limiter.wait_if_needed()
        response = ClaudeBedrockLLM.call(prompt, max_tokens=6000)
        print(f"\n=== PMC PAPER RESPONSE ===")
        print(f"Variant: {variant}")
        print(f"PMID: {paper.get('pmid', '')}")
        print(f"Raw response: {response}")
        print("=" * 50)
        
        result = extract_json_from_response(response)
        if result:
            print(f"Parsed result: {json.dumps(result, indent=2)}")
            return result
        print(f"Failed to parse JSON from response")
        return {"pmid": paper.get('pmid', ''), "relevant": False}
    except Exception as e:
        print(f"Error processing PMC paper {paper.get('pmid', '')}: {e}")
        return {"pmid": paper.get('pmid', ''), "relevant": False}



def filter_json_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    variant = data.get('variant', '')
    
    filename = os.path.basename(filepath).replace('.json', '_filtered.json')
    output_path = os.path.join(output_dir, filename)
    
    if os.path.exists(output_path):
        print(f"Skipping {variant} - filtered file already exists")
        return
    
    print(f"Processing {variant}...")
    
    papers = data.get('literature_summaries', [])
    
    # Sort papers by relevance score (if available) and take top 25
    papers_with_scores = [p for p in papers if 'relevance_score' in p]
    papers_without_scores = [p for p in papers if 'relevance_score' not in p]
    
    if papers_with_scores:
        papers_with_scores.sort(key=lambda x: x.get('relevance_score', 0), reverse=True)
        papers = papers_with_scores[:50] + papers_without_scores
    
    print(f"Processing top {len(papers)} papers (sorted by relevance)")
    
    filtered_summaries = []
    
    # Separate abstracts and PMC papers
    # PMC papers with no sections (inactive PMC) go into abstract batch
    abstracts = [p for p in papers if not p.get('sections') or p.get('sections', '').strip() == '']
    pmc_papers = [p for p in papers if p.get('sections') and p.get('sections', '').strip() != '']
    
    # Process all LLM calls concurrently
    abstract_batches = [abstracts[i:i+5] for i in range(0, len(abstracts), 5)]
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        # Submit abstract batches
        abstract_futures = {}
        for batch in abstract_batches:
            future = executor.submit(process_three_abstracts, variant, batch)
            abstract_futures[future] = batch
        
        # Submit PMC papers
        pmc_futures = {}
        for paper in pmc_papers:
            future = executor.submit(process_single_pmc, variant, paper)
            pmc_futures[future] = paper
        
        # Collect abstract results
        for future in as_completed(abstract_futures):
            batch = abstract_futures[future]
            try:
                results = future.result()
                for j, result in enumerate(results):
                    if result.get('relevant'):
                        original_paper = batch[j] if j < len(batch) else {}
                        entry = {
                            'title': original_paper.get('title', ''),
                            'source': original_paper.get('source', ''),
                            'drug_treatment_used': result.get('drug_treatment_used', 'No drugs specified'),
                            'treatment_info': result.get('treatment_info', ''),
                            'relevance_category': result.get('relevance_category', 'direct_treatment')
                        }
                        # Use pmid if available (preferred), fall back to pmcid
                        if original_paper.get('pmid'):
                            entry['pmid'] = original_paper['pmid']
                        if original_paper.get('pmcid'):
                            entry['pmcid'] = original_paper['pmcid']
                        filtered_summaries.append(entry)
            except Exception as e:
                print(f"Error in abstract batch: {e}")
        
        # Collect PMC results
        for future in as_completed(pmc_futures):
            paper = pmc_futures[future]
            try:
                result = future.result()
                if result.get('relevant'):
                    entry = {
                        'title': paper.get('title', ''),
                        'source': paper.get('source', ''),
                        'drug_treatment_used': result.get('drug_treatment_used', 'No drugs specified'),
                        'treatment_info': result.get('treatment_info', ''),
                        'relevance_category': result.get('relevance_category', 'direct_treatment')
                    }
                    if paper.get('pmcid'):
                        entry['pmcid'] = paper['pmcid']
                    if paper.get('pmid'):
                        entry['pmid'] = paper['pmid']
                    filtered_summaries.append(entry)
            except Exception as e:
                print(f"Error in PMC paper: {e}")
    
    filtered_data = data.copy()
    filtered_data['literature_summaries'] = filtered_summaries
    filtered_data['papers_processed'] = len(filtered_summaries)
    filtered_data['filtering_note'] = f"Filtered for treatment information specific to {variant}"
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(filtered_data, f, indent=2, ensure_ascii=False)
    
    print(f"Saved filtered file: {output_path}")
    print(f"Kept {len(filtered_summaries)} out of {len(papers)} papers\n")

def main():
    json_files = glob.glob(os.path.join(input_dir, "*_extracted_FrompubmedAndPMC.json"))
    
    if not json_files:
        print(f"No JSON files found in {input_dir} directory")
        return
    
    print(f"Found {len(json_files)} JSON files to process")
    
    for filepath in json_files:
        try:
            filter_json_file(filepath)
        except Exception as e:
            print(f"Error processing {filepath}: {e}")

if __name__ == "__main__":
    main()
