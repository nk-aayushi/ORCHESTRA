"""
Claude Batch Benchmark: Compare Claude models against MOAlmanac truth set.

Uses the EXACT same prompt as baseline_chatgpt_test.py, submitted via
AWS Bedrock Batch Inference for 3 Claude models:
- Claude Opus 4.5
- Claude Opus 4
- Claude Sonnet 4

Steps:
1. Generate JSONL batch input files (one per model, same prompts)
2. Create S3 bucket and upload inputs
3. Submit batch inference jobs
4. (After completion) Parse results

Usage:
    python claude_batch_benchmark.py --generate     # Generate JSONL + upload to S3
    python claude_batch_benchmark.py --submit       # Submit batch jobs
    python claude_batch_benchmark.py --status       # Check job status
    python claude_batch_benchmark.py --parse        # Parse results into CSV
"""

import csv
import json
import os
import sys
import time

import boto3

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_CSV = os.path.join(BASE_DIR, "batch_results_comparison.csv")
BATCH_INPUT_DIR = os.path.join(BASE_DIR, "claude_batch", "batch_input")
BATCH_OUTPUT_DIR = os.path.join(BASE_DIR, "claude_batch", "batch_output")

S3_BUCKET = "orchestra-claude-benchmark"
S3_PREFIX = "claude_therapy_benchmark"
AWS_REGION = "us-east-1"
SERVICE_ROLE_ARN = "arn:aws:iam::<YOUR_AWS_ACCOUNT_ID>:role/NCCNPdfParse"

MODELS = {
    "claude-opus-4.5": "global.anthropic.claude-opus-4-5-20251101-v1:0",
    "claude-sonnet-4": "global.anthropic.claude-sonnet-4-6",
}

# Exact same prompt from baseline_chatgpt_test.py
PROMPT_TEMPLATE = (
    "For the variant {gene} {protein_change} in {cancer_type}, "
    "what are the recommended targeted therapies or treatments? "
    "For each therapy, include the level of evidence in brackets "
    "(e.g. Level 1, Level 2, Level 3, Level 4) based on FDA approval, "
    "clinical guidelines, and clinical evidence strength. "
    "First provide a detailed explanation, then on the last line write "
    "'THERAPIES: ' followed by a comma-separated list of therapy names "
    "each with their level in brackets, e.g. 'DrugA (Level 1), DrugB (Level 3)'."
)


def get_unique_variants():
    """Read input CSV and get unique (Gene, Protein_Change, Cancer Type) tuples."""
    with open(INPUT_CSV, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    seen = set()
    unique = []
    for r in rows:
        key = (r["Gene"], r["Protein_Change"], r["Cancer Type"])
        if key not in seen:
            seen.add(key)
            unique.append(key)
    return unique, rows


def generate_jsonl():
    """Generate JSONL batch input files for all 3 Claude models."""
    unique_variants, _ = get_unique_variants()
    print(f"Generating batch inputs for {len(unique_variants)} unique variants across {len(MODELS)} models")

    os.makedirs(BATCH_INPUT_DIR, exist_ok=True)

    for model_name, model_id in MODELS.items():
        jsonl_path = os.path.join(BATCH_INPUT_DIR, f"{model_name}.jsonl")
        with open(jsonl_path, "w") as f:
            for gene, pchange, cancer in unique_variants:
                prompt = PROMPT_TEMPLATE.format(
                    gene=gene, protein_change=pchange, cancer_type=cancer
                )
                record_id = f"{gene}_{pchange}_{cancer}".replace(" ", "_").replace(",", "").replace("/", "-")

                record = {
                    "recordId": record_id,
                    "modelInput": {
                        "anthropic_version": "bedrock-2023-05-31",
                        "max_tokens": 4000,
                        "temperature": 0,
                        "messages": [
                            {"role": "user", "content": [{"type": "text", "text": prompt}]}
                        ]
                    }
                }
                f.write(json.dumps(record) + "\n")

            # Pad to 100 records minimum (Bedrock batch requirement)
            total = len(unique_variants)
            if total < 100:
                for idx in range(100 - total):
                    gene, pchange, cancer = unique_variants[idx]
                    prompt = PROMPT_TEMPLATE.format(
                        gene=gene, protein_change=pchange, cancer_type=cancer
                    )
                    record_id = f"pad_{idx}_{gene}_{pchange}_{cancer}".replace(" ", "_").replace(",", "").replace("/", "-")
                    record = {
                        "recordId": record_id,
                        "modelInput": {
                            "anthropic_version": "bedrock-2023-05-31",
                            "max_tokens": 4000,
                            "temperature": 0,
                            "messages": [
                                {"role": "user", "content": [{"type": "text", "text": prompt}]}
                            ]
                        }
                    }
                    f.write(json.dumps(record) + "\n")
                total = 100

        print(f"  Written: {jsonl_path} ({total} records)")


def create_bucket_and_upload():
    """Create S3 bucket and upload JSONL files."""
    s3 = boto3.client("s3", region_name=AWS_REGION)

    # Create bucket
    try:
        s3.head_bucket(Bucket=S3_BUCKET)
        print(f"Bucket {S3_BUCKET} already exists")
    except:
        print(f"Creating bucket: {S3_BUCKET}")
        s3.create_bucket(Bucket=S3_BUCKET)

    # Upload JSONL files
    for model_name in MODELS:
        local_path = os.path.join(BATCH_INPUT_DIR, f"{model_name}.jsonl")
        s3_key = f"{S3_PREFIX}/input/{model_name}.jsonl"
        print(f"  Uploading: s3://{S3_BUCKET}/{s3_key}")
        s3.upload_file(local_path, S3_BUCKET, s3_key)

    print("\nAll files uploaded successfully.")


def submit_batch_jobs():
    """Submit batch inference jobs for all 3 models."""
    bedrock = boto3.client("bedrock", region_name=AWS_REGION)

    job_ids = {}
    for model_name, model_id in MODELS.items():
        input_uri = f"s3://{S3_BUCKET}/{S3_PREFIX}/input/{model_name}.jsonl"
        output_uri = f"s3://{S3_BUCKET}/{S3_PREFIX}/output/{model_name}/"
        job_name = f"orchestra-benchmark-{model_name}-{int(time.time())}"

        print(f"\nSubmitting: {model_name}")
        print(f"  Model: {model_id}")
        print(f"  Input: {input_uri}")
        print(f"  Output: {output_uri}")

        try:
            response = bedrock.create_model_invocation_job(
                jobName=job_name,
                modelId=model_id,
                roleArn=SERVICE_ROLE_ARN,
                inputDataConfig={
                    "s3InputDataConfig": {
                        "s3Uri": input_uri,
                        "s3InputFormat": "JSONL"
                    }
                },
                outputDataConfig={
                    "s3OutputDataConfig": {
                        "s3Uri": output_uri
                    }
                }
            )
            job_id = response["jobArn"]
            job_ids[model_name] = job_id
            print(f"  Job ARN: {job_id}")
        except Exception as e:
            print(f"  ERROR: {e}")

    # Save job IDs
    jobs_file = os.path.join(BASE_DIR, "claude_batch", "job_ids.json")
    with open(jobs_file, "w") as f:
        json.dump(job_ids, f, indent=2)
    print(f"\nJob IDs saved to: {jobs_file}")


def check_status():
    """Check status of submitted batch jobs."""
    bedrock = boto3.client("bedrock", region_name=AWS_REGION)
    jobs_file = os.path.join(BASE_DIR, "claude_batch", "job_ids.json")

    if not os.path.exists(jobs_file):
        print("No jobs submitted yet. Run --submit first.")
        return

    with open(jobs_file) as f:
        job_ids = json.load(f)

    print("Batch Job Status:")
    print("=" * 60)
    for model_name, job_arn in job_ids.items():
        try:
            response = bedrock.get_model_invocation_job(jobIdentifier=job_arn)
            status = response["status"]
            print(f"  {model_name}: {status}")
            if status == "Failed":
                print(f"    Reason: {response.get('message', 'Unknown')}")
        except Exception as e:
            print(f"  {model_name}: ERROR - {e}")


def parse_results():
    """Download and parse batch inference results into CSV."""
    s3 = boto3.client("s3", region_name=AWS_REGION)
    unique_variants, all_rows = get_unique_variants()

    # Build truth set lookup
    truth_data = {}
    for r in all_rows:
        key = (r["Gene"], r["Protein_Change"], r["Cancer Type"])
        if key not in truth_data:
            truth_data[key] = {"therapies": set(), "our_therapies": r["Our_Therapies"]}
        for t in r["Therapies"].split(","):
            t = t.strip()
            if t:
                truth_data[key]["therapies"].add(t)

    # Parse each model's output
    results = {model: {} for model in MODELS}

    for model_name in MODELS:
        output_prefix = f"{S3_PREFIX}/output/{model_name}/"
        # List objects in output
        try:
            resp = s3.list_objects_v2(Bucket=S3_BUCKET, Prefix=output_prefix)
            for obj in resp.get("Contents", []):
                key = obj["Key"]
                if key.endswith(".jsonl.out") or key.endswith(".jsonl"):
                    # Download
                    local_out = os.path.join(BATCH_OUTPUT_DIR, f"{model_name}.jsonl.out")
                    os.makedirs(BATCH_OUTPUT_DIR, exist_ok=True)
                    s3.download_file(S3_BUCKET, key, local_out)
                    print(f"Downloaded: {key}")

                    # Parse
                    with open(local_out) as f:
                        for line in f:
                            try:
                                data = json.loads(line.strip())
                                record_id = data.get("recordId", "")
                                output = data.get("modelOutput", {})
                                content = output.get("content", [])
                                text = content[0].get("text", "") if content else ""
                                results[model_name][record_id] = text
                            except:
                                continue
                    print(f"  Parsed {len(results[model_name])} records for {model_name}")
        except Exception as e:
            print(f"  Error fetching {model_name} results: {e}")

    # Extract therapy lines and build output CSV
    def extract_therapy_list(response_text):
        for line in reversed(response_text.splitlines()):
            if line.strip().upper().startswith("THERAPIES:"):
                return line.split(":", 1)[1].strip()
        return ""

    output_rows = []
    for gene, pchange, cancer in unique_variants:
        record_id = f"{gene}_{pchange}_{cancer}".replace(" ", "_").replace(",", "").replace("/", "-")
        truth = truth_data.get((gene, pchange, cancer), {})

        row = {
            "Gene": gene,
            "Protein_Change": pchange,
            "Cancer_Type": cancer,
            "MOAlmanac_Therapies": ", ".join(sorted(truth.get("therapies", set()))),
            "ORCHESTRA_Therapies": truth.get("our_therapies", ""),
        }

        for model_name in MODELS:
            response = results[model_name].get(record_id, "")
            therapies = extract_therapy_list(response)
            row[f"{model_name}_Therapies"] = therapies
            row[f"{model_name}_Detailed"] = response

        output_rows.append(row)

    # Write CSV
    output_csv = os.path.join(BASE_DIR, "claude_batch", "claude_benchmark_results.csv")
    fieldnames = ["Gene", "Protein_Change", "Cancer_Type", "MOAlmanac_Therapies", "ORCHESTRA_Therapies"]
    for model_name in MODELS:
        fieldnames.extend([f"{model_name}_Therapies", f"{model_name}_Detailed"])

    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(output_rows)

    print(f"\nResults saved to: {output_csv}")
    print(f"Total variants: {len(output_rows)}")


def update_iam_policy():
    """Print the IAM policy that needs to be attached to NCCNPdfParse role."""
    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": ["s3:GetObject", "s3:PutObject", "s3:ListBucket"],
                "Resource": [
                    f"arn:aws:s3:::{S3_BUCKET}",
                    f"arn:aws:s3:::{S3_BUCKET}/*"
                ],
                "Condition": {
                    "StringEquals": {"aws:ResourceAccount": "<YOUR_AWS_ACCOUNT_ID>"}
                }
            },
            {
                "Effect": "Allow",
                "Action": ["bedrock:InvokeModel"],
                "Resource": [
                    "arn:aws:bedrock:us-east-1:<YOUR_AWS_ACCOUNT_ID>:inference-profile/global.anthropic.claude-opus-4-5-20251101-v1:0",
                    "arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-opus-4-5-20251101-v1:0",
                    "arn:aws:bedrock:us-east-2::foundation-model/anthropic.claude-opus-4-5-20251101-v1:0",
                    "arn:aws:bedrock:us-west-2::foundation-model/anthropic.claude-opus-4-5-20251101-v1:0",
                    "arn:aws:bedrock:us-east-1:<YOUR_AWS_ACCOUNT_ID>:inference-profile/global.anthropic.claude-opus-4-8",
                    "arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-opus-4-8",
                    "arn:aws:bedrock:us-east-2::foundation-model/anthropic.claude-opus-4-8",
                    "arn:aws:bedrock:us-west-2::foundation-model/anthropic.claude-opus-4-8",
                    "arn:aws:bedrock:us-east-1:<YOUR_AWS_ACCOUNT_ID>:inference-profile/global.anthropic.claude-sonnet-4-6",
                    "arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-sonnet-4-6",
                    "arn:aws:bedrock:us-east-2::foundation-model/anthropic.claude-sonnet-4-6",
                    "arn:aws:bedrock:us-west-2::foundation-model/anthropic.claude-sonnet-4-6"
                ]
            }
        ]
    }

    policy_path = os.path.join(BASE_DIR, "claude_batch", "iam_policy.json")
    with open(policy_path, "w") as f:
        json.dump(policy, f, indent=2)

    print(f"IAM policy saved to: {policy_path}")
    print(f"\nAttach this policy to the NCCNPdfParse role:")
    print(f"  aws iam put-role-policy \\")
    print(f"    --role-name NCCNPdfParse \\")
    print(f"    --policy-name OrchestraClaude BenchmarkAccess \\")
    print(f"    --policy-document file://{policy_path}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python claude_batch_benchmark.py --generate   # Generate JSONL + create S3 bucket + upload")
        print("  python claude_batch_benchmark.py --submit     # Submit batch jobs")
        print("  python claude_batch_benchmark.py --status     # Check job status")
        print("  python claude_batch_benchmark.py --parse      # Parse results into CSV")
        print("  python claude_batch_benchmark.py --policy     # Generate IAM policy for the role")
        sys.exit(1)

    flag = sys.argv[1]
    if flag == "--generate":
        generate_jsonl()
        create_bucket_and_upload()
    elif flag == "--submit":
        submit_batch_jobs()
    elif flag == "--status":
        check_status()
    elif flag == "--parse":
        parse_results()
    elif flag == "--policy":
        update_iam_policy()
    else:
        print(f"Unknown flag: {flag}")
        sys.exit(1)
