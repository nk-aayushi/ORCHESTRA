import re

def generate_variant_search_terms(hgvs):
    variants = set()
    variants.add(hgvs)

    # SNV
    snv = re.match(r"c\.(\d+)([ACGT])>([ACGT])", hgvs)
    if snv:
        pos, ref, alt = snv.groups()
        variants |= {
            f"c.{pos}{ref}>{alt}",
            f"{ref}{pos}{alt}",
            f"{pos}{ref}>{alt}",
            f"{ref}->{alt} at {pos}",
            f"c.{pos}{ref}/{alt}",
        }

    # Splice SNV
    splice = re.match(r"c\.(\d+)([+-]\d+)([ACGT])>([ACGT])", hgvs)
    if splice:
        base, offset, ref, alt = splice.groups()
        variants |= {
            f"c.{base}{offset}{ref}>{alt}",
            f"{base}{offset}{ref}>{alt}",
            f"splice {ref}>{alt} {base}{offset}",
        }

    # Deletion
    deletion = re.match(r"c\.(\d+)(?:_(\d+))?del([ACGT]*)", hgvs)
    if deletion:
        start, end, seq = deletion.groups()
        end = end or start
        length = len(seq) if seq else int(end) - int(start) + 1

        variants |= {
            f"c.{start}_{end}del",
            f"{start}_{end}del",
            f"del{length}",
            f"deletion {start}-{end}",
        }

    # Insertion
    insertion = re.match(r"c\.(\d+)_(\d+)ins([ACGT]+)", hgvs)
    if insertion:
        start, end, seq = insertion.groups()
        variants |= {
            f"c.{start}_{end}ins{seq}",
            f"{start}_{end}ins{seq}",
            f"ins{seq}",
        }

    # Delins
    delins = re.match(
        r"c\.(\d+)_(\d+)del([ACGT]+)ins([ACGT]+)", hgvs
    )
    if delins:
        start, end, deleted, inserted = delins.groups()
        variants |= {
            f"c.{start}_{end}delins{inserted}",
            f"c.{start}_{end}delins",
            f"del{len(deleted)}ins{inserted}",
            f"{start}_{end}delins{inserted}",
        }

    # Duplication
    dup = re.match(r"c\.(\d+)(?:_(\d+))?dup([ACGT]*)", hgvs)
    if dup:
        start, end, seq = dup.groups()
        end = end or start
        variants |= {
            f"c.{start}_{end}dup",
            f"{start}_{end}dup",
            f"duplication {start}-{end}",
        }
    

    #splice
    splice = re.match(r"c\.(\d+)([+-]\d+)_(\d+)([+-]\d+)del([ACGT]*)$", hgvs)
    if splice:
        pos1, shift1, pos2, shift2, deleted = splice.groups()
        variants |= {
            f"c.{pos1}{shift1}_{pos2}{shift2}del{deleted}",
            f"{pos1}{shift1}_{pos2}{shift2}del{deleted}", 
            f"c.{pos1}{shift1}_{pos2}{shift2}del",
            f"{pos1}{shift1}_{pos2}{shift2}del"
        }

    splice = re.match(r"c\.(\d+)([+-]\d+)([ATCG]+)>([ATCG]+)$", hgvs)
    if splice:
        pos, shift, ref, alt = splice.groups()
        variants |= {
            f"c.{pos}{shift}{ref}>{alt}",
            f"{pos}{shift}{ref}>{alt}" 
        }
    
    #promoter
    #c.-146C>T
    promoter = re.match(r"c\.(-\d+)([ACGT]+)>([ACGT]+)$", hgvs)
    if promoter:
        pos, ref, alt = promoter.groups()
        variants |= {
            f"c.{pos}{ref}>{alt}",
            f"{pos}{ref}>{alt}"
        }

    promoter = re.match(r"c\.(-\d+)del$", hgvs)
    if promoter:
        pos = promoter.groups()
        variants |= {
            f"c.{pos}del",
            f"{pos}del"
        }

    #c.-57_ -56insA
    promoter = re.match(r"c\.(-\d+)_(-\d+)ins([ACTG]+)$", hgvs)
    if promoter:
        pos1, pos2, insert = promoter.groups()
        variants |= {
            f"c.{pos1}_{pos2}ins{insert}",
            f"{pos1}_{pos2}ins{insert}" 
        }

    return sorted(v for v in variants if v)
        
def convertCChange(cChange):
    return generate_variant_search_terms(cChange)
