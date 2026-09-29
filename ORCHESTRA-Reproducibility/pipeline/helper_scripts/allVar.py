from Bio.Data import IUPACData
import re

# Build AA maps
three_to_one = {k.capitalize(): v for k, v in IUPACData.protein_letters_3to1.items()}
one_to_three = {v: k for k, v in three_to_one.items()}

def parse_variant_general(variant):
    """Parse variant into structured (type, details)"""
    variant = variant.strip().replace("p.", "")
    
    # Handle Ter (termination codon) - convert to *
    variant = variant.replace("Ter", "*")

    # --- Substitution ---
    # Three letter to stop codon
    m = re.match(r"([A-Z][a-z]{2})(\d+)\*$", variant)
    if m:
        ref3, pos = m.groups()
        return ("substitution", (three_to_one[ref3], pos, "*"))
    
    m = re.match(r"([A-Z][a-z]{2})(\d+)([A-Z][a-z]{2})$", variant)
    if m:
        ref3, pos, alt3 = m.groups()
        return ("substitution", (three_to_one[ref3], pos, three_to_one[alt3]))

    m = re.match(r"([A-Z])(\d+)([A-Z*])$", variant)
    if m:
        return ("substitution", m.groups())

    m = re.match(r"([A-Z])(\d+)>[A-Z*]", variant)
    if m:
        ref, pos = m.groups()
        alt = variant.split(">")[1]
        return ("substitution", (ref, pos, alt))
    
    # --- frameshift ---
    m = re.match(r"([A-Z])(\d+)([A-Z])fs\*(\d*)$", variant)
    if m:
        ref1, pos, alt1, stop = m.groups()
        return ("frameshift", (ref1, pos, alt1, stop))
    
    m = re.match(r"([A-Z][a-z]{2})(\d+)([A-Z][a-z]{2})fs\*(\d*)$", variant) 
    if m:
        ref1, pos, alt1, stop = m.groups()
        return ("frameshift", (three_to_one[ref1], pos, three_to_one[alt1], stop))

    m = re.match(r"([A-Z])(\d+)fs$", variant)
    if m:
        ref1, pos = m.groups()
        return ("frameshift_2", (ref1, pos))
    
    m = re.match(r"([A-Z][a-z]{2})(\d+)fs$", variant)
    if m:
        ref1, pos = m.groups()
        return ("frameshift_2", (three_to_one[ref1], pos))
    # --- delins ---
    m = re.match(r"([A-Z][a-z]{2})(\d+)_([A-Z][a-z]{2})(\d+)delins([A-Z][a-z]{2})", variant)
    if m:
        a1, p1, a2, p2, ins = m.groups()
        return ("delins", (three_to_one[a1], p1, three_to_one[a2], p2, three_to_one[ins]))

    m = re.match(r"([A-Z])(\d+)_([A-Z])(\d+)delins([A-Z])", variant)
    if m:
        return ("delins", m.groups())

    m = re.match(r"del([A-Z])(\d+)_([A-Z])(\d+)ins([A-Z])", variant)
    if m:
        return ("delins", m.groups())

    m = re.match(r"([A-Z])(\d+)([A-Z])(\d+)>[A-Z]", variant)
    if m:
        aa1, p1, aa2, p2 = m.groups()
        ins = variant.split(">")[1]
        return ("delins", (aa1, p1, aa2, p2, ins))

    # --- Insertion ---
    m = re.match(r"([A-Z][a-z]{2})(\d+)_([A-Z][a-z]{2})(\d+)ins([A-Z][a-z]{2})", variant)
    if m:
        a1, p1, a2, p2, ins = m.groups()
        return ("insertion", (three_to_one[a1], p1, three_to_one[a2], p2, three_to_one[ins]))

    m = re.match(r"([A-Z])(\d+)_([A-Z])(\d+)ins([A-Z])", variant)
    if m:
        return ("insertion", m.groups())

    # --- Simple Deletion ---
    m = re.match(r"([A-Z][a-z]{2})(\d+)del$", variant)
    if m:
        aa3, pos = m.groups()
        return ("deletion", (three_to_one[aa3], pos, None, None))

    m = re.match(r"([A-Z])(\d+)del$", variant)
    if m:
        return ("deletion", (m.group(1), m.group(2), None, None))

    m = re.match(r"([A-Z])(\d+)_([A-Z])(\d+)del$", variant)
    if m:
        return ("deletion", (m.group(1), m.group(2), m.group(3), m.group(4)))

    m = re.match(r"([A-Z][a-z]{2})(\d+)_([A-Z][a-z]{2})(\d+)del$", variant)
    if m:
        a1, p1, a2, p2 = m.groups()
        return ("deletion", (three_to_one[a1], p1, three_to_one[a2], p2))

    raise ValueError(f"Unrecognized variant format: {variant}")

def convert_variant_to_all_formats(var_type, data):
    """Convert parsed variant to equivalent formats"""
    if var_type == "substitution":
        ref, pos, alt = data
        # Handle * (stop codon) - don't convert to three letter
        if alt == "*":
            return {
                "HGVS_3letter": f"p.{one_to_three.get(ref, ref)}{pos}Ter",
                "1L": f"{ref}{pos}*",
                "arrow": f"{ref}{pos}>*",
                "p_style": f"p.{ref}{pos}*"
            }
        elif ref == "*":
            return {
                "HGVS_3letter": f"p.Ter{pos}{one_to_three.get(alt, alt)}",
                "1L": f"*{pos}{alt}",
                "arrow": f"*{pos}>{alt}",
                "p_style": f"p.*{pos}{alt}"
            }
        else:
            return {
                "HGVS_3letter": f"p.{one_to_three[ref]}{pos}{one_to_three[alt]}",
                "1L": f"{ref}{pos}{alt}",
                "arrow": f"{ref}{pos}>{alt}",
                "p_style": f"p.{ref}{pos}{alt}"
            }

    elif var_type == "delins":
        a1, p1, a2, p2, ins = data
        return {
            "HGVS_3letter": f"p.{one_to_three[a1]}{p1}_{one_to_three[a2]}{p2}delins{one_to_three[ins]}",
            "1L_format": f"{a1}{p1}_{a2}{p2}delins{ins}",
            "1L_short": f"{a1}{p1}_{a2}{p2}ins{ins}",
            "delins_named": f"del{a1}{p1}_{a2}{p2}ins{ins}",
            "sub_style": f"{a1}{p1}_{a2}{p2}>{ins}",
            "p_style_short": f"p.{a1}{p1}_{a2}{p2}delins{ins}"
        }

    elif var_type == "insertion":
        a1, p1, a2, p2, ins = data
        return {
            "HGVS_3letter": f"p.{one_to_three[a1]}{p1}_{one_to_three[a2]}{p2}ins{one_to_three[ins]}",
            "1L_format": f"{a1}{p1}_{a2}{p2}ins{ins}",
            "p_style_short": f"p.{a1}{p1}_{a2}{p2}ins{ins}"
        }

    elif var_type == "deletion":
        a1, p1, a2, p2 = data
        if a2 and p2:
            return {
                "HGVS_3letter": f"p.{one_to_three[a1]}{p1}_{one_to_three[a2]}{p2}del",
                "1L_range": f"{a1}{p1}_{a2}{p2}del",
                "p_style_range": f"p.{a1}{p1}_{a2}{p2}del"
            }
        else:
            return {
                "HGVS_3letter": f"p.{one_to_three[a1]}{p1}del",
                "1L": f"{a1}{p1}del",
                "p_style": f"p.{a1}{p1}del"
            }
    elif var_type == "frameshift":
        ref, pos, alt, stop = data
        return {
            "HGVS_3letter_with_*_withp": f"p.{one_to_three[ref]}{pos}{one_to_three[alt]}fs*{stop}",
            "HGVS_3letter_with_Ter_withp": f"p.{one_to_three[ref]}{pos}{one_to_three[alt]}fsTer{stop}",
            "1L_with_*_withp": f"p.{ref}{pos}{alt}fs*{stop}",
            "1L_with_Ter_withp": f"p.{ref}{pos}{alt}fsTer{stop}",
            "HGVS_3letter_with_*_withoutp": f"{one_to_three[ref]}{pos}{one_to_three[alt]}fs*{stop}",
            "HGVS_3letter_with_Ter_withoutp": f"{one_to_three[ref]}{pos}{one_to_three[alt]}fsTer{stop}",
            "1L_with_*_withoutp": f"{ref}{pos}{alt}fs*{stop}",
            "1L_with_Ter_withoutp": f"{ref}{pos}{alt}fsTer{stop}",
            "truncation": "truncation"
        }
    elif var_type == "frameshift_2":
        ref, pos = data
        return {
            "HGVS_3letter_with_*_withp": f"p.{one_to_three[ref]}{pos}fs*",
            "HGVS_3letter_with_Ter_withp": f"p.{one_to_three[ref]}{pos}fsTer",
            "1L_with_*_withp": f"p.{ref}{pos}fs*",
            "1L_with_Ter_withp": f"p.{ref}{pos}fsTer",
            "HGVS_3letter_with_*_withoutp": f"{one_to_three[ref]}{pos}fs*",
            "HGVS_3letter_with_Ter_withoutp": f"{one_to_three[ref]}{pos}fsTer",
            "1L_with_*_withoutp": f"{ref}{pos}fs*",
            "1L_with_Ter_withoutp": f"{ref}{pos}fsTer",
            "truncation": "truncation"
        }

def convert_any_variant(variant_string):
    """Main function: input any HGVS string, get alternate formats"""
    var_type, parsed = parse_variant_general(variant_string)
    return convert_variant_to_all_formats(var_type, parsed)