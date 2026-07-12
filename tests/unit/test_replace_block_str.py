import pytest

from main import replace_block_str
from tests.unit.helpers import make_state


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
    state = make_state(
      replace_block={"minecraft:oak_stairs": "minecraft:birch_stairs"},
      replace_block_pattern={"minecraft:oak_{part}": "minecraft:dark_oak_{part}"},
    )
    with pytest.raises(RuntimeError):
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
    with pytest.raises(RuntimeError):
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
    with pytest.raises(RuntimeError):
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
