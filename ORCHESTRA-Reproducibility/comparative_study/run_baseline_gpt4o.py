import csv
import time
from openai import OpenAI

# ===== INSERT YOUR API KEY HERE =====
API_KEY = "<YOUR_OPENAI_API_KEY>"
MODEL = "gpt-4o"
# =====================================

INPUT_CSV = "batch_results_comparison.csv"
OUTPUT_CSV = "baseline_chatgpt_results.csv"
TRIAL_LIMIT = None  # Set to None to run all 98 unique entries

client = OpenAI(api_key=API_KEY)

def query_chatgpt(gene, protein_change, cancer_type):
    prompt = (
        f"For the variant {gene} {protein_change} in {cancer_type}, "
        f"what are the recommended targeted therapies or treatments? "
        f"For each therapy, include the level of evidence in brackets "
        f"(e.g. Level 1, Level 2, Level 3, Level 4) based on FDA approval, "
        f"clinical guidelines, and clinical evidence strength. "
        f"First provide a detailed explanation, then on the last line write "
        f"'THERAPIES: ' followed by a comma-separated list of therapy names "
        f"each with their level in brackets, e.g. 'DrugA (Level 1), DrugB (Level 3)'."
    )
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
    )
    return resp.choices[0].message.content.strip()

# Read all rows
with open(INPUT_CSV, newline="", encoding="utf-8") as f:
    rows = list(csv.DictReader(f))

# Get unique (Gene, Protein_Change, Cancer Type) combos preserving order
seen = set()
unique_keys = []
for r in rows:
    key = (r["Gene"], r["Protein_Change"], r["Cancer Type"])
    if key not in seen:
        seen.add(key)
        unique_keys.append(key)

if TRIAL_LIMIT:
    unique_keys = unique_keys[:TRIAL_LIMIT]

print(f"Querying ChatGPT for {len(unique_keys)} unique variants...")

# Query ChatGPT for each unique variant
gpt_results = {}
for i, (gene, pchange, cancer) in enumerate(unique_keys):
    print(f"[{i+1}/{len(unique_keys)}] {gene} {pchange} — {cancer}")
    try:
        answer = query_chatgpt(gene, pchange, cancer)
    except Exception as e:
        print(f"  ERROR: {e}")
        answer = f"ERROR: {e}"
    gpt_results[(gene, pchange, cancer)] = answer
    time.sleep(1)  # rate limit buffer

# Parse the one-line therapy list from the response
def extract_therapy_list(response_text):
    for line in reversed(response_text.splitlines()):
        if line.strip().upper().startswith("THERAPIES:"):
            return line.split(":", 1)[1].strip()
    return ""

# Build a lookup: unique key -> merged Therapies and Our_Therapies from all rows
key_data = {}
for r in rows:
    key = (r["Gene"], r["Protein_Change"], r["Cancer Type"])
    if key not in key_data:
        key_data[key] = {"therapies": set(), "our_therapies": r["Our_Therapies"]}
    for t in r["Therapies"].split(","):
        t = t.strip()
        if t:
            key_data[key]["therapies"].add(t)

# Write clean output — one row per unique variant
clean_fields = [
    "Gene", "Protein_Change", "Cancer Type",
    "Therapies", "Our_Therapies",
    "ChatGPT_Therapies", "ChatGPT_Detailed"
]

clean_rows = []
for key in unique_keys:
    full_resp = gpt_results[key]
    d = key_data[key]
    clean_rows.append({
        "Gene": key[0],
        "Protein_Change": key[1],
        "Cancer Type": key[2],
        "Therapies": ", ".join(sorted(d["therapies"])),
        "Our_Therapies": d["our_therapies"],
        "ChatGPT_Therapies": extract_therapy_list(full_resp),
        "ChatGPT_Detailed": full_resp,
    })

with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=clean_fields)
    writer.writeheader()
    writer.writerows(clean_rows)

print(f"\nDone! Wrote {len(clean_rows)} rows to {OUTPUT_CSV} (one per unique variant)")
