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
        if "palette" not in root:
            return []
        return [str(entry["Name"]) for entry in root["palette"] if "Name" in entry]


def palette_counter(path: Path) -> Counter[str]:
    return Counter(palette_blocks(path))


def block_placement_counter(path: Path) -> Counter[str]:
    with nbtlib.load(path) as root:
        if "palette" not in root:
            return Counter()

        palette = [str(entry.get("Name", "")) for entry in root["palette"]]
        blocks: Counter[str] = Counter()
        for block in root.get("blocks", []):
            state = int(block.get("state", -1))
            if 0 <= state < len(palette):
                blocks[palette[state]] += 1
        return blocks


def property_counter(path: Path, block: str) -> Counter[str]:
    with nbtlib.load(path) as root:
        return Counter(
            str(entry.get("Properties", {}))
            for entry in root["palette"]
            if str(entry.get("Name", "")) == block
        )


def potted_plant_blocks(path: Path) -> set[str]:
    return {
        block for block in palette_blocks(path) if block.startswith("minecraft:potted_")
    }


def item_id_counter(path: Path) -> Counter[str]:
    items: Counter[str] = Counter()
    with nbtlib.load(path) as root:
        for block in root.get("blocks", []):
            block_nbt = block.get("nbt")
            if not block_nbt:
                continue
            for item in block_nbt.get("Items", []):
                if "id" in item:
                    items[str(item["id"])] += int(item.get("count", 1))
    return items


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


def find_structures_with_common_blocks(
    structure_dir: Path,
    target_blocks: set[str],
    *,
    under: tuple[str, ...],
    limit: int,
) -> list[Path]:
    scored: list[tuple[int, str, Path]] = []
    for subpath in under:
        for path in sorted((structure_dir / subpath).rglob("*.nbt")):
            counts = block_placement_counter(path)
            score = sum(counts[block] for block in target_blocks)
            if score:
                scored.append((score, str(path.relative_to(structure_dir)), path))

    scored.sort(reverse=True)
    if len(scored) < limit:
        raise AssertionError(
            f"Found only {len(scored)} structures with {sorted(target_blocks)}"
        )
    return [path for _, _, path in scored[:limit]]


def copy_structure(source: Path, structure_dir: Path, input_dir: Path) -> Path:
    relative = source.relative_to(structure_dir)
    target = input_dir / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    return target


def write_config(path: Path, body: str) -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / ".bz.toml").write_text(body.strip() + "\n", encoding="utf-8")


def test_rewrites_many_common_blocks_across_many_real_structures(
    tmp_path: Path,
    structure_dir: Path,
) -> None:
    replacements = {
        "minecraft:stone_bricks": "minecraft:deepslate_bricks",
        "minecraft:cobblestone": "minecraft:calcite",
        "minecraft:oak_planks": "minecraft:spruce_planks",
        "minecraft:oak_log": "minecraft:spruce_log",
        "minecraft:oak_stairs": "minecraft:spruce_stairs",
        "minecraft:oak_slab": "minecraft:spruce_slab",
    }
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    sources = find_structures_with_common_blocks(
        structure_dir,
        set(replacements),
        under=(
            "village/plains/houses",
            "village/plains/zombie/houses",
            "woodland_mansion",
            "underwater_ruin",
        ),
        limit=40,
    )
    copied = [copy_structure(source, structure_dir, input_dir) for source in sources]

    write_config(
        input_dir,
        """
    [replace-block]
    "minecraft:stone_bricks" = "minecraft:deepslate_bricks"
    "minecraft:cobblestone" = "minecraft:calcite"
    "minecraft:oak_planks" = "minecraft:spruce_planks"
    "minecraft:oak_log" = "minecraft:spruce_log"
    "minecraft:oak_stairs" = "minecraft:spruce_stairs"
    "minecraft:oak_slab" = "minecraft:spruce_slab"
    """,
    )

    before = Counter()
    for path in copied:
        before.update(block_placement_counter(path))

    start(BZArgs(target_dir=input_dir, output_dir=output_dir))

    after = Counter()
    for path in copied:
        out_file = output_dir / path.relative_to(input_dir)
        assert out_file.exists()
        after.update(block_placement_counter(out_file))

    assert len(copied) == 40
    assert before["minecraft:stone_bricks"] >= 500
    assert before["minecraft:cobblestone"] >= 3_000
    assert (
        before["minecraft:oak_planks"]
        + before["minecraft:oak_log"]
        + before["minecraft:oak_stairs"]
        + before["minecraft:oak_slab"]
        >= 4_000
    )

    for old_block, new_block in replacements.items():
        assert after[old_block] == 0
        assert after[new_block] == before[new_block] + before[old_block]


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

    start(
        BZArgs(
            target_dir=input_dir,
            output_dir=output_dir,
            tree_output=tree_output,
        )
    )

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

    start(
        BZArgs(
            target_dir=input_dir,
            output_dir=output_dir,
            dry_run=True,
            tree_output=tree_output,
        )
    )

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

    start(BZArgs(target_dir=input_dir, output_dir=output_dir))

    root_after = palette_counter(output_dir / root_copy.relative_to(input_dir))
    local_after = palette_counter(output_dir / local_copy.relative_to(input_dir))

    assert root_after["minecraft:cobblestone"] == 0
    assert root_after["minecraft:deepslate"] > 0
    assert root_after["minecraft:grass_block"] > 0
    assert local_after["minecraft:cobblestone"] > 0
    assert local_after["minecraft:grass_block"] == 0
    assert local_after["minecraft:mycelium"] > 0


def test_pattern_replacement_can_ignore_captured_placeholder(
    tmp_path: Path,
    structure_dir: Path,
) -> None:
    source = find_structure_with_blocks(
        structure_dir,
        {"minecraft:orange_terracotta"},
        under="trail_ruins/buildings",
    )
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    copied = copy_structure(source, structure_dir, input_dir)

    write_config(
        input_dir,
        """
    [replace-block-pattern]
    "minecraft:{color}_terracotta" = "minecraft:white_concrete"
    """,
    )

    before = palette_counter(copied)
    matched_blocks = {
        block
        for block in before
        if block.startswith("minecraft:") and block.endswith("_terracotta")
    }
    matched_count = sum(before[block] for block in matched_blocks)

    start(BZArgs(target_dir=input_dir, output_dir=output_dir))

    after = palette_counter(output_dir / copied.relative_to(input_dir))

    assert matched_count > 0
    for block in matched_blocks:
        assert after[block] == 0
    assert (
        after["minecraft:white_concrete"]
        == before["minecraft:white_concrete"] + matched_count
    )


def test_block_pattern_replacement_potted_plants(
    tmp_path: Path,
    structure_dir: Path,
) -> None:
    source = structure_dir / "woodland_mansion" / "1x1_a1.nbt"
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    copied = copy_structure(source, structure_dir, input_dir)

    before = palette_counter(copied)
    potted_blocks = potted_plant_blocks(copied)
    replacement = "minecraft:potted_pale_oak_sapling"

    write_config(
        input_dir,
        """
    [replace-block-pattern]
    "minecraft:potted_{plant}" = "minecraft:potted_pale_oak_sapling"
    """,
    )

    assert potted_blocks == {
        "minecraft:potted_allium",
        "minecraft:potted_azure_bluet",
        "minecraft:potted_blue_orchid",
        "minecraft:potted_oxeye_daisy",
    }

    start(BZArgs(target_dir=input_dir, output_dir=output_dir))

    after = palette_counter(output_dir / copied.relative_to(input_dir))

    for block in potted_blocks:
        assert after[block] == 0
    assert after[replacement] == sum(before[block] for block in potted_blocks)


def test_string_replacement_hardcoded_chests(
    tmp_path: Path,
    structure_dir: Path,
) -> None:
    source = structure_dir / "woodland_mansion" / "1x1_b5.nbt"
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    copied = copy_structure(source, structure_dir, input_dir)

    before_items = item_id_counter(copied)
    before_blocks = palette_counter(copied)

    write_config(
        input_dir,
        """
    [replace-block]
    "minecraft:birch_planks" = "minecraft:dark_oak_planks"

    [replace-string]
    "minecraft:allium" = "minecraft:poppy"
    """,
    )

    assert before_items["minecraft:allium"] == 8

    start(BZArgs(target_dir=input_dir, output_dir=output_dir))

    out_file = output_dir / copied.relative_to(input_dir)
    after_items = item_id_counter(out_file)
    after_blocks = palette_counter(out_file)

    assert (
        after_blocks["minecraft:dark_oak_planks"]
        == before_blocks["minecraft:birch_planks"]
    )
    assert after_items["minecraft:allium"] == 0
    assert after_items["minecraft:poppy"] == 8


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

    with pytest.raises(RuntimeError):
        start(BZArgs(target_dir=input_dir, output_dir=output_dir))

    assert not (output_dir / copied.relative_to(input_dir)).exists()
