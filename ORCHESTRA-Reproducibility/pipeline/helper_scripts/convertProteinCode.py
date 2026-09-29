from Bio.Data.IUPACData import protein_letters_3to1
import re

def convertProteinCode(protein_str):
    """
    Converts a protein mutation description from three-letter to one-letter amino acid codes.
    Example: 'p.Glu709_Thr710' -> 'E709_T710'
    """
    # Regex pattern to match three-letter amino acid codes and positions
    pattern1 = r'p\.([A-Z][a-z]{2})(\d+)_([A-Z][a-z]{2})(\d+)'
    pattern2 = r'p\.([A-Z][a-z]{2})(\d+)([A-Z][a-z]{2})'

    match1 = re.search(pattern1, protein_str)
    match2 = re.search(pattern2, protein_str)
    if match1:
        aa1, pos1, aa2, pos2 = match1.groups()
        
        # Convert to one-letter codes
        aa1_one = protein_letters_3to1.get(aa1, aa1)  # Default to original if not found
        aa2_one = protein_letters_3to1.get(aa2, aa2)

        # Return formatted string
        return f"{aa1_one}{pos1}_{aa2_one}{pos2}"
    elif (match2):
        aa1, pos1, aa2 = match2.groups()
        aa1_one = protein_letters_3to1.get(aa1, aa1)  # Default to original if not found
        aa2_one = protein_letters_3to1.get(aa2, aa2)
        return f"{aa1_one}{pos1}{aa2_one}"

    else:
        return "Invalid input format"


# protein_code = "p.Glu709_Thr710"
# converted_code = convertProteinCode(protein_code)
# print(converted_code)