import pytest

from main import load_config


class TestLoadConfig:
  def test_replace_string_is_loaded_as_string_replacement(self, tmp_path):
    (tmp_path / ".bz.toml").write_text(
      """
      [string.simple]
      "minecraft:allium" = "minecraft:poppy"
      """,
      encoding="utf-8",
    )

    config = load_config(tmp_path)

    assert config is not None
    assert config.string.simple == {
      "minecraft:allium": "minecraft:poppy",
    }

  def test_named_config_file_is_loaded(self, tmp_path):
    (tmp_path / "wood.bz.toml").write_text(
      """
      [block.simple]
      "minecraft:oak_planks" = "minecraft:spruce_planks"
      """,
      encoding="utf-8",
    )

    config = load_config(tmp_path)

    assert config is not None
    assert config.block.simple == {
      "minecraft:oak_planks": "minecraft:spruce_planks",
    }

  def test_string_pattern_and_regex_rules_are_loaded(self, tmp_path):
    (tmp_path / ".bz.toml").write_text(
      """
      [string.pattern]
      "minecraft:{flower}" = "minecraft:potted_{flower}"

      [string.regex]
      "minecraft:(?P<wood>oak)_sign" = "minecraft:dark_{wood}_sign"
      """,
      encoding="utf-8",
    )

    config = load_config(tmp_path)

    assert config is not None
    assert config.string.pattern == {
      "minecraft:{flower}": "minecraft:potted_{flower}",
    }
    assert config.string.regex == {
      "minecraft:(?P<wood>oak)_sign": "minecraft:dark_{wood}_sign",
    }

  def test_multiple_config_files_raise_error(self, tmp_path):
    (tmp_path / ".bz.toml").write_text(
      """
      [block.simple]
      "minecraft:stone" = "minecraft:deepslate"
      """,
      encoding="utf-8",
    )
    (tmp_path / "replace_stairs.bz.toml").write_text(
      """
      [block.pattern]
      "minecraft:oak_{part}" = "minecraft:dark_oak_{part}"
      """,
      encoding="utf-8",
    )

    with pytest.raises(RuntimeError):
      load_config(tmp_path)
