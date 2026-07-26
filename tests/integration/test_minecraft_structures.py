from __future__ import annotations

from pathlib import Path

import pytest

from main import BZArgs, start
from tests.integration.helpers import (
    copy_structure_dir,
    counter_for_paths,
    item_id_counter,
    palette_counter,
    structure_paths,
    transformed_or_original_paths,
    write_config,
)


def test_replace_plains_village_replace_oak_dark_oak(
    tmp_path: Path,
    structure_dir: Path,
) -> None:
    """
    input/
      .bz.toml             # oak* -> dark_oak*
      village/
        plains/
          ...
    """

    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    copied = []
    copied.extend(copy_structure_dir("village/plains", structure_dir, input_dir))

    write_config(
        input_dir,
        """
    [replace-block-pattern]
    "minecraft:oak{whatever}" = "minecraft:dark_oak{whatever}"
    """,
    )

    before = counter_for_paths(copied, palette_counter)

    start(BZArgs(target_dir=input_dir, output_dir=output_dir))

    after = counter_for_paths(
        transformed_or_original_paths(copied, input_dir, output_dir),
        palette_counter,
    )

    assert before["minecraft:oak_planks"] > 0
    assert before["minecraft:oak_stairs"] > 0

    assert after["minecraft:oak_planks"] == 0
    assert after["minecraft:dark_oak_planks"] == before["minecraft:oak_planks"]

    assert after["minecraft:oak_stairs"] == 0
    assert after["minecraft:dark_oak_stairs"] == before["minecraft:oak_stairs"]


def test_replace_plains_village_houses_stone_and_oak(
    tmp_path: Path,
    structure_dir: Path,
) -> None:
    """
    input/
      .bz.toml             # cobblestone -> deepslate, oak_* -> dark_oak_*
      village/
        plains/
          houses/
            ...
    """

    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    copied = copy_structure_dir("village/plains/houses", structure_dir, input_dir)

    write_config(
        input_dir,
        """
    [replace-block]
    "minecraft:cobblestone" = "minecraft:deepslate"

    [replace-block-pattern]
    "minecraft:oak_{part}" = "minecraft:dark_oak_{part}"
    """,
    )

    before = counter_for_paths(copied, palette_counter)

    start(BZArgs(target_dir=input_dir, output_dir=output_dir))

    after_files = transformed_or_original_paths(copied, input_dir, output_dir)
    after = counter_for_paths(after_files, palette_counter)

    assert before["minecraft:oak_stairs"] > 0
    assert before["minecraft:cobblestone"] > 0
    assert after["minecraft:oak_stairs"] == 0
    assert (
        after["minecraft:dark_oak_stairs"]
        == before["minecraft:dark_oak_stairs"] + before["minecraft:oak_stairs"]
    )
    assert after["minecraft:cobblestone"] == 0
    assert after["minecraft:deepslate"] == (
        before["minecraft:deepslate"] + before["minecraft:cobblestone"]
    )


def test_plains_village_hay_to_kelp_dry_run(
    tmp_path: Path,
    structure_dir: Path,
) -> None:
    """
    input/
      .bz.toml             # hay_block -> dried_kelp_block, dry run only
      village/
        plains/
          houses/
            ...
    """

    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    copied = copy_structure_dir("village/plains/houses", structure_dir, input_dir)

    write_config(
        input_dir,
        """
    [replace-block]
    "minecraft:hay_block" = "minecraft:dried_kelp_block"
    """,
    )

    before = counter_for_paths(copied, palette_counter)

    start(
        BZArgs(
            target_dir=input_dir,
            output_dir=output_dir,
            dry_run=True,
        )
    )

    after = counter_for_paths(copied, palette_counter)

    assert before["minecraft:hay_block"] > 0
    assert after["minecraft:hay_block"] == before["minecraft:hay_block"]
    assert after["minecraft:dried_kelp_block"] == before["minecraft:dried_kelp_block"]
    assert not output_dir.exists()


def test_taiga_village_cobblestone_inherit_false(
    tmp_path: Path,
    structure_dir: Path,
) -> None:
    """
    input/
      village/
        taiga/
          .bz.toml       # cobblestone -> deepslate
          houses/
            .bz.toml     # inherit = false
          zombie/
            ...
    """

    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    copy_structure_dir("village/taiga", structure_dir, input_dir)
    houses_dir = input_dir / "village/taiga/houses"
    zombie_dir = input_dir / "village/taiga/zombie"

    write_config(
        input_dir / "village/taiga",
        """
    [replace-block]
    "minecraft:cobblestone" = "minecraft:deepslate"
    """,
    )
    write_config(
        input_dir / "village/taiga/houses",
        """
    inherit = false
    """,
    )

    houses = structure_paths(houses_dir)
    zombie = structure_paths(zombie_dir)
    houses_before = counter_for_paths(houses, palette_counter)
    zombie_before = counter_for_paths(zombie, palette_counter)

    start(BZArgs(target_dir=input_dir, output_dir=output_dir))

    houses_after = counter_for_paths(
        transformed_or_original_paths(houses, input_dir, output_dir),
        palette_counter,
    )
    zombie_after = counter_for_paths(
        transformed_or_original_paths(zombie, input_dir, output_dir),
        palette_counter,
    )

    assert houses_before["minecraft:cobblestone"] > 0
    assert zombie_before["minecraft:cobblestone"] > 0

    assert (
        houses_after["minecraft:cobblestone"] == houses_before["minecraft:cobblestone"]
    )
    assert houses_after["minecraft:deepslate"] == houses_before["minecraft:deepslate"]

    assert zombie_after["minecraft:cobblestone"] == 0
    assert zombie_after["minecraft:deepslate"] == (
        zombie_before["minecraft:deepslate"] + zombie_before["minecraft:cobblestone"]
    )


def test_trail_ruins_replace_terracotta_pattern_to_empty(
    tmp_path: Path,
    structure_dir: Path,
) -> None:
    """
    input/
      .bz.toml             # *_terracotta -> diamond_block
      trail_ruins/
        buildings/
          ...
    """

    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    copied = copy_structure_dir("trail_ruins/buildings", structure_dir, input_dir)

    write_config(
        input_dir,
        """
    [replace-block-pattern]
    "minecraft:{color}_terracotta" = "minecraft:diamond_block"
    """,
    )

    before = counter_for_paths(copied, palette_counter)

    # These are the only terracotta blocks that appear in trail ruins
    terracotta = [
        "minecraft:black_glazed_terracotta",
        "minecraft:blue_terracotta",
        "minecraft:brown_terracotta",
        "minecraft:cyan_terracotta",
        "minecraft:gray_terracotta",
        "minecraft:light_blue_glazed_terracotta",
        "minecraft:light_gray_glazed_terracotta",
        "minecraft:light_gray_terracotta",
        "minecraft:orange_glazed_terracotta",
        "minecraft:orange_terracotta",
        "minecraft:red_terracotta",
        "minecraft:white_terracotta",
        "minecraft:yellow_glazed_terracotta",
        "minecraft:yellow_terracotta",
    ]

    terracotta_sum = sum(before[block] for block in terracotta)

    start(BZArgs(target_dir=input_dir, output_dir=output_dir))

    after = counter_for_paths(
        transformed_or_original_paths(copied, input_dir, output_dir),
        palette_counter,
    )

    assert terracotta_sum > 0
    for block in terracotta:
        assert before[block] > 0
        assert after[block] == 0
    assert after["minecraft:diamond_block"] == (
        before["minecraft:diamond_block"] + terracotta_sum
    )


def test_shipwreck_replace_birch_wood(
    tmp_path: Path,
    structure_dir: Path,
) -> None:
    """
    Shipwrecks use "palettes" plural instead of palette singular.

    input/
      .bz.toml             # birch_planks -> diamond_block
      shipwreck/
        ...
    """

    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    copied = copy_structure_dir("shipwreck", structure_dir, input_dir)

    write_config(
        input_dir,
        """
    [replace-block]
    "minecraft:birch_planks" = "minecraft:diamond_block"
    """,
    )

    before = counter_for_paths(copied, palette_counter)

    start(BZArgs(target_dir=input_dir, output_dir=output_dir))

    after = counter_for_paths(
        transformed_or_original_paths(copied, input_dir, output_dir),
        palette_counter,
    )

    assert before["minecraft:birch_planks"] > 0

    assert after["minecraft:birch_planks"] == 0
    assert after["minecraft:diamond_block"] == before["minecraft:birch_planks"]


def test_woodland_mansion_replace_potted_plants(
    tmp_path: Path,
    structure_dir: Path,
) -> None:
    """
    Different potted plants are their own block.

    input/
      .bz.toml             # potted_* -> potted_pale_oak_sapling
      woodland_mansion/
        ...
    """

    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    copied = copy_structure_dir("woodland_mansion", structure_dir, input_dir)

    write_config(
        input_dir,
        """
    [replace-block-pattern]
    "minecraft:potted_{plant}" = "minecraft:potted_pale_oak_sapling"
    """,
    )

    before = counter_for_paths(copied, palette_counter)

    start(BZArgs(target_dir=input_dir, output_dir=output_dir))

    after = counter_for_paths(
        transformed_or_original_paths(copied, input_dir, output_dir),
        palette_counter,
    )

    assert before["minecraft:potted_allium"] > 0
    assert before["minecraft:potted_white_tulip"] > 0

    assert after["minecraft:potted_allium"] == 0
    assert after["minecraft:potted_white_tulip"] == 0
    assert (
        after["minecraft:potted_pale_oak_sapling"]
        > before["minecraft:potted_pale_oak_sapling"]
    )


def test_woodland_mansion_allium_chest(
    tmp_path: Path,
    structure_dir: Path,
) -> None:
    """
    Woodland mansion allium chest is hardcoded in the structure, not a loot table.
    It always has 8 alliums.

    input/
      .bz.toml             # allium -> poppy
      woodland_mansion/
        ...
    """

    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    copied = copy_structure_dir("woodland_mansion", structure_dir, input_dir)

    write_config(
        input_dir,
        """
    [replace-string]
    "minecraft:allium" = "minecraft:poppy"
    """,
    )

    before_items = counter_for_paths(copied, item_id_counter)

    assert before_items["minecraft:allium"] == 8

    start(BZArgs(target_dir=input_dir, output_dir=output_dir))

    after_files = transformed_or_original_paths(copied, input_dir, output_dir)
    after_items = counter_for_paths(after_files, item_id_counter)

    assert after_items["minecraft:allium"] == 0
    assert after_items["minecraft:poppy"] == 8


def test_plains_village_houses_errors_no_overlap(
    tmp_path: Path,
    structure_dir: Path,
) -> None:
    """
    input/
      .bz.toml             # oak_trapdoor overlaps with oak_{part}
      village/
        plains/
          houses/
            ...
    """

    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    copied = copy_structure_dir("village/plains/houses", structure_dir, input_dir)

    write_config(
        input_dir,
        """
    [replace-block]
    "minecraft:oak_trapdoor" = "minecraft:birch_trapdoor"

    [replace-block-pattern]
    "minecraft:oak_{part}" = "minecraft:dark_oak_{part}"
    """,
    )

    before = counter_for_paths(copied, palette_counter)

    assert before["minecraft:oak_trapdoor"] > 0

    with pytest.raises(RuntimeError):
        start(BZArgs(target_dir=input_dir, output_dir=output_dir))

    assert not output_dir.exists()
