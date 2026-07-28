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
    assert config.replace_string == {
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
    assert config.replace_block == {
      "minecraft:oak_planks": "minecraft:spruce_planks",
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
