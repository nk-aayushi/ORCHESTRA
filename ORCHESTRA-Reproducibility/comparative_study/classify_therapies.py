import csv
import re

INPUT = 'batch_results_comparison.csv'
OUTPUT = 'batch_results_classified.csv'

def parse_our_therapies(our_therapies_str):
    """Split Our_Therapies into tier1 names and other_tier names."""
    tier1, other_tier = [], []
    if not our_therapies_str or not our_therapies_str.strip():
        return tier1, other_tier
    # Split by comma, each entry is a therapy (possibly with + combos and level)
    for entry in our_therapies_str.split(','):
        entry = entry.strip()
        if not entry:
            continue
        level_match = re.search(r'\(Level\s+\d+\)', entry)
        # Extract just the therapy name(s) without level
        name = re.sub(r'\(Level\s+\d+\)', '', entry).strip()
        # Get individual drug names from combo therapies (split by +)
        drugs = [d.strip().lower() for d in name.split('+') if d.strip()]
        if level_match:
            other_tier.extend(drugs)
        else:
            tier1.extend(drugs)
    return set(tier1), set(other_tier)

def classify_row(therapies_str, our_therapies_str):
    """Classify each therapy word and return category + per-word details."""
    tier1_set, other_set = parse_our_therapies(our_therapies_str)
    if not therapies_str or not therapies_str.strip():
        return 'No Therapies Listed', '', '', ''

    # Split input therapies by comma, then each word individually
    words = [w.strip() for w in therapies_str.split(',') if w.strip()]

    in_tier1, in_other, absent = [], [], []
    for word in words:
        wl = word.lower()
        if wl in tier1_set:
            in_tier1.append(word)
        elif wl in other_set:
            in_other.append(word)
        else:
            absent.append(word)

    # Determine category
    if in_tier1 and not in_other and not absent:
        category = 'All Present as Tier 1'
    elif in_other and not in_tier1 and not absent:
        category = 'All Present as Different Tier'
    elif absent and not in_tier1 and not in_other:
        category = 'All Absent'
    elif not in_tier1 and not in_other and not absent:
        category = 'No Therapies Listed'
    else:
        category = 'Partially Present'

    return category, ', '.join(in_tier1), ', '.join(in_other), ', '.join(absent)

with open(INPUT, newline='', encoding='utf-8') as fin:
    reader = csv.DictReader(fin)
    fieldnames = reader.fieldnames + [
        'Our_Tier1_Therapies', 'Our_Other_Tier_Therapies',
        'Match_Category', 'Matched_Tier1', 'Matched_Other_Tier', 'Not_Found'
    ]
    rows = []
    for row in reader:
        tier1_set, other_set = parse_our_therapies(row.get('Our_Therapies', ''))
        cat, matched_t1, matched_other, not_found = classify_row(
            row.get('Therapies', ''), row.get('Our_Therapies', '')
        )
        row['Our_Tier1_Therapies'] = ', '.join(sorted(tier1_set))
        row['Our_Other_Tier_Therapies'] = ', '.join(sorted(other_set))
        row['Match_Category'] = cat
        row['Matched_Tier1'] = matched_t1
        row['Matched_Other_Tier'] = matched_other
        row['Not_Found'] = not_found
        rows.append(row)

with open(OUTPUT, 'w', newline='', encoding='utf-8') as fout:
    writer = csv.DictWriter(fout, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)

# Print summary
from collections import Counter
cats = Counter(r['Match_Category'] for r in rows)
print(f"Wrote {len(rows)} rows to {OUTPUT}")
print("Category breakdown:")
for cat, count in cats.most_common():
    print(f"  {cat}: {count}")
