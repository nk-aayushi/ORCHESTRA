import requests
import json
import os
from HelperScripts.allVar import convert_any_variant

ONCOKB_API_KEY = "<YOUR_ONCOKB_API_KEY>"

def fetch_oncokb(gene, alteration, api_key=None):
    """
    Fetch OncoKB annotation for a given gene and alteration
    Tries all variant formats from convert_any_variant
    
    Args:
        gene (str): Gene symbol (e.g., 'EGFR')
        alteration (str): Protein change (e.g., 'L858R' or 'p.Leu858Arg')
        api_key (str): OncoKB API key (optional, will use env var if not provided)
    
    Returns:
        dict: OncoKB response data or error message
    """
    if not api_key:
        api_key = ONCOKB_API_KEY or os.getenv("ONCOKB_API_KEY")
    
    if not api_key:
        return {"error": "ONCOKB_API_KEY not found in environment variables"}
    
    base_url = "https://www.oncokb.org/api/v1/annotate/mutations/byProteinChange"
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json"
    }
    
    # Get all variant formats
    try:
        all_formats = convert_any_variant(alteration)
        # Create list of all unique variant strings to try
        variants_to_try = [all_formats["1L"]]
       
    except:
        # If conversion fails, just try the original
        variants_to_try = [alteration]
    
    print(f"Trying OncoKB with variants: {variants_to_try}")
    
    # Try each variant format
    for variant in variants_to_try:
        params = {
            "hugoSymbol": gene,
            "alteration": variant,
            "referenceGenome": "GRCh37"
        }
        
        try:
            response = requests.get(base_url, headers=headers, params=params)
            
            if response.status_code == 200:
                result = response.json()
                # Check if we got meaningful data (not just empty response)
                if result and (result.get('query') or result.get('geneExist')):
                    print(f"OncoKB success with variant format: {variant}")
                    return result
            elif response.status_code != 404:
                # Non-404 errors should be reported
                return {
                    "error": f"OncoKB API error: {response.status_code}",
                    "message": response.text
                }
        
        except requests.exceptions.RequestException as e:
            continue
    
    # If all formats failed, return error
    return {
        "error": "No OncoKB data found for any variant format",
        "tried_variants": variants_to_try
    }

def save_oncokb_result(gene, protein_change, data, output_dir):
    """
    Save OncoKB result to JSON file
    
    Args:
        gene (str): Gene symbol
        protein_change (str): Protein change
        data (dict): OncoKB response data
        output_dir (str): Output directory
    """
    os.makedirs(output_dir, exist_ok=True)
    filename = f"{gene}_{protein_change}_oncokb.json"
    filepath = os.path.join(output_dir, filename)
    
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2)
    
    return filepath