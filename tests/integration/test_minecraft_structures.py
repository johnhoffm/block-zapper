from __future__ import annotations

import shutil
import os
from collections import Counter
from pathlib import Path

import nbtlib
import pytest

from main import BZArgs, start

DEFAULT_MCMETA_REF = "1.21.8-data"
DEFAULT_STRUCTURE_DIR = (
    Path(__file__).parent
    / ".cache"
    / "mcmeta"
    / DEFAULT_MCMETA_REF
    / "data"
    / "minecraft"
    / "structure"
)


@pytest.fixture(scope="session")
def structure_dir() -> Path:
    path = Path(os.environ.get("BZ_MCMETA_STRUCTURE_DIR", DEFAULT_STRUCTURE_DIR))
    if not path.is_dir():
        pytest.skip(
            "Minecraft structure cache not found. Run "
            "`scripts/cache-mcmeta-structures.sh` or set BZ_MCMETA_STRUCTURE_DIR."
        )
    return path


def palette_blocks(path: Path) -> list[str]:
    with nbtlib.load(path) as root:
        return [str(entry["Name"]) for entry in root["palette"] if "Name" in entry]


def palette_counter(path: Path) -> Counter[str]:
    return Counter(palette_blocks(path))


def property_counter(path: Path, block: str) -> Counter[str]:
    with nbtlib.load(path) as root:
        return Counter(
            str(entry.get("Properties", {}))
            for entry in root["palette"]
            if str(entry.get("Name", "")) == block
        )


def find_structure_with_blocks(
    structure_dir: Path,
    required_blocks: set[str],
    *,
    under: str | None = None,
) -> Path:
    search_root = structure_dir / under if under else structure_dir
    for path in sorted(search_root.rglob("*.nbt")):
        blocks = set(palette_blocks(path))
        if required_blocks <= blocks:
            return path
    raise AssertionError(
        f"No structure under {search_root} contains {sorted(required_blocks)}"
    )


def copy_structure(source: Path, structure_dir: Path, input_dir: Path) -> Path:
    relative = source.relative_to(structure_dir)
    target = input_dir / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    return target


def write_config(path: Path, body: str) -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / ".bz.toml").write_text(body.strip() + "\n", encoding="utf-8")


def run_block_zapper(
    input_dir: Path,
    output_dir: Path,
    *,
    tree_output: Path | None = None,
    dry_run: bool = False,
    allow_overlaps: bool = False,
) -> None:
    start(
        BZArgs(
            target_dir=input_dir,
            output_dir=output_dir,
            dry_run=dry_run,
            allow_overlaps=allow_overlaps,
            tree_output=tree_output,
        )
    )


def test_rewrites_real_village_subset_and_preserves_palette_properties(
    tmp_path: Path,
    structure_dir: Path,
) -> None:
    source = find_structure_with_blocks(
        structure_dir,
        {"minecraft:oak_stairs", "minecraft:cobblestone"},
        under="village/plains/houses",
    )
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    tree_output = tmp_path / "tree.txt"
    copied = copy_structure(source, structure_dir, input_dir)

    write_config(
        input_dir,
        """
    [replace-block]
    "minecraft:cobblestone" = "minecraft:deepslate"

    [replace-block-pattern]
    "minecraft:oak_{part}" = "minecraft:dark_oak_{part}"
    """,
    )

    before = palette_counter(copied)
    oak_stairs_properties = property_counter(copied, "minecraft:oak_stairs")

    run_block_zapper(input_dir, output_dir, tree_output=tree_output)

    out_file = output_dir / copied.relative_to(input_dir)
    after = palette_counter(out_file)

    assert before["minecraft:oak_stairs"] > 0
    assert before["minecraft:cobblestone"] > 0
    assert after["minecraft:oak_stairs"] == 0
    assert after["minecraft:dark_oak_stairs"] == before["minecraft:oak_stairs"]
    assert after["minecraft:cobblestone"] == 0
    assert after["minecraft:deepslate"] == before["minecraft:cobblestone"]
    assert (
        property_counter(out_file, "minecraft:dark_oak_stairs") == oak_stairs_properties
    )

    tree = tree_output.read_text(encoding="utf-8")
    assert source.name in tree
    assert "minecraft:cobblestone -> minecraft:deepslate" in tree
    assert "minecraft:oak_stairs -> minecraft:dark_oak_stairs" in tree


def test_dry_run_reports_replacements_without_writing_outputs(
    tmp_path: Path,
    structure_dir: Path,
) -> None:
    source = find_structure_with_blocks(
        structure_dir,
        {"minecraft:hay_block"},
        under="village",
    )
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    tree_output = tmp_path / "dry-run-tree.txt"
    copied = copy_structure(source, structure_dir, input_dir)

    write_config(
        input_dir,
        """
    [replace-block]
    "minecraft:hay_block" = "minecraft:dried_kelp_block"
    """,
    )

    run_block_zapper(input_dir, output_dir, tree_output=tree_output, dry_run=True)

    assert not (output_dir / copied.relative_to(input_dir)).exists()
    assert not output_dir.exists()
    assert "minecraft:hay_block -> minecraft:dried_kelp_block" in tree_output.read_text(
        encoding="utf-8"
    )


def test_nested_configs_can_disable_inherited_rules_on_real_structures(
    tmp_path: Path,
    structure_dir: Path,
) -> None:
    source = find_structure_with_blocks(
        structure_dir,
        {"minecraft:cobblestone", "minecraft:grass_block"},
        under="village/taiga/houses",
    )
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    root_copy = copy_structure(source, structure_dir, input_dir / "root")
    local_copy = copy_structure(source, structure_dir, input_dir / "local")

    write_config(
        input_dir,
        """
    [replace-block]
    "minecraft:cobblestone" = "minecraft:deepslate"
    """,
    )
    write_config(
        local_copy.parent,
        """
    inherit = false

    [replace-block]
    "minecraft:grass_block" = "minecraft:mycelium"
    """,
    )

    run_block_zapper(input_dir, output_dir)

    root_after = palette_counter(output_dir / root_copy.relative_to(input_dir))
    local_after = palette_counter(output_dir / local_copy.relative_to(input_dir))

    assert root_after["minecraft:cobblestone"] == 0
    assert root_after["minecraft:deepslate"] > 0
    assert root_after["minecraft:grass_block"] > 0
    assert local_after["minecraft:cobblestone"] > 0
    assert local_after["minecraft:grass_block"] == 0
    assert local_after["minecraft:mycelium"] > 0


def test_real_structure_overlap_errors_stop_before_writing_output(
    tmp_path: Path,
    structure_dir: Path,
) -> None:
    source = find_structure_with_blocks(
        structure_dir,
        {"minecraft:oak_stairs"},
        under="village/plains/houses",
    )
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    copied = copy_structure(source, structure_dir, input_dir)

    write_config(
        input_dir,
        """
    [replace-block]
    "minecraft:oak_stairs" = "minecraft:birch_stairs"

    [replace-block-pattern]
    "minecraft:oak_{part}" = "minecraft:dark_oak_{part}"
    """,
    )

    with pytest.raises(RuntimeError, match="matches exact rule AND pattern"):
        run_block_zapper(input_dir, output_dir)

    assert not (output_dir / copied.relative_to(input_dir)).exists()
