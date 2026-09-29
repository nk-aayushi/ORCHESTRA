"""
variant_normalization.py
------------------------
Reference module documenting all variant normalization steps used in ORCHESTRA.

This file re-exports the key normalization functions from helper_scripts/ and
documents the exact logic applied before querying each database.

For full implementations see:
  helper_scripts/allVar.py          -- protein change format conversion
  helper_scripts/allCChange.py      -- coding change format conversion
  helper_scripts/mutalyzer.py       -- DNA <-> protein via Mutalyzer API
  helper_scripts/convertProteinCode.py -- 3-letter to 1-letter amino acid
"""

# ── Imports ────────────────────────────────────────────────────────────────────
from helper_scripts.allVar import convert_any_variant
from helper_scripts.allCChange import convertCChange
from helper_scripts.mutalyzer import dnaToProtein, proteinToDNA
from helper_scripts.convertProteinCode import convertProteinCode


# ── Protein change normalization ───────────────────────────────────────────────
def get_all_protein_formats(protein_change: str) -> dict:
    """
    Given any protein change string, return all equivalent representations.

    Input examples:
        "p.L858R", "L858R", "p.Leu858Arg", "p.Glu709_Thr710delinsAsp"

    Output keys (vary by variant type):
        Substitution:
            HGVS_3letter  e.g. "p.Leu858Arg"
            1L            e.g. "L858R"
            arrow         e.g. "L858R>"
            p_style       e.g. "p.L858R"

        Deletion:
            HGVS_3letter, 1L_range, p_style_range  (range deletion)
            HGVS_3letter, 1L, p_style               (single residue)

        Delins:
            HGVS_3letter, 1L_format, 1L_short, delins_named, sub_style, p_style_short

        Frameshift:
            Multiple HGVS and 1-letter forms with Ter/* notation

    All returned formats are submitted as separate search queries to ClinVar
    and CIViC to maximise recall across databases that use inconsistent notation.
    """
    return convert_any_variant(protein_change)


# ── Coding change normalization ────────────────────────────────────────────────
def get_all_coding_formats(coding_change: str) -> list:
    """
    Given a coding change string, return equivalent HGVS representations.

    Input example: "c.2573T>G"
    Output: list of equivalent coding change strings tried against ClinVar.
    """
    return convertCChange(coding_change)


# ── DNA <-> Protein conversion via Mutalyzer ──────────────────────────────────
def coding_to_protein(gene: str, c_change: str) -> str | None:
    """
    Convert a coding change to protein change using Mutalyzer normalize API.

    Uses MANE Select v1.5 reference transcripts (GRCh38).
    Returns None if Mutalyzer normalization fails.

    Example:
        coding_to_protein("EGFR", "c.2573T>G") -> "p.Leu858Arg"
    """
    return dnaToProtein(gene, c_change)


def protein_to_coding(gene: str, p_change: str) -> str | None:
    """
    Back-translate a protein change to a coding change using Mutalyzer.

    Note: back-translation is not unique (multiple codons can encode the same
    amino acid). Mutalyzer returns one representative coding change.
    Returns None if normalization fails.

    Example:
        protein_to_coding("EGFR", "p.L858R") -> "c.2573T>G"
    """
    return proteinToDNA(gene, p_change)


# ── CNV normalization ──────────────────────────────────────────────────────────
def normalize_cnv_type(cnv_type: str) -> str:
    """
    Normalize CNV type strings to canonical form.

    Mapping:
        "gain", "amplification", "duplication"  ->  "amplification"
        "loss", "deletion"                       ->  "deletion"

    Raises ValueError for unrecognized types.
    """
    cnv_lower = cnv_type.lower()
    if cnv_lower in ("gain", "amplification", "duplication"):
        return "amplification"
    elif cnv_lower in ("loss", "deletion"):
        return "deletion"
    else:
        raise ValueError(f"Unrecognized CNV type: {cnv_type!r}")


# ── Fusion notation ────────────────────────────────────────────────────────────
def get_fusion_query_term(gene1: str, gene2: str, fusion_name: str = None) -> str:
    """
    Build the fusion query term used in PubMed and CIViC searches.

    Uses HGVS fusion notation: GENE1::GENE2
    Appends fusion_name if provided.

    Example:
        get_fusion_query_term("EML4", "ALK", "EML4-ALK") -> "EML4::ALK EML4-ALK"
    """
    term = f"{gene1}::{gene2}"
    if fusion_name:
        term += f" {fusion_name}"
    return term
