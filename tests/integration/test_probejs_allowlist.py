from __future__ import annotations

from pathlib import Path

from main import BZArgs, start
from tests.integration.helpers import (
    copy_structure_dir,
    counter_for_paths,
    item_id_counter,
    palette_counter,
    transformed_or_original_paths,
    write_config,
)


def test_replace_plains_village_blocks_with_probejs_allowlist(
    tmp_path: Path,
    structure_dir: Path,
) -> None:
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    copied = copy_structure_dir("village/plains", structure_dir, input_dir)

    write_config(
        input_dir,
        """
    [replace-block]
    "minecraft:oak_planks" = "minecraft:dark_oak_planks"
    """,
    )

    probejs_registry = input_dir / ".probe/@special/types/RegistryTypes/index.d.ts"
    probejs_registry.parent.mkdir(parents=True)
    probejs_registry.write_text(
        """
declare module "@special/types/RegistryTypes" {
  export type Block = "minecraft:air" | "minecraft:cobblestone" | "minecraft:oak_log" | "minecraft:oak_planks" | "minecraft:oak_stairs" | "minecraft:dark_oak_planks";
}
""",
        encoding="utf-8",
    )

    before = counter_for_paths(copied, palette_counter)

    start(
        BZArgs(
            target_dir=input_dir,
            output_dir=output_dir,
            allowlist=probejs_registry,
        )
    )

    after = counter_for_paths(
        transformed_or_original_paths(copied, input_dir, output_dir),
        palette_counter,
    )

    assert before["minecraft:oak_planks"] > 0
    assert after["minecraft:oak_planks"] == 0
    assert after["minecraft:dark_oak_planks"] == (
        before["minecraft:dark_oak_planks"] + before["minecraft:oak_planks"]
    )


def test_replace_woodland_mansion_items_with_probejs_allowlist(
    tmp_path: Path,
    structure_dir: Path,
) -> None:
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

    probejs_registry = input_dir / ".probe/@special/types/RegistryTypes/index.d.ts"
    probejs_registry.parent.mkdir(parents=True)
    probejs_registry.write_text(
        """
declare module "@special/types/RegistryTypes" {
  export type Block = "minecraft:air";
  export type Item = "minecraft:allium" | "minecraft:poppy";
}
""",
        encoding="utf-8",
    )

    before = counter_for_paths(copied, item_id_counter)

    start(
        BZArgs(
            target_dir=input_dir,
            output_dir=output_dir,
            allowlist=probejs_registry,
        )
    )

    after = counter_for_paths(
        transformed_or_original_paths(copied, input_dir, output_dir),
        item_id_counter,
    )

    assert before["minecraft:allium"] == 8
    assert after["minecraft:allium"] == 0
    assert after["minecraft:poppy"] == 8
