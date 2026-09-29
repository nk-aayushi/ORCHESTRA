import requests
import logging
from urllib.parse import quote
import pandas as pd

logger = logging.getLogger(__name__)

# NM_001378902.1:c.(3601C>T), ROS1
# ('NM_001378902.1(NP_001365831.1):p.(Leu1201Phe)', 'all good')

def makeHGVS(geneName, change):
    df = pd.read_csv("MANE.GRCh38.v1.5.summary.txt", sep="\t")
    geneId = df[df["symbol"] == geneName]['RefSeq_nuc'].values[0]
    return f"{geneId}:{change}"

def mutalyzer_normalize(hgvs, only_variants=False):
    encoded = quote(hgvs, safe="():>")
    url = f"https://mutalyzer.nl/api/normalize/{encoded}"

    params = {
        "sequence": hgvs,
        "only_variants": str(only_variants).lower()
    }

    try:
        r = requests.get(url, params=params, timeout=30)
        r.raise_for_status()

        if not r.content:
            logger.warning("Empty response from Mutalyzer for %s", hgvs)
            return None

        return r.json()

    except requests.exceptions.Timeout:
        logger.warning("Mutalyzer timeout for %s", hgvs)

    except requests.exceptions.HTTPError as e:
        status = e.response.status_code if e.response else "unknown"
        logger.warning("Mutalyzer HTTP %s for %s", status, hgvs)

    except requests.exceptions.RequestException as e:
        logger.warning("Mutalyzer request failed for %s: %s", hgvs, e)

    except ValueError:
        logger.warning("Invalid JSON from Mutalyzer for %s", hgvs)

    return None

def mulayzer_dnaToProtein(dnaCode):
    data = mutalyzer_normalize(dnaCode)
    if data is not None:
        protein_hgvs = data["protein"]["description"]
        return (protein_hgvs, "protein", "all good")
    return (None, "protein", "Mutalyzer normalization failed")

def mutalyzer_proteinToDNA(proteinCode, referenceSequence=None):
    data = mutalyzer_normalize(proteinCode)
    if data is not None:
        dna_hgvs = data["back_translated_descriptions"][0]
        return (dna_hgvs, "dna", "Please verify this conversion as it may not be unique.")
    return (None, "dna", "Mutalyzer normalization failed")

def preetify(obj):
    if obj[0] is not None:
        if obj[1] == "dna":
            return "c." + obj[0].split(":c.")[1].strip("()")
        elif obj[1] == "protein":
            return "p." + obj[0].split(":p.")[1].strip("()")
    else:
        return None 


def dnaToProtein(geneName, cChange):
    res = mulayzer_dnaToProtein(makeHGVS(geneName, cChange))
    return preetify(res)

def proteinToDNA(geneName, pChange):
    res = mutalyzer_proteinToDNA(makeHGVS(geneName, pChange))
    return preetify(res)

