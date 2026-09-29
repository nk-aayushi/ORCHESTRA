import requests
import json
import xml.etree.ElementTree as ET
import os
import re
import pandas as pd
from HelperScripts.clinvarSearchBasev2 import runClinvarQuery
from HelperScripts.civicSearchBase import runCivicQuery
from HelperScripts.pubmedSearchBase import searchPubmed
from HelperScripts.pubmedSearchFusion import searchPubmedFusion
from HelperScripts.civicSearchFusion import runCivicQueryFusion
# from HelperScripts.genomeNexus import get_variant_annotation
from HelperScripts.oncokbSearch import fetch_oncokb, save_oncokb_result
from HelperScripts.oncokbSearchCNV import fetch_oncokb_cnv, save_oncokb_cnv_result
from HelperScripts.oncokbSearchFusion import fetch_oncokb_fusion, save_oncokb_fusion_result
from HelperScripts.mutalyzer import dnaToProtein, proteinToDNA
from HelperScripts.clinvarSearchCNV import runClinvarQueryCNV

var = pd.read_csv("ngs_report_summary.csv", sep=",")
cancer_type = str(var['cancer_type'].iloc[0]).strip() if 'cancer_type' in var.columns and pd.notna(var['cancer_type'].iloc[0]) else None

import sys
# Accept full job directory path (e.g. study_jobs/Lung_Cancer/1 or jobs/old_job)
JOB_PATH = sys.argv[1] if len(sys.argv) > 1 else None

if JOB_PATH:
    job_base = JOB_PATH
else:
    job_base = None

if job_base:
    for sub in ["clinvar_output", "civic_output", "pubmed_output", "oncokb_output", "summary"]:
        os.makedirs(f"{job_base}/{sub}", exist_ok=True)
else:
    for sub in ["clinvar_output", "civic_output", "pubmed_output", "oncokb_output", "summary"]:
        os.makedirs(sub, exist_ok=True)

def get_output_path(base_dir, filename):
    if job_base:
        return f"{job_base}/{base_dir}/{filename}" if filename else f"{job_base}/{base_dir}"
    return f"{base_dir}/{filename}" if filename else base_dir

def variant_files_exist(gene, identifier, variant_type):
    """Check if all output files for a specific variant already exist"""
    if variant_type == "SNV":
        # gn_path = f"genomenexus_output/{gene}_{identifier}_genomenexus.json"
        cv_path = get_output_path("clinvar_output", f"{gene}_{identifier}_clinvar.json")
        civic_path = get_output_path("civic_output", f"{gene}_{identifier}_civic.json")
        oncokb_path = get_output_path("oncokb_output", f"{gene}_{identifier}_oncokb.json")
        pubmed_path = get_output_path("pubmed_output", f"{gene}_{identifier}_extracted_FrompubmedAndPMC.json")
        
        # gn_exists = os.path.exists(gn_path)
        cv_exists = os.path.exists(cv_path)
        civic_exists = os.path.exists(civic_path)
        oncokb_exists = os.path.exists(oncokb_path)
        pubmed_exists = os.path.exists(pubmed_path)
        
        all_exist = cv_exists and civic_exists and oncokb_exists and pubmed_exists
        print(f"Checking SNV {gene}_{identifier}: CV={cv_exists}, Civic={civic_exists}, OncoKB={oncokb_exists}, PubMed={pubmed_exists} -> Skip={all_exist}")
        return all_exist
        
    elif variant_type == "CNV":
        cv_path = get_output_path("clinvar_output", f"{gene}_{identifier}_clinvar.json")
        civic_path = get_output_path("civic_output", f"{gene}_{identifier}_civic.json")
        oncokb_path = get_output_path("oncokb_output", f"{gene}_{identifier}_oncokb.json")
        pubmed_path = get_output_path("pubmed_output", f"{gene}_{identifier}_extracted_FrompubmedAndPMC.json")
        
        cv_exists = os.path.exists(cv_path)
        civic_exists = os.path.exists(civic_path)
        oncokb_exists = os.path.exists(oncokb_path)
        pubmed_exists = os.path.exists(pubmed_path)
        
        all_exist = cv_exists and civic_exists and oncokb_exists and pubmed_exists
        print(f"Checking CNV {gene}_{identifier}: CV={cv_exists}, Civic={civic_exists}, OncoKB={oncokb_exists}, PubMed={pubmed_exists} -> Skip={all_exist}")
        return all_exist
        
    elif variant_type == "FUSION":
        civic_path = get_output_path("civic_output", f"{gene}_{identifier}_civic.json")
        oncokb_path = get_output_path("oncokb_output", f"{gene}_{identifier}_oncokb.json")
        pubmed_path = get_output_path("pubmed_output", f"{gene}_{identifier}_extracted_FrompubmedAndPMC.json")
        
        civic_exists = os.path.exists(civic_path)
        oncokb_exists = os.path.exists(oncokb_path)
        pubmed_exists = os.path.exists(pubmed_path)
        
        all_exist = civic_exists and oncokb_exists and pubmed_exists
        print(f"Checking FUSION {gene}_{identifier}: Civic={civic_exists}, OncoKB={oncokb_exists}, PubMed={pubmed_exists} -> Skip={all_exist}")
        return all_exist
        
    return False

#we need to select those i s which don't have synonymous or benign written in them
def giveMutList(var):
    idList = []
    for i in range(0, len(var)):
        if(var["variant_classification"][i] == "synonymous" or var["variant_classification"][i] == "Benign"):
            continue
        else:
            idList.append(i)
    datAbs = []
    
    for ids in idList:
        dat = {}
        
        # Handle empty/NaN variant_type values
        variant_type_raw = var['variant_type'][ids]
        if pd.isna(variant_type_raw) or variant_type_raw == "":
            # Determine variant type based on available columns
            if not pd.isna(var.get('gene_5prime', {}).get(ids)) and not pd.isna(var.get('gene_3prime', {}).get(ids)):
                mutationType = "FUSION"
            elif not pd.isna(var.get('cnv_type', {}).get(ids)) or not pd.isna(var.get('copy_number', {}).get(ids)):
                mutationType = "CNV"
            elif not pd.isna(var.get('coding_change', {}).get(ids)) or not pd.isna(var.get('protein_change', {}).get(ids)):
                mutationType = "SNV"
            else:
                print(f"Skipping variant at index {ids} - cannot determine variant type")
                continue
        else:
            mutationType = str(variant_type_raw).upper()
        
        # Map variant types to standard categories
        if mutationType in ["MISSENSE", "NONSENSE", "FRAMESHIFT", "SPLICE_SITE", "INFRAME_INSERTION", "INFRAME_DELETION"]:
            mutationType = "SNV"
        
        # If variant type is not recognized, determine based on available fields
        if mutationType not in ["SNV", "DELINS", "CNV", "FUSION"]:
            if not pd.isna(var.get('gene_5prime', {}).get(ids)) and not pd.isna(var.get('gene_3prime', {}).get(ids)):
                mutationType = "FUSION"
            elif not pd.isna(var.get('cnv_type', {}).get(ids)) or not pd.isna(var.get('copy_number', {}).get(ids)):
                mutationType = "CNV"
            elif not pd.isna(var.get('coding_change', {}).get(ids)) or not pd.isna(var.get('protein_change', {}).get(ids)):
                mutationType = "SNV"
            else:
                print(f"Skipping variant at index {ids} - unsupported variant type: {variant_type_raw}")
                continue
        
        if mutationType == "SNV" or mutationType == "DELINS":
            foundCChange = 0
            foundPChange = 0
            dat["mutationType"] = mutationType
            dat["gene"] = var['gene'][ids]
            cChange = var['coding_change'][ids]
            
            # Handle NaN/empty values
            if pd.isna(cChange):
                cChange = ""
            else:
                cChange = str(cChange)
            
            if "(" in cChange:
                match = re.findall(r"p\.\(([^)]*)\)", cChange)
                dat["cChange"] = "c."+match[0]
                foundCChange = 1
            elif cChange:
                dat["cChange"] = cChange
                foundCChange = 1
            else:
                dat["cChange"] = ""
            
            pChange = var['protein_change'][ids]
            if pd.isna(pChange):
                pChange = ""
            else:
                pChange = str(pChange)
            
            if "(" in pChange:
                match = re.findall(r"p\.\(([^)]*)\)", pChange)
                dat["pChange"] = "p."+match[0]
                foundPChange = 1
            elif pChange:
                dat["pChange"] = pChange
                foundPChange = 1
            else:
                dat["pChange"] = ""

            if foundCChange == 0 and foundPChange == 1 and dat["pChange"]:
                #convert pChange to cChange
                try:
                    convertedCChange = proteinToDNA(dat["gene"], dat["pChange"])
                    if convertedCChange is not None:
                        dat["cChange"] = convertedCChange
                    else:
                        dat["cChange"] = ""
                except:
                    dat["cChange"] = ""
            
            elif foundPChange == 0 and foundCChange == 1 and dat["cChange"]:
                #convert cChange to pChange
                try:
                    convertedPChange = dnaToProtein(dat["gene"], dat["cChange"])
                    if convertedPChange is not None:
                        dat["pChange"] = convertedPChange
                    else:
                        dat["pChange"] = ""
                except:
                    dat["pChange"] = ""
            
            # Skip variant if both cChange and pChange are empty
            if not dat.get("cChange") and not dat.get("pChange"):
                print(f"Skipping {dat['gene']} - no coding or protein change")
                continue

        elif mutationType == "CNV":
            dat["mutationType"] = mutationType
            dat["gene"] = var['gene'][ids]
            dat["cnvType"] = var['cnv_type'][ids]
            dat["copyNo"] = var['copy_number'][ids]
        elif mutationType == "FUSION":
            dat["mutationType"] = mutationType
            dat["gene1"] = var['gene_5prime'][ids]
            dat["gene2"] = var['gene_3prime'][ids]
            dat["fusionType"] = var['fusion_name'][ids]
        else:
            print(mutationType)
            print("This type of mutation is not supported")
            continue
        datAbs.append(dat)

    return datAbs

for mut in giveMutList(var):
    mutationType = mut["mutationType"]
    print(mut)
    
    if mutationType == "SNV" or mutationType == "DELINS":
        gene = mut["gene"]
        cChange = mut["cChange"]
        pChange = mut["pChange"]
        
        if variant_files_exist(gene, pChange, "SNV"):
            print(f"Skipping {gene}_{pChange} - all files already exist")
            continue
        
        # Get GenomeNexus annotation
        # gn_path = f"genomenexus_output/{gene}_{pChange}_genomenexus.json"
        # if not os.path.exists(gn_path):
        #     gn_data = get_variant_annotation(gene, cChange)
        #     with open(gn_path, "w") as f:
        #         json.dump(gn_data, f, indent=2)
        # else:
        #     print(f"GenomeNexus file exists, skipping")
        
        # Get OncoKB annotation
        oncokb_path = get_output_path("oncokb_output", f"{gene}_{pChange}_oncokb.json")
        if not os.path.exists(oncokb_path):
            protein_change_clean = pChange.replace("p.", "")
            oncokb_data = fetch_oncokb(gene, protein_change_clean)
            oncokb_dir = get_output_path("oncokb_output", "")
            save_oncokb_result(gene, pChange, oncokb_data, oncokb_dir)
        else:
            print(f"OncoKB file exists, skipping")
        
        # ClinVar and CIViC
        cv_path = get_output_path("clinvar_output", f"{gene}_{pChange}_clinvar.json")
        civic_path = get_output_path("civic_output", f"{gene}_{pChange}_civic.json")
        pubmed_path = get_output_path("pubmed_output", f"{gene}_{pChange}_extracted_FrompubmedAndPMC.json")
        
        if not os.path.exists(cv_path) or not os.path.exists(civic_path) or not os.path.exists(pubmed_path):
            def returnDicts(gene, cChange, pChange):
                allPubmed = []
                clinvarOut, allPubmedClinvar = runClinvarQuery(gene, cChange, pChange, allPubmed)
                print(clinvarOut)
                civicOut = {}
                resCivic, allPubmedCivic = runCivicQuery(gene, pChange, allPubmed, civicOut)
                allPubmed = list(set(allPubmedClinvar + allPubmedCivic))
                return (clinvarOut, resCivic, allPubmed)
            dicts = returnDicts(gene, cChange, pChange)
            
            # Save ClinVar output
            if not os.path.exists(cv_path):
                with open(cv_path, "w") as f:
                    json.dump(dicts[0], f, indent=2)
            else:
                print(f"ClinVar file exists, skipping")
            
            # Save CIViC output
            if not os.path.exists(civic_path):
                with open(civic_path, "w") as f:
                    json.dump(dicts[1], f, indent=2)
            else:
                print(f"CIViC file exists, skipping")
            
            # PubMed search
            if not os.path.exists(pubmed_path):
                searchPubmed(dicts[2], gene, pChange, cancer_type=cancer_type)
                if os.path.exists("extracted_FrompubmedAndPMC.json"):
                    os.rename("extracted_FrompubmedAndPMC.json", pubmed_path)
            else:
                print(f"PubMed file exists, skipping")
        else:
            print(f"ClinVar, CIViC, and PubMed files exist, skipping")

    elif mutationType == "CNV":
        gene = mut["gene"]
        cnvType = mut["cnvType"]
        if cnvType.lower() == "gain" or cnvType.lower() == "amplification" or cnvType.lower() == "duplication":
            cnvType = "amplification"
        elif cnvType.lower() == "loss" or cnvType.lower() == "deletion":
            cnvType = "deletion"
        else:
            print("This type of CNV is not supported")
        copyNo = mut["copyNo"]
        
        if variant_files_exist(gene, cnvType, "CNV"):
            print(f"Skipping {gene}_{cnvType} - all files already exist")
            continue
        
        # Get OncoKB CNV annotation
        oncokb_path = get_output_path("oncokb_output", f"{gene}_{cnvType}_oncokb.json")
        if not os.path.exists(oncokb_path):
            oncokb_cnv_data = fetch_oncokb_cnv(gene, cnvType)
            oncokb_dir = get_output_path("oncokb_output", "")
            save_oncokb_cnv_result(gene, cnvType, oncokb_cnv_data, oncokb_dir)
        else:
            print(f"OncoKB file exists, skipping")
        
        # ClinVar, CIViC, and PubMed
        cv_path = get_output_path("clinvar_output", f"{gene}_{cnvType}_clinvar.json")
        civic_path = get_output_path("civic_output", f"{gene}_{cnvType}_civic.json")
        pubmed_path = get_output_path("pubmed_output", f"{gene}_{cnvType}_extracted_FrompubmedAndPMC.json")
        
        if not os.path.exists(cv_path) or not os.path.exists(civic_path) or not os.path.exists(pubmed_path):
            def returnDicts(gene, cnvType):
                civicOut = {}
                allPubmed = []
                if cnvType == "amplification":
                    clinvarOut, allPubmedClinvar = runClinvarQueryCNV(gene, "duplication", allPubmed)
                else:
                    clinvarOut, allPubmedClinvar = runClinvarQueryCNV(gene, cnvType, allPubmed)
                resCivic, allPubmedCivic = runCivicQuery(gene, cnvType, allPubmed, civicOut)
                allPubmed = list(set(allPubmedCivic + allPubmedClinvar))
                return (clinvarOut, resCivic, allPubmed)
            dicts = returnDicts(gene, cnvType)
            
            # Save CIViC output
            if not os.path.exists(civic_path):
                with open(civic_path, "w") as f:
                    json.dump(dicts[1], f, indent=2)
            else:
                print(f"CIViC file exists, skipping")
            
            # Save ClinVar output
            if not os.path.exists(cv_path):
                with open(cv_path, "w") as f:
                    json.dump(dicts[0], f, indent=2)
            else:
                print(f"ClinVar file exists, skipping")
            
            # PubMed search
            if not os.path.exists(pubmed_path):
                print(dicts[2])
                if copyNo == "" or copyNo is None:
                    searchPubmed(dicts[2], gene, cnvType, copyNo, cancer_type=cancer_type)
                else:
                    searchPubmed(dicts[2], gene, cnvType, cancer_type=cancer_type)
                if os.path.exists("extracted_FrompubmedAndPMC.json"):
                    os.rename("extracted_FrompubmedAndPMC.json", pubmed_path)
            else:
                print(f"PubMed file exists, skipping")
        else:
            print(f"ClinVar, CIViC, and PubMed files exist, skipping")

    elif mutationType == "FUSION":
        allPubmed = []
        gene1 = mut["gene1"]
        gene2 = mut["gene2"]
        fusionType = mut["fusionType"]
        
        if variant_files_exist(gene1, f"{gene2}_{fusionType}", "FUSION"):
            print(f"Skipping {gene1}_{gene2}_{fusionType} - all files already exist")
            continue
        
        # Get OncoKB fusion annotation
        oncokb_path = get_output_path("oncokb_output", f"{gene1}_{gene2}_{fusionType}_oncokb.json")
        if not os.path.exists(oncokb_path):
            oncokb_fusion_data = fetch_oncokb_fusion(gene1, gene2)
            oncokb_dir = get_output_path("oncokb_output", "")
            save_oncokb_fusion_result(gene1, gene2, fusionType, oncokb_fusion_data, oncokb_dir)
        else:
            print(f"OncoKB file exists, skipping")
        
        # CIViC and PubMed
        civic_path = get_output_path("civic_output", f"{gene1}_{gene2}_{fusionType}_civic.json")
        pubmed_path = get_output_path("pubmed_output", f"{gene1}_{gene2}_{fusionType}_extracted_FrompubmedAndPMC.json")
        
        if not os.path.exists(civic_path) or not os.path.exists(pubmed_path):
            def returnDicts(gene1, gene2, fusionType):
                allPubmed = []
                civicOut = {}
                resCivic, allPubmedCivic = runCivicQueryFusion(gene1, gene2, fusionType, allPubmed, civicOut)
                allPubmed = list(set(allPubmedCivic))
                return (resCivic, allPubmed)
            dicts = returnDicts(gene1, gene2, fusionType)
            
            # Save CIViC output
            if not os.path.exists(civic_path):
                with open(civic_path, "w") as f:
                    json.dump(dicts[0], f, indent=2)
            else:
                print(f"CIViC file exists, skipping")
            
            # PubMed search
            if not os.path.exists(pubmed_path):
                print(dicts[1])
                if fusionType == "" or fusionType is None:
                    searchPubmedFusion(dicts[1], gene1, gene2, cancer_type=cancer_type)
                else:
                    searchPubmedFusion(dicts[1], gene1, gene2, fusionType, cancer_type=cancer_type)
                if os.path.exists("extracted_FrompubmedAndPMC.json"):
                    os.rename("extracted_FrompubmedAndPMC.json", pubmed_path)
            else:
                print(f"PubMed file exists, skipping")
        else:
            print(f"CIViC and PubMed files exist, skipping")
    else:
        print("This type of change is not supported")
