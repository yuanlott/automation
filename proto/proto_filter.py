import argparse
import re
import sys

def parse_args():
    parser = argparse.ArgumentParser(
        description="Filter a textproto file by relationship kinds."
    )
    parser.add_argument("-i", "--input", required=True, help="Input textproto file")
    parser.add_argument(
        "-r", "--relationships",
        required=True,
        help="Comma-separated list of relationship kinds to keep, e.g. RK_CONTAINS,RK_CONTROLS"
    )
    parser.add_argument("-o", "--output", required=True, help="Output filtered textproto file")
    return parser.parse_args()

def read_blocks(text):
    """
    Split the file into top-level 'entity: { ... }' or 'relationship: { ... }' blocks.
    """
    pattern = re.compile(r'(?=^\s*(entity|relationship)\s*:\s*\{)', re.MULTILINE)
    indices = [m.start() for m in pattern.finditer(text)]
    blocks = []

    if not indices:
        return blocks

    for i, start in enumerate(indices):
        end = indices[i + 1] if i + 1 < len(indices) else len(text)
        blocks.append(text[start:end].strip())
    return blocks

def extract_relationship_kind(block):
    match = re.search(r'kind\s*:\s*(RK_\w+)', block)
    return match.group(1) if match else None

def extract_entity_id(block):
    match = re.search(r'id\s*:\s*"([^"]+)"', block)
    return match.group(1) if match else None

def extract_relationship_endpoints(block):
    a_match = re.search(r'a\s*:\s*"([^"]+)"', block)
    z_match = re.search(r'z\s*:\s*"([^"]+)"', block)
    return (a_match.group(1) if a_match else None,
            z_match.group(1) if z_match else None)

def main():
    args = parse_args()
    keep_relationships = {r.strip() for r in args.relationships.split(",")}

    try:
        with open(args.input, "r", encoding="utf-8") as f:
            text = f.read()
    except Exception as e:
        sys.exit(f"Error reading input file: {e}")

    blocks = read_blocks(text)
    kept_relationships = []
    involved_entity_ids = set()

    # Pass 1: collect relationships of specified kinds and entity IDs
    for block in blocks:
        if block.startswith("relationship"):
            kind = extract_relationship_kind(block)
            if kind in keep_relationships:
                kept_relationships.append(block)
                a, z = extract_relationship_endpoints(block)
                if a:
                    involved_entity_ids.add(a)
                if z:
                    involved_entity_ids.add(z)

    # Pass 2: keep entities that are referenced
    kept_entities = [
        block for block in blocks
        if block.startswith("entity") and extract_entity_id(block) in involved_entity_ids
    ]

    # Write out filtered content
    try:
        with open(args.output, "w", encoding="utf-8") as out:
            for block in kept_entities + kept_relationships:
                out.write(block.strip() + "\n\n")
    except Exception as e:
        sys.exit(f"Error writing output file: {e}")

if __name__ == "__main__":
    main()
