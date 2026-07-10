import pytest
from pathlib import Path
from main import BZConfig, BZRules, BZRun, BZState, merge_state, replace_block_str, state_for_children


def make_state(
  replace_block: dict[str, str] | None = None,
  replace_block_pattern: dict[str, str] | None = None,
  allow_overlaps: bool = False,
) -> BZState:
  """Create a minimal BZState for testing."""
  return BZState(
    rules=BZRules(
      replace_block=replace_block or {},
      replace_block_pattern=replace_block_pattern or {},
      replace_item={},
    ),
    run=BZRun(
      output_root_dir=Path("."),
      input_root_dir=Path("."),
      dry_run=False,
      allow_overlaps=allow_overlaps,
    ),
    tree=None,
  )


class TestReplaceBlockStr:
  def test_exact_match(self):
    state = make_state(replace_block={"minecraft:stone": "minecraft:deepslate"})
    result = replace_block_str("minecraft:stone", state)
    assert result == "minecraft:deepslate"

  def test_pattern_match(self):
    state = make_state(
      replace_block_pattern={"minecraft:oak_{part}": "minecraft:dark_oak_{part}"}
    )
    result = replace_block_str("minecraft:oak_stairs", state)
    assert result == "minecraft:dark_oak_stairs"

  def test_exact_and_pattern_overlap_raises_error(self):
    # Both exact and pattern matching the same block is an overlap error
    state = make_state(
      replace_block={"minecraft:oak_stairs": "minecraft:birch_stairs"},
      replace_block_pattern={"minecraft:oak_{part}": "minecraft:dark_oak_{part}"},
    )
    with pytest.raises(RuntimeError, match="matches exact rule AND pattern"):
      replace_block_str("minecraft:oak_stairs", state)

  def test_exact_and_pattern_overlap_allowed(self):
    state = make_state(
      replace_block={"minecraft:oak_stairs": "minecraft:birch_stairs"},
      replace_block_pattern={"minecraft:oak_{part}": "minecraft:dark_oak_{part}"},
      allow_overlaps=True,
    )
    result = replace_block_str("minecraft:oak_stairs", state)
    assert result == "minecraft:birch_stairs"

  def test_no_match_returns_none(self):
    state = make_state(replace_block={"minecraft:stone": "minecraft:deepslate"})
    result = replace_block_str("minecraft:dirt", state)
    assert result is None

  def test_pattern_overlap_raises_error(self):
    state = make_state(
      replace_block_pattern={
        "minecraft:oak_{part}": "minecraft:dark_oak_{part}",
        "minecraft:{wood}_stairs": "minecraft:{wood}_slab",
      }
    )
    with pytest.raises(RuntimeError, match="matches multiple patterns"):
      replace_block_str("minecraft:oak_stairs", state)

  def test_pattern_overlap_allowed(self):
    state = make_state(
      replace_block_pattern={
        "minecraft:oak_{part}": "minecraft:dark_oak_{part}",
        "minecraft:{wood}_stairs": "minecraft:{wood}_slab",
      },
      allow_overlaps=True,
    )
    # Should not raise, returns first match
    result = replace_block_str("minecraft:oak_stairs", state)
    assert result is not None

  def test_empty_config(self):
    state = make_state()
    result = replace_block_str("minecraft:stone", state)
    assert result is None

  def test_exact_and_pattern_overlap_with_multiple_patterns_raises_error(self):
    # Exact match + multiple overlapping patterns - still an error
    state = make_state(
      replace_block={"minecraft:oak_stairs": "minecraft:spruce_stairs"},
      replace_block_pattern={
        "minecraft:oak_{part}": "minecraft:dark_oak_{part}",
        "minecraft:{wood}_stairs": "minecraft:{wood}_slab",
      },
    )
    with pytest.raises(RuntimeError, match="matches exact rule AND pattern"):
      replace_block_str("minecraft:oak_stairs", state)

  def test_exact_and_pattern_overlap_with_multiple_patterns_allowed(self):
    state = make_state(
      replace_block={"minecraft:oak_stairs": "minecraft:spruce_stairs"},
      replace_block_pattern={
        "minecraft:oak_{part}": "minecraft:dark_oak_{part}",
        "minecraft:{wood}_stairs": "minecraft:{wood}_slab",
      },
      allow_overlaps=True,
    )
    result = replace_block_str("minecraft:oak_stairs", state)
    assert result == "minecraft:spruce_stairs"

  def test_pattern_match_different_block(self):
    # A block that matches only one pattern
    state = make_state(
      replace_block_pattern={
        "minecraft:oak_{part}": "minecraft:dark_oak_{part}",
        "minecraft:{wood}_stairs": "minecraft:{wood}_slab",
      }
    )
    result = replace_block_str("minecraft:oak_planks", state)
    assert result == "minecraft:dark_oak_planks"


class TestMergeState:
  def test_inherit_true_merges_parent_and_local_rules(self):
    base = make_state(
      replace_block={
        "minecraft:stone": "minecraft:deepslate",
        "minecraft:oak_planks": "minecraft:birch_planks",
      },
      replace_block_pattern={
        "minecraft:oak_{part}": "minecraft:dark_oak_{part}",
      },
    )
    config = BZConfig(
      replace_block={
        "minecraft:oak_planks": "minecraft:spruce_planks",
      },
      replace_item={
        "farmersdelight:dough": "create:dough",
      },
    )

    state = merge_state(base, config)

    assert state.rules.replace_block == {
      "minecraft:stone": "minecraft:deepslate",
      "minecraft:oak_planks": "minecraft:spruce_planks",
    }
    assert state.rules.replace_block_pattern == {
      "minecraft:oak_{part}": "minecraft:dark_oak_{part}",
    }
    assert state.rules.replace_item == {
      "farmersdelight:dough": "create:dough",
    }

  def test_inherit_false_replaces_parent_rules_with_local_rules(self):
    base = make_state(
      replace_block={
        "minecraft:stone": "minecraft:deepslate",
        "minecraft:oak_planks": "minecraft:birch_planks",
      },
      replace_block_pattern={
        "minecraft:oak_{part}": "minecraft:dark_oak_{part}",
      },
    )
    config = BZConfig(
      inherit=False,
      replace_block={
        "minecraft:oak_planks": "minecraft:spruce_planks",
      },
    )

    state = merge_state(base, config)

    assert state.rules.replace_block == {
      "minecraft:oak_planks": "minecraft:spruce_planks",
    }
    assert state.rules.replace_block_pattern == {}
    assert state.rules.replace_item == {}


class TestStateForChildren:
  def test_no_local_config_passes_local_state_to_children(self):
    parent = make_state(replace_block={"minecraft:stone": "minecraft:deepslate"})
    local = make_state(replace_block={"minecraft:dirt": "minecraft:grass_block"})

    child_state = state_for_children(parent, local, None)

    assert child_state.rules == local.rules

  def test_recursive_true_passes_local_state_to_children(self):
    parent = make_state(replace_block={"minecraft:stone": "minecraft:deepslate"})
    local = make_state(replace_block={"minecraft:dirt": "minecraft:grass_block"})

    child_state = state_for_children(parent, local, BZConfig(recursive=True))

    assert child_state.rules == local.rules

  def test_recursive_false_with_inherit_true_passes_parent_state_to_children(self):
    parent = make_state(replace_block={"minecraft:stone": "minecraft:deepslate"})
    local = make_state(replace_block={"minecraft:dirt": "minecraft:grass_block"})

    child_state = state_for_children(
      parent,
      local,
      BZConfig(recursive=False, inherit=True),
    )

    assert child_state.rules == parent.rules

  def test_recursive_false_with_inherit_false_passes_empty_rules_to_children(self):
    parent = make_state(replace_block={"minecraft:stone": "minecraft:deepslate"})
    local = make_state(replace_block={"minecraft:dirt": "minecraft:grass_block"})

    child_state = state_for_children(
      parent,
      local,
      BZConfig(recursive=False, inherit=False),
    )

    assert child_state.rules == BZRules()
