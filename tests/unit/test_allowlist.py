import pytest

from main import BZAllowlist, load_allowlist


def test_load_allowlist_reads_one_block_identifier_per_line(tmp_path):
  allowlist_path = tmp_path / "allowlist.txt"
  allowlist_path.write_text("minecraft:dirt\n\nminecraft:grass_block\n")

  assert load_allowlist(allowlist_path) == BZAllowlist(
    blocks={"minecraft:dirt", "minecraft:grass_block"},
    items={"minecraft:dirt", "minecraft:grass_block"},
  )


def test_load_allowlist_rejects_invalid_block_identifier(tmp_path):
  allowlist_path = tmp_path / "allowlist.txt"
  allowlist_path.write_text("minecraft:dirt\nnot a block\n")

  with pytest.raises(RuntimeError):
    load_allowlist(allowlist_path)


def test_load_allowlist_reads_blocks_and_items_from_probejs_registry_type_file(tmp_path):
  allowlist_path = tmp_path / "index.d.ts"
  allowlist_path.write_text('''
declare module "@special/types/RegistryTypes" {
  export type Item = "minecraft:stone" | "minecraft:stick";
  export type Block = "minecraft:dirt" | "minecraft:grass_block" | "example:lamp";
}
''')

  assert load_allowlist(allowlist_path) == BZAllowlist(
    blocks={
      "minecraft:dirt",
      "minecraft:grass_block",
      "example:lamp",
    },
    items={"minecraft:stone", "minecraft:stick"},
  )
