import os
import requests
import json

ONCOKB_API_KEY = "<YOUR_ONCOKB_API_KEY>"

def fetch_oncokb_cnv(gene, cnv_type, api_key=None, reference_genome="GRCh37"):
    """
    Fetch OncoKB annotation for CNV alterations
    
    Args:
        gene (str): Gene symbol (e.g., 'ERBB2')
        cnv_type (str): CNV type ('amplification', 'deletion', 'gain', 'loss')
        api_key (str): OncoKB API key (optional, will use env var if not provided)
        reference_genome (str): Reference genome version
    
    Returns:
        dict: OncoKB response data or error message
    """
    if not api_key:
        api_key = ONCOKB_API_KEY or os.getenv("ONCOKB_API_KEY")
    if not api_key:
        return {"error": "ONCOKB_API_KEY not found"}

    # Map CNV types to OncoKB format
    cnv_mapping = {
        "amplification": "GAIN",
        "gain": "GAIN", 
        "deletion": "LOSS",
        "loss": "LOSS"
    }
    
    oncokb_cnv_type = cnv_mapping.get(cnv_type.lower())
    if not oncokb_cnv_type:
        return {"error": f"Unsupported CNV type: {cnv_type}"}

    url = "https://www.oncokb.org/api/v1/annotate/copyNumberAlterations"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json"
    }

    params = {
        "hugoSymbol": gene,
        "copyNameAlterationType": oncokb_cnv_type,
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

def save_oncokb_cnv_result(gene, cnv_type, data, output_dir="oncokb_output"):
    """
    Save OncoKB CNV result to JSON file
    
    Args:
        gene (str): Gene symbol
        cnv_type (str): CNV type
        data (dict): OncoKB response data
        output_dir (str): Output directory
    """
    os.makedirs(output_dir, exist_ok=True)
    filename = f"{gene}_{cnv_type}_oncokb.json"
    filepath = os.path.join(output_dir, filename)
    
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2)
    
    return filepath