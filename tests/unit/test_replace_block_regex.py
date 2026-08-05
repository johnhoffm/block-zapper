import pytest

from main import BZAllowlist, load_config, match_block_regex, replace_block_str
from tests.unit.helpers import make_state


class TestMatchBlockRegex:
  def test_named_capture_is_substituted_in_replacement(self):
    regexes = {
      "minecraft:(?P<wood>oak)_planks": "minecraft:dark_{wood}_planks",
    }

    result, matches = match_block_regex("minecraft:oak_planks", regexes)

    assert result == "minecraft:dark_oak_planks"
    assert matches == ["minecraft:(?P<wood>oak)_planks"]

  def test_or_expression_matches_either_choice(self):
    regexes = {
      "minecraft:(?P<wood>oak|birch)_planks": "minecraft:dark_{wood}_planks",
    }

    result, matches = match_block_regex("minecraft:birch_planks", regexes)

    assert result == "minecraft:dark_birch_planks"
    assert matches == ["minecraft:(?P<wood>oak|birch)_planks"]

  def test_capture_accepts_id_characters_including_slashes_and_colons(self):
    regexes = {
      "(?P<id>[a-z0-9_/:]+)": "copy:{id}",
    }

    result, matches = match_block_regex("example:folder/block_2", regexes)

    assert result == "copy:example:folder/block_2"
    assert matches == ["(?P<id>[a-z0-9_/:]+)"]

  def test_regex_without_named_captures_uses_fixed_replacement(self):
    regexes = {
      "minecraft:oak_planks": "minecraft:dark_oak_planks",
    }

    result, matches = match_block_regex("minecraft:oak_planks", regexes)

    assert result == "minecraft:dark_oak_planks"
    assert matches == ["minecraft:oak_planks"]

  def test_only_matches_the_entire_block_id(self):
    regexes = {
      "minecraft:oak": "minecraft:dark_oak",
    }

    result, matches = match_block_regex("minecraft:oak_planks", regexes)

    assert result is None
    assert matches == []

  def test_multiple_matching_regexes_are_reported(self):
    regexes = {
      "minecraft:(?P<wood>oak)_planks": "minecraft:dark_{wood}_planks",
      "minecraft:oak_(?P<block>.+)": "minecraft:birch_{block}",
    }

    result, matches = match_block_regex("minecraft:oak_planks", regexes)

    assert result == "minecraft:dark_oak_planks"
    assert matches == list(regexes)


class TestReplaceBlockRegex:
  def test_regex_rule_replaces_block(self):
    state = make_state(
      replace_block_regex={
        "minecraft:(?P<wood>oak)_planks": "minecraft:dark_{wood}_planks",
      },
    )

    assert replace_block_str("minecraft:oak_planks", state) == "minecraft:dark_oak_planks"

  def test_regex_rule_replaces_block_when_destination_is_allowlisted(self):
    state = make_state(
      replace_block_regex={
        "minecraft:(?P<wood>oak)_planks": "minecraft:dark_{wood}_planks",
      },
      allowlist=BZAllowlist(blocks={"minecraft:dark_oak_planks"}, items=set()),
    )

    assert replace_block_str("minecraft:oak_planks", state) == "minecraft:dark_oak_planks"

  def test_regex_rule_rejects_block_when_destination_is_not_allowlisted(self):
    state = make_state(
      replace_block_regex={
        "minecraft:(?P<wood>oak)_planks": "minecraft:dark_{wood}_planks",
      },
      allowlist=BZAllowlist(blocks={"minecraft:oak_planks"}, items=set()),
    )

    with pytest.raises(RuntimeError):
      replace_block_str("minecraft:oak_planks", state)

  def test_regex_and_template_pattern_overlap_raises_error(self):
    state = make_state(
      replace_block_pattern={"minecraft:oak_{part}": "minecraft:dark_oak_{part}"},
      replace_block_regex={"minecraft:oak_(?P<part>.+)": "minecraft:birch_{part}"},
    )

    with pytest.raises(RuntimeError):
      replace_block_str("minecraft:oak_planks", state)

  def test_regex_rules_are_loaded_from_config(self, tmp_path):
    (tmp_path / ".bz.toml").write_text(
      """
      [block.regex]
      "minecraft:(?P<wood>oak)_planks" = "minecraft:dark_{wood}_planks"
      """,
      encoding="utf-8",
    )

    config = load_config(tmp_path)

    assert config is not None
    assert config.block.regex == {
      "minecraft:(?P<wood>oak)_planks": "minecraft:dark_{wood}_planks",
    }

  def test_invalid_regex_in_config_raises_clear_error(self, tmp_path):
    (tmp_path / ".bz.toml").write_text(
      """
      [block.regex]
      "minecraft:(?P<wood>oak" = "minecraft:dark_{wood}"
      """,
      encoding="utf-8",
    )

    with pytest.raises(RuntimeError):
      load_config(tmp_path)
