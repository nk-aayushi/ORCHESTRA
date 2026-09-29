import os
import requests
import json

ONCOKB_API_KEY = "<YOUR_ONCOKB_API_KEY>"

def fetch_oncokb_fusion(gene1, gene2, api_key=None, reference_genome="GRCh37"):
    """
    Fetch OncoKB annotation for gene fusions
    
    Args:
        gene1 (str): First gene symbol (5' partner)
        gene2 (str): Second gene symbol (3' partner)
        api_key (str): OncoKB API key (optional, will use env var if not provided)
        reference_genome (str): Reference genome version
    
    Returns:
        dict: OncoKB response data or error message
    """
    if not api_key:
        api_key = ONCOKB_API_KEY or os.getenv("ONCOKB_API_KEY")
    if not api_key:
        return {"error": "ONCOKB_API_KEY not found"}

    url = "https://www.oncokb.org/api/v1/annotate/structuralVariants"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json"
    }

    params = {
        "hugoSymbolA": gene1,
        "hugoSymbolB": gene2,
        "structuralVariantType": "FUSION",
        "referenceGenome": reference_genome
    }

    try:
        r = requests.get(url, headers=headers, params=params)
        if r.status_code == 200:
            return r.json()
        else:
            return {"error": r.status_code, "message": r.text}
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}

def save_oncokb_fusion_result(gene1, gene2, fusion_type, data, output_dir="oncokb_output"):
    """
    Save OncoKB fusion result to JSON file
    
    Args:
        gene1 (str): First gene symbol
        gene2 (str): Second gene symbol  
        fusion_type (str): Fusion type/name
        data (dict): OncoKB response data
        output_dir (str): Output directory
    """
    os.makedirs(output_dir, exist_ok=True)
    filename = f"{gene1}_{gene2}_{fusion_type}_oncokb.json"
    filepath = os.path.join(output_dir, filename)
    
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2)
    
    return filepath