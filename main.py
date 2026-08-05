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
RESOURCE_IDENTIFIER_PATTERN = re.compile(r"^[a-z0-9_.-]+:[a-z0-9_./-]+$")
RESOURCE_PATH_PATTERN = re.compile(r"^[a-z0-9_./-]+$")
PROBEJS_REGISTRY_TYPE_PATTERN = re.compile(
  r"\b(?:export\s+)?type\s+(?P<registry>Block|Item)\s*=\s*(?P<definition>.*?);",
  re.DOTALL,
)
PROBEJS_STRING_LITERAL_PATTERN = re.compile(r'"(?P<resource>[^"]+)"')

@dataclass
class BZArgs:
  target_dir: Path
  output_dir: Path
  verbose: bool = False
  dry_run: bool = False
  allow_overlaps: bool = False
  allowlist: Path | None = None
  tree_output: Path | None = None

@dataclass
class BZReplacementRules:
  """Rules for one replacement domain, applied as simple, pattern, then regex."""
  simple: dict[str, str] = field(default_factory=dict)
  pattern: dict[str, str] = field(default_factory=dict)
  regex: dict[str, str] = field(default_factory=dict)

  def merged_with(self, overriding_rules: "BZReplacementRules") -> "BZReplacementRules":
    return BZReplacementRules(
      simple=self.simple | overriding_rules.simple,
      pattern=self.pattern | overriding_rules.pattern,
      regex=self.regex | overriding_rules.regex,
    )

  def is_empty(self) -> bool:
    return not (self.simple or self.pattern or self.regex)

@dataclass
class BZConfig:
  recursive: bool = True
  inherit: bool = True
  block: BZReplacementRules = field(default_factory=BZReplacementRules)
  string: BZReplacementRules = field(default_factory=BZReplacementRules)

@dataclass
class BZRules:
  block: BZReplacementRules = field(default_factory=BZReplacementRules)
  string: BZReplacementRules = field(default_factory=BZReplacementRules)

@dataclass
class BZAllowlist:
  blocks: set[str]
  items: set[str]

@dataclass(frozen=True)
class BZRun:
  output_root_dir: Path
  input_root_dir: Path
  dry_run: bool = False
  allow_overlaps: bool = False
  allowlist: BZAllowlist | None = None

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
  parser.add_argument('--allowlist', type=Path, metavar='FILE', help='only replace listed blocks and items in FILE (one mod:id per line or a path to ProbeJS registry type file)')
  parser.add_argument('--tree-output', type=Path, help='output a tree summary to the specified file')

  args = parser.parse_args()

  bz_args = BZArgs(
    target_dir=args.target_dir,
    output_dir=args.output_dir,
    verbose=args.verbose,
    dry_run=args.dry_run,
    allow_overlaps=args.allow_overlaps,
    allowlist=args.allowlist,
    tree_output=args.tree_output
  )

  start(bz_args)

def start(bz_args: BZArgs):
  allowlist = load_allowlist(bz_args.allowlist) if bz_args.allowlist else None

  # Check if output directory exists and is non-empty
  if bz_args.output_dir.exists():
    if any(bz_args.output_dir.iterdir()):
      raise RuntimeError(f"Output directory '{bz_args.output_dir}' exists and is not empty")

  root_tree, root_tree_node_id = create_tree_summary(bz_args.target_dir) if bz_args.tree_output else (None, None)
  
  run = BZRun(
    output_root_dir=bz_args.output_dir,
    input_root_dir=bz_args.target_dir,
    dry_run=bz_args.dry_run,
    allow_overlaps=bz_args.allow_overlaps,
    allowlist=allowlist)

  initial_state = BZState(
    rules=BZRules(),
    run=run,
    tree=root_tree,
    tree_node_id=root_tree_node_id)
  
  process_dir_rec(bz_args.target_dir, initial_state)
  
  if bz_args.tree_output and root_tree:
    with open(bz_args.tree_output, "w") as f:
      f.write(render_tree_summary(root_tree))

def load_allowlist(path: Path) -> BZAllowlist:
  """Load block and item allowlists from plain text or a ProbeJS registry type file."""
  try:
    content = path.read_text(encoding="utf-8")  
  except OSError as error:
    raise RuntimeError(f"Failed to read allowlist file {path}") from error

  probejs_registry_types = {
    match.group("registry"): load_probejs_allowlist(
      path,
      match.group("registry"),
      match.group("definition"),
    )
    for match in PROBEJS_REGISTRY_TYPE_PATTERN.finditer(content)
  }
  if probejs_registry_types:
    return BZAllowlist(
      blocks=probejs_registry_types.get("Block", set()),
      items=probejs_registry_types.get("Item", set()),
    )

  allowlist = set()
  for line_number, line in enumerate(content.splitlines(), start=1):
    resource = line.strip()
    if not resource:
      continue
    validate_resource_identifier(resource, f"allowlist {path} on line {line_number}")
    allowlist.add(resource)

  resources = set(allowlist)
  return BZAllowlist(blocks=resources, items=resources)

def load_probejs_allowlist(
  path: Path,
  registry: str,
  type_definition: str,
) -> set[str]:
  """Extract resource IDs from a ProbeJS generated registry type union."""
  allowlist = {
    normalize_probejs_resource(resource, f"ProbeJS {registry} type in {path}")
    for resource in PROBEJS_STRING_LITERAL_PATTERN.findall(type_definition)
  }
  return allowlist

def normalize_probejs_resource(resource: str, location: str) -> str:
  if RESOURCE_IDENTIFIER_PATTERN.fullmatch(resource):
    return resource
  if RESOURCE_PATH_PATTERN.fullmatch(resource):
    return f"minecraft:{resource}"
  raise RuntimeError(f"Invalid resource identifier in {location}: {resource!r}")

def validate_resource_identifier(resource: str, location: str):
  if not RESOURCE_IDENTIFIER_PATTERN.fullmatch(resource):
    raise RuntimeError(f"Invalid resource identifier in {location}: {resource!r}")

def load_replacement_rules(
  config_path: Path,
  rule_kind: str,
  data: dict,
) -> BZReplacementRules:
  rule_data = data.get(rule_kind, {})
  regexes = rule_data.get("regex", {})
  for regex in regexes:
    try:
      re.compile(regex)
    except re.error as error:
      raise RuntimeError(
        f"Invalid {rule_kind}.regex '{regex}' in {config_path}: {error}"
      ) from error

  return BZReplacementRules(
    simple=rule_data.get("simple", {}),
    pattern=rule_data.get("pattern", {}),
    regex=regexes,
  )

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
    block=load_replacement_rules(config, "block", data),
    string=load_replacement_rules(config, "string", data),
  )

def merge_state(base: BZState, config: BZConfig, subtree: str | None = None) -> BZState:
  base_rules = base.rules if config.inherit else BZRules()

  return BZState(
    rules=BZRules(
      block=base_rules.block.merged_with(config.block),
      string=base_rules.string.merged_with(config.string),
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


def match_pattern(value: str, patterns: dict) -> tuple[str | None, list[str]]:
  """
  Match a value against patterns with {placeholder} syntax.
  Returns (replacement string or None, list of all matching pattern keys).
  """
  matches = []
  result = None
  
  for pattern, replacement in patterns.items():
    # Convert pattern to regex: {name} -> (?P<name>.+)
    regex_pattern = re.escape(pattern)
    regex_pattern = re.sub(r'\\{(\w+)\\}', r'(?P<\1>.+)', regex_pattern)
    regex_pattern = f'^{regex_pattern}$'
    
    match = re.match(regex_pattern, value)
    if match:
      matches.append(pattern)
      if result is None:
        # Substitute captured groups into replacement
        result = replacement
        for name, captured_value in match.groupdict().items():
          result = result.replace(f'{{{name}}}', captured_value)
  
  return result, matches

def match_block_pattern(block: str, patterns: dict) -> tuple[str | None, list[str]]:
  return match_pattern(block, patterns)

def match_regex(value: str, regexes: dict, rule_kind: str) -> tuple[str | None, list[str]]:
  """
  Match a value against full regular expressions with named capture groups.
  Named groups can be referenced in replacement strings with {name}.
  Returns (replacement string or None, list of all matching regex keys).
  """
  matches = []
  result = None

  for regex, replacement in regexes.items():
    try:
      match = re.fullmatch(regex, value)
    except re.error as error:
      raise RuntimeError(f"Invalid {rule_kind}.regex '{regex}': {error}") from error

    if match:
      matches.append(regex)
      if result is None:
        result = replacement
        for name, captured_value in match.groupdict().items():
          result = result.replace(f"{{{name}}}", captured_value or "")

  return result, matches

def match_block_regex(block: str, regexes: dict) -> tuple[str | None, list[str]]:
  return match_regex(block, regexes, "block")

def resolve_replacement(
  value: str,
  rules: BZReplacementRules,
  rule_kind: str,
  allow_overlaps: bool,
) -> str | None:
  """Resolve one value according to the replacement rule precedence."""
  has_exact = value in rules.simple
  pattern_result, matching_patterns = match_pattern(value, rules.pattern) if rules.pattern else (None, [])
  regex_result, matching_regexes = match_regex(value, rules.regex, rule_kind) if rules.regex else (None, [])
  matching_rules = matching_patterns + matching_regexes

  if has_exact and matching_rules:
    msg = f"'{value}' {rule_kind} rules are ambiguous: matches simple rule and pattern(s): {matching_rules}"
    if allow_overlaps:
      print(f"WARN: {msg} (using simple)")
    else:
      raise RuntimeError(f"{msg}. Use --allow-overlaps to proceed anyway.")

  if len(matching_rules) > 1:
    msg = f"{value} matches multiple {rule_kind} patterns: {matching_rules}"
    if allow_overlaps:
      print(f"WARN: {msg} (using first)")
    else:
      raise RuntimeError(f"{msg}. Use --allow-overlaps to proceed anyway.")

  if has_exact:
    return rules.simple[value]
  if pattern_result:
    return pattern_result
  return regex_result

def replace_block_str(block: str, state: BZState) -> str | None:
  """
  Get a block replacement, checking simple, pattern, then regex rules.
  Raises RuntimeError on overlapping matches unless allow_overlaps is set.
  """
  rules = state.rules.block
  replacement = resolve_replacement(
    block,
    rules,
    "block",
    state.run.allow_overlaps,
  )
  if replacement is None:
    return None

  if state.run.allowlist is not None and replacement not in state.run.allowlist.blocks:
    raise RuntimeError(
      f"Replacement block '{replacement}' is not in the global block allowlist."
    )

  return replacement

def replace_nbt_strings(
  node,
  rules: BZReplacementRules,
  location: str,
  allowlist: BZAllowlist | None = None,
  allow_overlaps: bool = False,
) -> list[BZReplacement]:
  """
  Recursively replace NBT string values.
  Returns string replacements made.
  """
  replacements_made = []

  if isinstance(node, dict):
    for key, value in node.items():
      child_location = f"{location}.{key}"
      if isinstance(value, nbtlib.tag.String):
        old_value = str(value)
        new_value = resolve_replacement(
          old_value, rules, "string", allow_overlaps
        )
        if new_value is not None:
          if allowlist is not None and new_value not in allowlist.items:
            raise RuntimeError(
              f"Replacement item '{new_value}' is not in the global item allowlist."
            )
          node[key] = nbtlib.tag.String(new_value)
          replacements_made.append(BZReplacement(
            kind=BZReplacementKind.STRING,
            old_value=old_value,
            new_value=new_value,
            location=child_location,
          ))
      else:
        replacements_made.extend(replace_nbt_strings(
          value, rules, child_location, allowlist, allow_overlaps
        ))
  elif isinstance(node, list):
    for index, value in enumerate(node):
      child_location = f"{location}[{index}]"
      if isinstance(value, nbtlib.tag.String):
        old_value = str(value)
        new_value = resolve_replacement(
          old_value, rules, "string", allow_overlaps
        )
        if new_value is not None:
          if allowlist is not None and new_value not in allowlist.items:
            raise RuntimeError(
              f"Replacement item '{new_value}' is not in the global item allowlist."
            )
          node[index] = nbtlib.tag.String(new_value)
          replacements_made.append(BZReplacement(
            kind=BZReplacementKind.STRING,
            old_value=old_value,
            new_value=new_value,
            location=child_location,
          ))
      else:
        replacements_made.extend(replace_nbt_strings(
          value, rules, child_location, allowlist, allow_overlaps
        ))

  return replacements_made

def replace_payload_strings(
  root,
  rules: BZReplacementRules,
  allowlist: BZAllowlist | None,
  allow_overlaps: bool,
) -> list[BZReplacement]:
  """
  Replace strings inside block/entity NBT payloads without touching palette block states.
  """
  replacements_made = []

  for index, block in enumerate(root.get("blocks", [])):
    if "nbt" in block:
      replacements_made.extend(
        replace_nbt_strings(
          block["nbt"], rules, f"blocks[{index}].nbt", allowlist, allow_overlaps,
        )
      )

  for index, entity in enumerate(root.get("entities", [])):
    if "nbt" in entity:
      replacements_made.extend(
        replace_nbt_strings(
          entity["nbt"], rules, f"entities[{index}].nbt", allowlist, allow_overlaps,
        )
      )

  return replacements_made

def transform_nbt(root, state: BZState) -> list[BZReplacement]:
  """
  Apply replacements to an NBT structure.
  Returns replacements made.
  """
  replacements = []

  if "palette" in root:
    palettes = [("palette", root["palette"])]
  # Shipwrecks use "palettes" plural since they have randomized material sets
  elif "palettes" in root:
    palettes = [
      (f"palettes[{palette_index}]", palette)
      for palette_index, palette in enumerate(root["palettes"])
    ]
  else:
    raise ValueError("No palette found in nbt data")

  for palette_location, palette in palettes:
    for index, entry in enumerate(palette):
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
          location=f"{palette_location}[{index}].Name",
        ))

  if not state.rules.string.is_empty():
    replacements.extend(
      replace_payload_strings(
        root,
        state.rules.string,
        state.run.allowlist,
        state.run.allow_overlaps,
      )
    )
  
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
