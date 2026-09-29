import requests
import xml.etree.ElementTree as ET
from HelperScripts.allVar import convert_any_variant
from HelperScripts.allCChange import convertCChange
import logging
logger = logging.getLogger(__name__)

apiKey = '<YOUR_NCBI_API_KEY>'


def getIdList(variant):
    url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=clinvar&term={variant}&retmode=json&api_key={apiKey}"
    
    try:
        response = requests.get(url)
        response.raise_for_status()

        if not response.content:
            logger.warning("Empty response from NCBI elink")
            return None

        data = response.json()
        idlist = data["esearchresult"]["idlist"]
        return idlist
    
    except requests.exceptions.Timeout:
        logger.warning("NCBI elink request timed out")

    except requests.exceptions.HTTPError as e:
        status = e.response.status_code if e.response else "unknown"
        logger.warning("NCBI elink HTTP %s", status)

    except requests.exceptions.RequestException as e:
        logger.warning("NCBI elink request failed")

    except ValueError:
        logger.warning("Invalid JSON from NCBI elink")

    return None

    

def get_variant_details(ids):

    if ids is None:
        return None

    esummary_url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=clinvar&id={','.join(ids)}&retmode=json&api_key={apiKey}"

    try:
        response = requests.get(esummary_url)
        response.raise_for_status()

        if not response.content:
            logger.warning("Empty response from NCBI elink")
            return None

        return response.json().get("result", {})
    
    except requests.exceptions.Timeout:
        logger.warning("NCBI elink request timed out")

    except requests.exceptions.HTTPError as e:
        status = e.response.status_code if e.response else "unknown"
        logger.warning("NCBI elink HTTP %s", status)

    except requests.exceptions.RequestException as e:
        logger.warning("NCBI elink request failed")

    except ValueError:
        logger.warning("Invalid JSON from NCBI elink")

    return None
    

# Step 2: Fetch citations using ELink
def get_citations(ids):
    if ids is None:
        return None

    elink_url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/elink.fcgi?dbfrom=clinvar&db=pubmed&id={','.join(ids)}&retmode=json&api_key={apiKey}"
    
    try:
        response = requests.get(elink_url)
        response.raise_for_status()

        if not response.content:
            logger.warning("Empty response from NCBI elink")
            return None

        data = response.json()

        citations = {}
        for linkset in data.get("linksets", []):
            for id_link in linkset.get("linksetdbs", []):
                if id_link.get("linkname") == "clinvar_pubmed":
                    citations[linkset["ids"][0]] = id_link.get("links", [])
        return citations
    
    except requests.exceptions.Timeout:
        logger.warning("NCBI elink request timed out")

    except requests.exceptions.HTTPError as e:
        status = e.response.status_code if e.response else "unknown"
        logger.warning("NCBI elink HTTP %s", status)

    except requests.exceptions.RequestException as e:
        logger.warning("NCBI elink request failed")

    except ValueError:
        logger.warning("Invalid JSON from NCBI elink")

    return None
    
def format_allele_freq(allele_freq_set):
    return {
        entry["source"]: {
            "frequency": float(entry["value"]) if entry.get("value") else None,
            "minor_allele": entry.get("minor_allele") or None
        }
        for entry in allele_freq_set
    }

# Step 3: Combine results
def getResults(idlist, cnvType, gene):

    if idlist is None or len(idlist) == 0:
        return ("", 0, [])

    variant_data = get_variant_details(idlist)
    # print(variant_data)
    citations = get_citations(idlist)

    if variant_data is None and citations is None:
        return ("", 0, [])
    
    allArticles = ""
    results = []
    numPrint = 0
    # Display combined results
    for vid in idlist:
        variant = variant_data.get(vid, {})
        title = variant.get('title')
        index = title.find(gene)

        if(index != -1):
            if(cnvType == ""):
                return ("", 0, [])

            if(variant.get('obj_type').lower() != cnvType.lower()):
                continue
            else:
                numPrint = 1
                variation_set = variant.get('variation_set', [])
                for var in variation_set:
                    allele_freq = var.get('allele_freq_set')
                    variant_loc = var.get('variation_loc')
                    aliases = var.get('aliases')
                    # if allele_freq:
                    #     print(allele_freq)
                    # if variant_loc:
                    #     print(variant_loc)
                    # if aliases:
                    #     print(aliases)
                
                result_entry = {
                    "id": variant.get('uid'),
                    "title": title,
                    "germline_classification": variant.get('germline_classification', {}).get('description'),
                    "clinical_impact_classification": variant.get('clinical_impact_classification', {}).get('description'),
                    "oncogenicity_classification": variant.get('oncogenicity_classification', {}).get('description'),
                    "consequence": variant.get('molecular_consequence_list'),
                    "protein_change": variant.get('protein_change'),
                    "allele_freqency": format_allele_freq(allele_freq)
                    
                }
                
                
                # Print citations
                cited_articles = citations.get(vid, [])
                if cited_articles:
                    result_entry["citedArticles"] = ', '.join(cited_articles)
                    allArticles = allArticles + ', '.join(cited_articles)

                results.append(result_entry)
                
        else:
            continue
    return(allArticles, numPrint, results)



def runClinvarQueryCNV(gene, cnvType, allPubmed):

    clinvarOut = {
        "section": "Clinvar",
        "variants": [],
        "message": ""
    }

    print("-"*80)
    print("Searching Clinvar")
    print("-"*80)

    if (cnvType == ""):
        clinvarOut["message"] = "No results found on ClinVar"

    else:
        allPubmed = []
        print(cnvType)
        listVar = [gene, cnvType]
        variant = " ".join(listVar)
        idlist = getIdList(variant)
        res = getResults(idlist, cnvType, gene)
        print(res[1])
        if(res[1] != 0):
            clinvarOut["variants"].append(res[2])
        allArticles = res[0]
        allArticles = [pmid.strip() for pmid in allArticles.split(',')]
        for pmids in allArticles:
            allPubmed.append(pmids)

    return(clinvarOut, allPubmed)
