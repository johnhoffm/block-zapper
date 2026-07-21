import pytest

from main import load_allowlist


def test_load_allowlist_reads_one_block_identifier_per_line(tmp_path):
  allowlist_path = tmp_path / "allowlist.txt"
  allowlist_path.write_text("minecraft:dirt\n\nminecraft:grass_block\n")

  assert load_allowlist(allowlist_path) == frozenset({
    "minecraft:dirt",
    "minecraft:grass_block",
  })


def test_load_allowlist_rejects_invalid_block_identifier(tmp_path):
  allowlist_path = tmp_path / "allowlist.txt"
  allowlist_path.write_text("minecraft:dirt\nnot a block\n")

  with pytest.raises(RuntimeError):
    load_allowlist(allowlist_path)
