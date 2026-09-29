import requests
import json
import xml.etree.ElementTree as ET
import os
import re
import pandas as pd
from HelperScripts.convertProteinCode import convertProteinCode
from HelperScripts.allVar import convert_any_variant



def runCivicQuery(gene, pChange, allPubmed, civicOut):
    print("-"*80)
    print("Searching Civic")
    print("-"*80)

    url = 'https://civicdb.org/api/graphql'
    #first getting the gene info to check for variants

    query = """
    query searchVariant($name: String!) {
    variants(name: $name) {
        edges {
        node {
            id
            name
            link
            variantAliases
            feature {
                name
            }
        }
        }
    }
    }
    """

    def run_query(query, variables):
        response = requests.post(url, json={"query": query, "variables": variables})
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Query failed with status code {response.status_code}\n{response.text}")

    allVarListQ = []
    if(pChange != 'amplification' and pChange != 'deletion'):
        allVar = convert_any_variant(pChange)
        for item in allVar:
            item2 = allVar[item]
            if "p." in item2:
                continue
            else:
                allVarListQ.append(item2)
    else:
        allVarListQ = ["amplification", "gain"] if pChange == "amplification" else ["deletion", "loss"]
    
    
    
    allRes = []
    for var in allVarListQ:
        variables = {"name": var}

        result = run_query(query, variables)
        print(result)
        data = result.get("data", {}).get("variants", {}).get("edges", [])
        if(len(data) > 0):
            allRes.append(data)
    
    ids = []
    for res in allRes:
        for subRes in res:
            node = subRes["node"]
            print(f"id:{node['id']}")
            print(f"Variant: {node['name']}")
            print(f"Link: {node['link']}")
            print(f"Gene: {node['feature']['name']}")
            print(f"Aliases: {node.get('variantAliases')}")
            print("-" * 40)
            if node['feature']['name'] == gene:
                ids.append(node['id'])
   
    ids = list(set(ids))

    if len(ids) == 0:
        print("No variants found for the given gene in Civic")
        return ({"message": "No variants found for the given gene in Civic"}, allPubmed)

    # GraphQL query for variant details
    query = """
    query getEvidenceFromVariant($id: Int!) {
    variant(id: $id) {
        id
        name
        variantTypes {
                description
                id
                name
                soid
                link
                url
            }
        molecularProfiles {
            edges {
            node {
                id
                name
                evidenceItems {
                edges {
                    node {
                    id
                    evidenceDirection
                    evidenceType
                    evidenceLevel
                    evidenceRating
                    significance
                    variantOrigin
                    therapyInteractionType
                    status
                    therapies {
                        deprecated
                        id
                        link
                        name
                        ncitId
                        therapyAliases
                        therapyUrl
                    }
                    source {
                            title
                            abstract
                            citation
                            citationId
                            clinicalTrials {
                                id
                                link
                                description
                                name
                                url
                            }
                            id
                            title
                            openAccess
                            pmcId
                            publicationYear
                            sourceUrl
                            sourceType
                        }
                    }
                }
                }
            }
            }
        }
    }
    }
    """

    # Replace with the actual variant ID
    variant_id = ids[0]

    variables = {"id": variant_id}


    # Function to execute the query
    def run_query(query, variables):
        response = requests.post(url, json={"query": query, "variables": variables})
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Query failed with code {response.status_code}: {response.text}")

    # Run the query
    variant_data = run_query(query, variables)

    def print_variant_info(data):
        variantInfo = {}
#        supportingEvidence = {}
        allEvidence = []
        print(data)
        variant = data['data']['variant']
        variantInfo["name"] = variant['name']
        print(f"\nVariant: {variant['name']}")
        for vtype in variant['variantTypes']:
            print(f"  • Type: {vtype['name']}")
            variantInfo["type"] = vtype['name']
            print(f"    Description: {vtype['description']}")
            variantInfo["Description"] = vtype['description']
            print(f"    SO ID: {vtype['soid']} ({vtype['url']})")
            variantInfo["SOID"] = vtype['soid']
            variantInfo["soidURL"] = vtype['url']
            
        civicOut["variantInfo"] = variantInfo

        profile = variant['molecularProfiles']['edges'][0]['node']
        print(f"\nMolecular Profile: {profile['name']}")
        
        civicOut["molecularProfile"] = profile['name']
        
        print("\nSupporting Evidence:")
        for idx, edge in enumerate(profile['evidenceItems']['edges'], start=1):
            supportingEvidence = {}
            node = edge['node']
            if len(node['therapies']) != 0:
                therapy = node['therapies'][0]
            else:
                therapy = None
            source = node['source']
            print(f"\n--- Evidence #{idx} ---")
            supportingEvidence["id"] = idx
            print(f"• Evidence Type: {node['evidenceType']}")
            supportingEvidence['evidenceType'] = node['evidenceType']
            print(f"• Significance: {node['significance']}")
            supportingEvidence['significance'] = node['significance']
            print(f"• Level: {node['evidenceLevel']}")
            supportingEvidence['evidenceLevel'] = node['evidenceLevel']
            if 'evidenceRating' in node:
                print(f"• Rating: {node.get('evidenceRating', 'N/A')}")
                supportingEvidence['evidenceRating'] = node['evidenceRating']
            print(f"• Variant Origin: {node['variantOrigin']}")
            supportingEvidence['variantOrigin'] = node['variantOrigin']
            if therapy is not None:
                print(f"• Therapy: {therapy['name']} ({therapy['therapyUrl']})")
                supportingEvidence['therapyName'] = therapy['name']
                supportingEvidence['therapyUrl'] = therapy['therapyUrl']
                print(f"  - Alias: {therapy['therapyAliases']}")
                supportingEvidence['therapyAliases'] = therapy['therapyAliases']

            print(f"• Source: {source['title']}")
            supportingEvidence['sourceTitle'] = source['title']
            print(f"  - Citation: {source['citation']}")
            supportingEvidence['sourceCitation'] = source['citation']
            print(f"  - PMID: {source['citationId']} ({source['sourceUrl']})")
            supportingEvidence['sourceCitationId'] = source['citationId']
            supportingEvidence['sourceCitationUrl'] = source['sourceUrl']
            print(f"  - Open Access: {'Yes' if source['openAccess'] else 'No'}")
            supportingEvidence['openAccess'] = source['openAccess']
            allEvidence.append(supportingEvidence)
            allPubmed.append(source['citationId'])

        civicOut["allEvidences"] = allEvidence
        return(civicOut)

    resCivic = print_variant_info(variant_data)
    return (resCivic, allPubmed)