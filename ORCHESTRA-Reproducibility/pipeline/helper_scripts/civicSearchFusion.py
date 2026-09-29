import requests
import json
import xml.etree.ElementTree as ET
import os
import re
import pandas as pd
from HelperScripts.convertProteinCode import convertProteinCode
from HelperScripts.allVar import convert_any_variant


def runCivicQueryFusion(gene1, gene2, fusionType, allPubmed, civicOut):
    print("-"*80)
    print("Searching Civic for fusion")
    print("-"*80)

    url = 'https://civicdb.org/api/graphql'

    def search_variants(variant_name):
        query = """
        query browseVariants($featureName: String, $first: Int) {
          browseVariants(featureName: $featureName, first: $first) {
            nodes {
              id
              name
              link
              featureName
              diseases {
                  name
                  id
              }
              therapies {
                  name
                  id
                  link
    
              }
              variantTypes {
                name
              }
            }
            totalCount
          }
        }
        """
        variables = {
            "featureName": variant_name
        }
        response = requests.post(
            url,
            json={"query": query, "variables": variables}
        )
        response.raise_for_status()
        data = response.json()
        return data
    results = search_variants(gene1)

    data = results['data']['browseVariants']['nodes']

    def grainy_search_variants(data, query):
        query = query.lower()
    
        result = []
        for item in data:
            featureName = item.get("featureName", "")
            name = item.get("name", "")
    
            if not isinstance(name, str) or not isinstance(featureName, str):
                continue
    
            if query in name.lower() or query in featureName.lower():
                result.append(item)
        
        return result

    def fine_search_variants(data, query):
        query = query.lower()
        result = []
        for item in data:
            featureName = item.get("featureName", "")
            name = item.get("name", "")
            if not isinstance(name, str) or not isinstance(featureName, str):
                continue
            if query in name.lower() or query in featureName.lower():
                result.append(item)
        return result

    finalResult = fine_search_variants(grainy_search_variants(data, gene1+"::"+gene2), fusionType)
    ids = 0
    for item in finalResult:
        id = item.get('id')
        ids = id

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
    
    variant_id = ids
    
    variables = {"id": variant_id}
    
    def run_query(query, variables):
        response = requests.post(url, json={"query": query, "variables": variables})
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Query failed with code {response.status_code}: {response.text}")
    
    variant_data = run_query(query, variables)

    
    def print_variant_info(data):
        variantInfo = {}
#        supportingEvidence = {}
        allEvidence = []
        variant = data['data']['variant']
        if variant is None:
            return civicOut
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