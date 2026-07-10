import sys
import os
import json
import nbtlib
from collections import defaultdict

# Global variables to track blocks and replacements
blocks = defaultdict(dict)  # mod_id -> {block_name: count}
block_structures = defaultdict(dict)  # mod_id -> {block_name: set of file paths}
replacements_made = defaultdict(int)

def load_replacements(replacements_file_path):
    with open(replacements_file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def get_mod_id(block_str: str):
    return block_str.split(":")

def print_level(content: str, level: int):
    print("  " * level + content)

def process_nbt_file(input_file_path: str, replacements: dict):
    print_level(f"{input_file_path}", 0)
    with nbtlib.load(input_file_path) as root:
        if "palette" not in root:
            print_level(f"! No palette found in {input_file_path}", 1)
            return
        for entry in root["palette"]:
            if "Name" not in entry:
                print_level(f"! Skipping entry in {input_file_path} without Name key: {entry}", 1)
                continue

            block_str = str(entry["Name"])
            # Keep track of all blocks in the structure
            (mod_id, _) = get_mod_id(block_str)
            if block_str not in blocks[mod_id]:
                blocks[mod_id][block_str] = 0
            blocks[mod_id][block_str] += 1
            
            # Track which structures use this block
            if block_str not in block_structures[mod_id]:
                block_structures[mod_id][block_str] = set()
            block_structures[mod_id][block_str].add(input_file_path)

            # Replace the block if it exists in the replacements
            if block_str in replacements:
                entry["Name"] = nbtlib.tag.String(replacements[block_str])
                print_level(f"{block_str} => {replacements[block_str]}", 1)
                replacements_made[block_str] += 1

def process_file(input_file_path, replacements):
    if input_file_path.endswith('.nbt'):
        process_nbt_file(input_file_path, replacements)
    else:
        print(f"! Skipping non-NBT file: {input_file_path}")

def process_directory(input_path, replacements):
    for root_dir, _, files in os.walk(input_path):
        for file in files:
            in_file = os.path.join(root_dir, file)
            process_file(in_file, replacements)

def process_file_or_directory(input_path, replacements):
    if os.path.isfile(input_path):
        process_file(input_path, replacements)
    elif os.path.isdir(input_path):
        process_directory(input_path, replacements)
    else:
        print(f"Error: '{input_path}' is not a file or directory.", file=sys.stderr)
        sys.exit(1)

def print_summary(replacements: dict):
    """Print a summary of all blocks found and replacements made."""
    print("\n=== SUMMARY ===")
    
    # Print all blocks found, grouped by mod and sorted by count
    print("Blocks found:")
    for mod_id in sorted(blocks.keys()):
        print(f"  {mod_id}:")
        # Sort blocks alphabetically by name
        sorted_blocks = sorted(blocks[mod_id].items(), key=lambda x: x[0])
        for block, count in sorted_blocks:
            # Get the structures that use this block
            structures = block_structures[mod_id].get(block, set())
            structure_list = ", ".join(sorted(structures))
            print(f"    - {block} ({count}) ({structure_list})")
    
    if replacements_made:
        print("\nReplacements made:")
        # Print header
        # Increase column widths for long block names
        col1_width = 50
        col2_width = 45
        col3_width = 8
        print(f"{'Original Block':<{col1_width}} {'Replacement':<{col2_width}} {'Structure Count':>{col3_width}}")
        print("-" * (col1_width + col2_width + col3_width + 2))
        for block, count in replacements_made.items():
            replacement = replacements.get(block, "Unknown")
            print(f"{block:<{col1_width}} {replacement:<{col2_width}} {count:>{col3_width}}")
    else:
        print("\nNo replacements made")

def main():
    if len(sys.argv) != 3:  
        print(f"Usage: {sys.argv[0]} <replacements.json> <input-file-or-directory>")
        sys.exit(1)
    
    replacements_file_path = sys.argv[1]
    input_path = sys.argv[2]
    replacements = load_replacements(replacements_file_path)
    
    # Reset global variables
    global blocks, block_structures, replacements_made
    blocks.clear()
    block_structures.clear()
    replacements_made.clear()
    
    process_file_or_directory(input_path, replacements)
    print_summary(replacements)

if __name__ == "__main__":
    main() 