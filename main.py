#!/usr/bin/env python3

import nbtlib
import tomllib
import argparse
import re
from pathlib import Path
from dataclasses import dataclass, field
from enum import StrEnum
from treelib import Tree

BZ_CONFIG_SUFFIX = ".bz.toml"
TREE_SUMMARY_LINE_TYPE = "ascii-ex"

@dataclass
class BZArgs:
  target_dir: Path
  output_dir: Path
  verbose: bool = False
  dry_run: bool = False
  allow_overlaps: bool = False
  tree_output: Path | None = None

@dataclass
class BZConfig:
  recursive: bool = True
  inherit: bool = True
  replace_block: dict[str, str] = field(default_factory=dict)
  replace_block_pattern: dict[str, str] = field(default_factory=dict)
  replace_string: dict[str, str] = field(default_factory=dict)

@dataclass
class BZRules:
  replace_block: dict[str, str] = field(default_factory=dict)
  replace_block_pattern: dict[str, str] = field(default_factory=dict)
  replace_string: dict[str, str] = field(default_factory=dict)

@dataclass(frozen=True)
class BZRun:
  output_root_dir: Path
  input_root_dir: Path
  dry_run: bool = False
  allow_overlaps: bool = False

class BZReplacementKind(StrEnum):
  BLOCK = "block"
  STRING = "string"

@dataclass(frozen=True)
class BZReplacement:
  kind: BZReplacementKind
  old_value: str
  new_value: str
  location: str | None = None

@dataclass(frozen=True)
class BZTreeDirectory:
  path: Path

@dataclass(frozen=True)
class BZTreeFile:
  path: Path

@dataclass
class BZState:
  rules: BZRules
  run: BZRun
  tree: Tree | None = None
  tree_node_id: str | None = None

def main():
  parser = argparse.ArgumentParser(
    prog="Block Zapper",
    description="Block Zapper is a script for recursively modifying blocks in Minecraft structure NBT."
  )
  parser.add_argument('target_dir', type=Path, help='target directory with nbt files and *.bz.toml files')
  parser.add_argument('output_dir', type=Path, help='output directory for modified nbt files')
  parser.add_argument('-v', '--verbose', action='store_true', help='enable verbose output')
  parser.add_argument('-n', '--dry-run', action='store_true', help='dry run, do not write or modify files')
  parser.add_argument('--allow-overlaps', action='store_true', help='allow blocks matching multiple rules (warns instead of failing)')
  parser.add_argument('--tree-output', type=Path, help='output a tree summary to the specified file')

  args = parser.parse_args()

  bz_args = BZArgs(
    target_dir=args.target_dir,
    output_dir=args.output_dir,
    verbose=args.verbose,
    dry_run=args.dry_run,
    allow_overlaps=args.allow_overlaps,
    tree_output=args.tree_output
  )

  start(bz_args)

def start(bz_args: BZArgs):
  # Check if output directory exists and is non-empty
  if bz_args.output_dir.exists():
    if any(bz_args.output_dir.iterdir()):
      raise RuntimeError(f"Output directory '{bz_args.output_dir}' exists and is not empty")

  root_tree, root_tree_node_id = create_tree_summary(bz_args.target_dir) if bz_args.tree_output else (None, None)
  
  run = BZRun(
    output_root_dir=bz_args.output_dir,
    input_root_dir=bz_args.target_dir,
    dry_run=bz_args.dry_run,
    allow_overlaps=bz_args.allow_overlaps)

  initial_state = BZState(
    rules=BZRules(),
    run=run,
    tree=root_tree,
    tree_node_id=root_tree_node_id)
  
  process_dir_rec(bz_args.target_dir, initial_state)
  
  if bz_args.tree_output and root_tree:
    with open(bz_args.tree_output, "w") as f:
      f.write(render_tree_summary(root_tree))

def load_config(path: Path) -> BZConfig | None:
  # Find *.bz.toml files in the current directory
  config_paths = sorted(
    file for file in path.iterdir()
    if file.is_file() and file.name.endswith(BZ_CONFIG_SUFFIX)
  )

  if not config_paths:
    return None

  if len(config_paths) > 1:
    names = ", ".join(config.name for config in config_paths)
    raise RuntimeError(f"Multiple bz configuration files found in {path}: {names}")

  config = config_paths[0]
  try: 
    with open(config, "rb") as f:
      data = tomllib.load(f)
  except Exception as e:
    raise RuntimeError(f"Failed to parse config file {config}") from e
  
  return BZConfig(
          recursive=data.get("recursive", True),
          inherit=data.get("inherit", True),
          replace_block=data.get("replace-block", {}),
          replace_block_pattern=data.get("replace-block-pattern", {}),
          replace_string=data.get("replace-string", {}),
      )

def merge_state(base: BZState, config: BZConfig, subtree: str | None = None) -> BZState:
  base_rules = base.rules if config.inherit else BZRules()

  return BZState(
    rules=BZRules(
      replace_block=base_rules.replace_block | config.replace_block,
      replace_block_pattern=base_rules.replace_block_pattern | config.replace_block_pattern,
      replace_string=base_rules.replace_string | config.replace_string,
    ),
    run=base.run,
    tree=base.tree,
    tree_node_id=subtree if subtree else base.tree_node_id
  )

def state_for_children(parent: BZState, local: BZState, config: BZConfig | None) -> BZState:
  if config is None or config.recursive:
    return local

  if config.inherit:
    return parent

  return BZState(
    rules=BZRules(),
    run=local.run,
    tree=local.tree,
    tree_node_id=local.tree_node_id
  )
  

def process_dir_rec(path: Path, old_state: BZState):
  """
  1. Get config if it exists
  2. Merge state
  3. Process nbt and snbt files
  4. Recurse into subdirectories
  """
  local_config = load_config(path)

  state = old_state if local_config is None else merge_state(old_state, local_config)
  child_base_state = state_for_children(old_state, state, local_config)

  for file in sorted(path.iterdir()):
    if file.is_file():
      process_file(file, state)

  for subdir in sorted(path.iterdir()):
    if subdir.is_dir():
      subtree = add_tree_directory(state.tree, state.tree_node_id, subdir) if state.tree and state.tree_node_id else None
      substate = BZState(
        rules=child_base_state.rules,
        run=child_base_state.run,
        tree=state.tree,
        tree_node_id=subtree
      )
      process_dir_rec(subdir, substate)

def process_file(path: Path, state: BZState):
  if path.suffix == ".nbt":
    process_nbt_file(path, state)
  elif path.suffix == ".snbt":
    process_snbt_file(path, state)


def match_block_pattern(block: str, patterns: dict) -> tuple[str | None, list[str]]:
  """
  Match a block against patterns with {placeholder} syntax.
  Returns (replacement string or None, list of all matching pattern keys).
  """
  matches = []
  result = None
  
  for pattern, replacement in patterns.items():
    # Convert pattern to regex: {name} -> (?P<name>.+)
    regex_pattern = re.escape(pattern)
    regex_pattern = re.sub(r'\\{(\w+)\\}', r'(?P<\1>.+)', regex_pattern)
    regex_pattern = f'^{regex_pattern}$'
    
    match = re.match(regex_pattern, block)
    if match:
      matches.append(pattern)
      if result is None:
        # Substitute captured groups into replacement
        result = replacement
        for name, value in match.groupdict().items():
          result = result.replace(f'{{{name}}}', value)
  
  return result, matches

def replace_block_str(block: str, state: BZState) -> str | None:
  """
  Get replacement for a block, checking exact matches first then patterns.
  Raises RuntimeError on overlapping matches unless allow_overlaps is set.
  """
  rules = state.rules
  has_exact = block in rules.replace_block
  pattern_result, matching_patterns = match_block_pattern(block, rules.replace_block_pattern) if rules.replace_block_pattern else (None, [])
  
  if has_exact and matching_patterns:
    msg = f"'{block}' rules are ambigious: matches exact rule and pattern(s): {matching_patterns}"
    if state.run.allow_overlaps:
      print(f"WARN: {msg} (using exact)")
    else:
      raise RuntimeError(f"{msg}. Use --allow-overlaps to proceed anyway.")

  if len(matching_patterns) > 1:
    msg = f"{block} matches multiple patterns: {matching_patterns}"
    if state.run.allow_overlaps:
      print(f"WARN: {msg} (using first)")
    else:
      raise RuntimeError(f"{msg}. Use --allow-overlaps to proceed anyway.")
  
  # Prioritize exact over pattern
  if has_exact:
    return rules.replace_block[block]
  elif pattern_result:
    return pattern_result
  return None

def replace_nbt_strings(
  node,
  replacements: dict[str, str],
  location: str,
) -> list[BZReplacement]:
  """
  Recursively replace exact NBT string values.
  Returns string replacements made.
  """
  replacements_made = []

  if isinstance(node, dict):
    for key, value in node.items():
      child_location = f"{location}.{key}"
      if isinstance(value, nbtlib.tag.String):
        old_value = str(value)
        if old_value in replacements:
          new_value = replacements[old_value]
          node[key] = nbtlib.tag.String(new_value)
          replacements_made.append(BZReplacement(
            kind=BZReplacementKind.STRING,
            old_value=old_value,
            new_value=new_value,
            location=child_location,
          ))
      else:
        replacements_made.extend(replace_nbt_strings(value, replacements, child_location))
  elif isinstance(node, list):
    for index, value in enumerate(node):
      child_location = f"{location}[{index}]"
      if isinstance(value, nbtlib.tag.String):
        old_value = str(value)
        if old_value in replacements:
          new_value = replacements[old_value]
          node[index] = nbtlib.tag.String(new_value)
          replacements_made.append(BZReplacement(
            kind=BZReplacementKind.STRING,
            old_value=old_value,
            new_value=new_value,
            location=child_location,
          ))
      else:
        replacements_made.extend(replace_nbt_strings(value, replacements, child_location))

  return replacements_made

def replace_payload_strings(root, replacements: dict[str, str]) -> list[BZReplacement]:
  """
  Replace strings inside block/entity NBT payloads without touching palette block states.
  """
  replacements_made = []

  for index, block in enumerate(root.get("blocks", [])):
    if "nbt" in block:
      replacements_made.extend(
        replace_nbt_strings(block["nbt"], replacements, f"blocks[{index}].nbt")
      )

  for index, entity in enumerate(root.get("entities", [])):
    if "nbt" in entity:
      replacements_made.extend(
        replace_nbt_strings(entity["nbt"], replacements, f"entities[{index}].nbt")
      )

  return replacements_made

def transform_nbt(root, state: BZState) -> list[BZReplacement]:
  """
  Apply replacements to an NBT structure.
  Returns replacements made.
  """
  replacements = []

  if "palette" not in root:
    raise ValueError("No palette found in nbt data")
  for index, entry in enumerate(root["palette"]):
    if "Name" not in entry:
      continue
    block = str(entry["Name"])
    new_block = replace_block_str(block, state)
    
    if new_block:
      entry["Name"] = nbtlib.tag.String(new_block)
      replacements.append(BZReplacement(
        kind=BZReplacementKind.BLOCK,
        old_value=block,
        new_value=new_block,
        location=f"palette[{index}].Name",
      ))

  if state.rules.replace_string:
    replacements.extend(replace_payload_strings(root, state.rules.replace_string))
  
  return replacements

def process_nbt_file(path: Path, state: BZState):
  """
  Load an NBT file, apply transformations, and save if changed.
  """
  nbt_file = nbtlib.load(path)
  
  try:
    replacements = transform_nbt(nbt_file, state)
  except ValueError as e:
    raise ValueError(f"{e} in {path}") from e
  
  if replacements:
    print_replacements(path, replacements)
    
    # Tree output
    if state.tree and state.tree_node_id:
      add_tree_file_replacements(state.tree, state.tree_node_id, path, replacements)
    
    if not state.run.dry_run:
      out_path = relative_output_path(path, state)
      out_path.parent.mkdir(parents=True, exist_ok=True)
      nbt_file.save(out_path)

def relative_output_path(path: Path, state: BZState) -> Path:
  return state.run.output_root_dir / path.relative_to(state.run.input_root_dir)

def print_replacements(path: Path, replacements: list[BZReplacement]):
  print(path)

  for replacement in replacements:
    print(f"    {replacement_label(replacement)}")

def replacement_label(replacement: BZReplacement) -> str:
  label = f"{replacement.old_value} -> {replacement.new_value}"
  return f"[{replacement.kind}] {label}"

def create_tree_summary(root_path: Path) -> tuple[Tree, str]:
  tree = Tree()
  root_node_id = tree_directory_id(root_path)
  tree.create_node(str(root_path), root_node_id, data=BZTreeDirectory(root_path))
  return tree, root_node_id

def add_tree_directory(tree: Tree, parent_node_id: str, path: Path) -> str:
  node_id = tree_directory_id(path)
  tree.create_node(f"{path.name}/", node_id, parent=parent_node_id, data=BZTreeDirectory(path))
  return node_id

def add_tree_file_replacements(
  tree: Tree,
  parent_node_id: str,
  path: Path,
  replacements: list[BZReplacement],
) -> str:
  file_node_id = tree_file_id(path)
  tree.create_node(path.name, file_node_id, parent=parent_node_id, data=BZTreeFile(path))

  for index, replacement in enumerate(replacements):
    tree.create_node(
      replacement_label(replacement),
      tree_replacement_id(path, index),
      parent=file_node_id,
      data=replacement,
    )

  return file_node_id

def render_tree_summary(tree: Tree) -> str:
  return tree.show(stdout=False, line_type=TREE_SUMMARY_LINE_TYPE, sorting=False)

def tree_directory_id(path: Path) -> str:
  return f"dir:{path}"

def tree_file_id(path: Path) -> str:
  return f"file:{path}"

def tree_replacement_id(path: Path, index: int) -> str:
  return f"replacement:{path}:{index}"

def process_snbt_file(file_path: Path, state: BZState):
  raise NotImplementedError("snbt processing not implemented yet")

if __name__ == "__main__":
  main()
