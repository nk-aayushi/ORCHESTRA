import requests
import json
import xml.etree.ElementTree as ET
import os
import re
import pandas as pd
import time
from HelperScripts.convertProteinCode import convertProteinCode
from HelperScripts.allVar import convert_any_variant

apiKey = '<YOUR_NCBI_API_KEY>'

# Rate limiter for PubMed API (5 requests per second)
class PubMedRateLimiter:
    def __init__(self, requests_per_second=5):
        self.min_interval = 1.0 / requests_per_second
        self.last_request_time = 0
    
    def wait(self):
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        if time_since_last < self.min_interval:
            time.sleep(self.min_interval - time_since_last)
        self.last_request_time = time.time()

rate_limiter = PubMedRateLimiter()

def searchPubmedFusion(allPubmed, gene1, gene2, fusionType = None, cancer_type = None):
    print("-"*80)
    print(f"Searching pubmed fusion with advanced filtering{f' (cancer type: {cancer_type})' if cancer_type else ''}")
    print("-"*80)
    literature_summaries = []
    url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"

    # Clinical intent keywords
    clinical_keywords = "(treatment OR therapy OR response OR resistance OR drug OR clinical OR outcome OR efficacy OR prognosis)"
    
    # Base filters: English, Humans, Year >= 2010
    base_filters = 'AND ("2010"[Date - Publication] : "3000"[Date - Publication]) AND (English[Language]) AND (Humans[MeSH Terms])'
    
    # Article type filters
    clinical_types = '("Clinical Trial"[Publication Type] OR "Clinical Study"[Publication Type] OR "Observational Study"[Publication Type] OR "Case Reports"[Publication Type])'
    review_type = '"Review"[Publication Type]'

    allPMIds = []
    
    def _run_query(query, ptype, retmax=100):
        params = {
            "db": "pubmed",
            "term": query,
            "retmode": "json",
            "retmax": retmax,
            "api_key": apiKey
        }
        rate_limiter.wait()
        resp = requests.get(url, params=params)
        d = resp.json()
        if 'esearchresult' in d and 'idlist' in d['esearchresult']:
            for pid in d['esearchresult']['idlist']:
                allPMIds.append((pid, ptype))
        else:
            print(f"Warning: No results for query: {query[:100]}...")
    
    # Build fusion query term
    fusion_term = f'{gene1}::{gene2}'
    if fusionType:
        fusion_term += f' {fusionType}'
    
    # Query 1: Fusion-specific clinical articles (no cancer_type hard filter)
    _run_query(f'{fusion_term} AND cancer AND {clinical_keywords} AND {clinical_types} {base_filters}', 'clinical')
    
    # Query 2: Fusion-specific reviews
    _run_query(f'{fusion_term} AND cancer AND {clinical_keywords} AND {review_type} {base_filters}', 'review', retmax=50)
    
    # Query 3: Gene-level — papers about either gene's fusions/rearrangements (catches other fusion partners)
    gene_level_query = f'({gene1} OR {gene2}) AND (fusion OR rearrangement OR translocation) AND cancer AND {clinical_keywords} AND {clinical_types} {base_filters}'
    _run_query(gene_level_query, 'gene_level', retmax=50)
    gene_level_review = f'({gene1} OR {gene2}) AND (fusion OR rearrangement OR translocation) AND cancer AND {clinical_keywords} AND {review_type} {base_filters}'
    _run_query(gene_level_review, 'gene_level_review', retmax=30)
    
    # Deduplicate: fusion-specific types take priority over gene_level
    pmid_dict = {}
    for pmid, ptype in allPMIds:
        if pmid not in pmid_dict:
            pmid_dict[pmid] = ptype
        elif ptype in ('clinical', 'review') and pmid_dict[pmid].startswith('gene_level'):
            pmid_dict[pmid] = ptype
        
    allIds = list(pmid_dict.keys())
    for pmid in allIds:
        allPubmed.append(pmid)
    
    fusion_specific = sum(1 for t in pmid_dict.values() if t in ('clinical', 'review'))
    gene_level = sum(1 for t in pmid_dict.values() if t.startswith('gene_level'))
    print(f"Found {len(allIds)} papers ({fusion_specific} fusion-specific, {gene_level} gene-level)")
    print("Fetching metadata and scoring papers...")
    fetch_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
    params = {
        "db": "pubmed",
        "id": ",".join(allPubmed),
        "retmode": "xml",
        "api_key": apiKey
    }

    rate_limiter.wait()
    response = requests.get(fetch_url, params=params)
    root = ET.fromstring(response.text)
    
    # Score each paper
    scored_papers = []

    for article in root.findall(".//PubmedArticle"):
        pmid_elem = article.find(".//PMID")
        pmid = pmid_elem.text if pmid_elem is not None else "Unknown PMID"
        
        title_elem = article.find(".//ArticleTitle")
        title = ''.join(title_elem.itertext()) if title_elem is not None else "No Title"
        
        abstract_parts = []
        for abstract_text in article.findall(".//AbstractText"):
            label = abstract_text.attrib.get('Label', '')
            section = f"{label}: " if label else ""
            section += ''.join(abstract_text.itertext())
            abstract_parts.append(section)
        full_abstract = "\n".join(abstract_parts) if abstract_parts else "No Abstract"
        
        # Calculate relevance score
        score = 0
        combined_text = (title + " " + full_abstract).lower()
        
        # Exact fusion mention (+3)
        fusion_matched = False
        if f'{gene1.lower()}::{gene2.lower()}' in combined_text or f'{gene1.lower()}-{gene2.lower()}' in combined_text:
            score += 3
            fusion_matched = True
        
        # Both genes mentioned (+2)
        if gene1.lower() in combined_text and gene2.lower() in combined_text:
            score += 2
            if not fusion_matched:
                fusion_matched = True  # close enough — both partners present
        
        # Fusion type mentioned (+1)
        if fusionType and fusionType.lower() in combined_text:
            score += 1
        
        # Clinical keywords (+1)
        clinical_terms = ['treatment', 'therapy', 'response', 'resistance', 'drug', 'efficacy', 'outcome']
        if any(term in combined_text for term in clinical_terms):
            score += 1
        
        # Cancer type mention (+3) — equally important as fusion match
        if cancer_type and cancer_type.lower() in combined_text:
            score += 3
        
        # Review penalty (-1)
        if pmid in pmid_dict and pmid_dict[pmid] in ('review', 'gene_level_review'):
            score -= 1
        
        evidence_tier = 'fusion_specific' if fusion_matched else 'gene_level'
        
        scored_papers.append({
            "pmid": pmid,
            "title": title,
            "abstract": full_abstract,
            "score": score,
            "is_review": pmid_dict.get(pmid) in ('review', 'gene_level_review'),
            "evidence_tier": evidence_tier
        })
    
    # Sort by score (highest first) and take top 25
    scored_papers.sort(key=lambda x: x['score'], reverse=True)
    top_papers = scored_papers[:25]
    allPubmedTop = []
    
    print(f"Ranked papers, keeping top {len(top_papers)} by relevance score")
    
    # Build literature summaries from top papers
    for paper in top_papers:
        allPubmedTop.append(paper['pmid'])
    print(allPubmedTop)  
    print("Searching for available PMCs")
    elink_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/elink.fcgi"
    
    pmcIds = []
    onlyPubmedIds = []
    pmid_to_pmc = {}
    
    for PMId in allPubmedTop:
        #print(PMId)
        elink_params = {
            "dbfrom": "pubmed",
            "db": "pmc",
            "id": PMId,
            "retmode": "json",
            "api_key": apiKey
        }
        try:
            rate_limiter.wait()
            response = requests.get(elink_url, params=elink_params, timeout=30)
            data = response.json()
            #print(data)
            for linkset in data.get('linksets', []):
                #print(linkset)
                pmid = linkset.get('ids', [None])[0]
                if pmid is None:
                    continue
                pmid = str(pmid)
                pmc_links = []
                for linksetdb in linkset.get('linksetdbs', []):
                    if linksetdb.get('dbto') == 'pmc':
                        pmc_links = linksetdb.get('links', [])
                        break
                if pmc_links:
                    pmid_to_pmc[pmid] = str(pmc_links[0])
        except (json.JSONDecodeError, requests.exceptions.RequestException) as e:
            print(f"Warning: Failed to fetch PMC links for batch ({type(e).__name__}), skipping")
    
    for pmid in allPubmedTop:
        if pmid in pmid_to_pmc:
            pmcIds.append(pmid_to_pmc[pmid])
        else:
            onlyPubmedIds.append(pmid)
    
    print(f"PMC available: {len(pmcIds)}, PubMed only: {len(onlyPubmedIds)}")
    print(f"pmcIds: {pmcIds}")
    print(f"onlyPubmedIds: {onlyPubmedIds}")

    for paper in top_papers:
        if paper['pmid'] in onlyPubmedIds:
            if paper['abstract'] is not None and paper['abstract'] != "No Abstract":
                literature_summaries.append({
                    "pmid": paper['pmid'],
                    "title": paper['title'],
                    "abstract": paper['abstract'],
                    "sections": None,
                    "source": "pubmed",
                    "relevance_score": paper['score'],
                    "is_review": paper['is_review'],
                    "evidence_tier": paper['evidence_tier']
                })

    def extract_text_except_methods(element, indent=0):
        """Recursively extract text excluding <methods> section with indentation."""
        text = ""

        # Skip <methods> section
        if element.tag == "sec":
            title = element.find("title")
            if title is not None and title.text:
                if "methods" in title.text.lower():
                    return ""  # Skip the methods section

        # Extract text content
        if element.text and element.text.strip():
            text += " " * indent + element.text.strip() + "\n"

        # Iterate over child elements
        for child in element:
            if child.tag == "title":
                if child.text and child.text.strip():
                    text += " " * indent + f"--- {child.text.strip()} ---\n"
            else:
                text += extract_text_except_methods(child, indent + 2)

        if element.tail and element.tail.strip():
            text += " " * indent + element.tail.strip() + "\n"

        return text

    for PMCId in pmcIds:
        try:
            rate_limiter.wait()
            pmc_url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pmc&id={PMCId}&retmode=xml"
            pmc_response = requests.get(pmc_url, timeout=30)
            root = ET.fromstring(pmc_response.content)

            title = None
            title_element = root.find(".//title-group/article-title")
            if title_element is not None:
                title = ''.join(title_element.itertext()).strip()


            abstract = root.findall(".//abstract")
            abstractText = None
            fullAbstract = None
            if abstract:
                abstractText = abstract[0].find("p")
            if abstractText is not None:
                fullAbstract = ''.join(abstractText.itertext()).strip()
            
            body = root.find(".//body")
            
            
            if title is not None:
                combined_text = extract_text_except_methods(body) if body is not None else None
                literature_summaries.append({
                    "pmcid": PMCId,
                    "title": title,
                    "abstract": fullAbstract,
                    "sections": combined_text,
                    "source": "pmc"
                })
        except Exception as e:
            print(f"Warning: Failed to fetch PMC article {id} ({type(e).__name__}), skipping")
            continue
    
    final_json = {
        "variant": f"{gene1}::{gene2} {fusionType if fusionType else 'fusion'}",
        "total_papers_found": len(allPubmed),
        "papers_processed": len(literature_summaries),
        "literature_summaries": literature_summaries
    }

    with open("extracted_FrompubmedAndPMC.json", "w", encoding="utf-8") as f:
        json.dump(final_json, f, indent=2, ensure_ascii=False)