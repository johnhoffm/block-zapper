from __future__ import annotations

import os
import shutil
from collections import Counter
from collections.abc import Callable
from pathlib import Path

import nbtlib

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


def cached_structure_dir() -> Path:
    return Path(os.environ.get("BZ_MCMETA_STRUCTURE_DIR", DEFAULT_STRUCTURE_DIR))


def palette_blocks(path: Path) -> list[str]:
    root = nbtlib.load(path)
    if "palette" in root:
        palettes = [root["palette"]]
    elif "palettes" in root:
        palettes = root["palettes"]
    else:
        return []

    return [
        str(entry["Name"])
        for palette in palettes
        for entry in palette
        if "Name" in entry
    ]


def palette_counter(path: Path) -> Counter[str]:
    return Counter(palette_blocks(path))


# Do not use - use palette counter instead
def block_placement_counter(path: Path) -> Counter[str]:
    root = nbtlib.load(path)
    if "palette" in root:
        palette = [str(entry.get("Name", "")) for entry in root["palette"]]
    elif "palettes" in root and root["palettes"]:
        palette = [str(entry.get("Name", "")) for entry in root["palettes"][0]]
    else:
        return Counter()

    blocks: Counter[str] = Counter()
    for block in root.get("blocks", []):
        state = int(block.get("state", -1))
        if 0 <= state < len(palette):
            blocks[palette[state]] += 1
    return blocks


def item_id_counter(path: Path) -> Counter[str]:
    items: Counter[str] = Counter()
    root = nbtlib.load(path)
    for block in root.get("blocks", []):
        block_nbt = block.get("nbt")
        if not block_nbt:
            continue
        for item in block_nbt.get("Items", []):
            if "id" in item:
                items[str(item["id"])] += int(item.get("count", 1))
    return items


def copy_structure_dir(
    relative_dir: str,
    structure_dir: Path,
    input_dir: Path,
) -> list[Path]:
    source = structure_dir / relative_dir
    if not source.is_dir():
        raise AssertionError(f"Missing cached Minecraft structure dir: {relative_dir}")

    target = input_dir / relative_dir
    shutil.copytree(source, target)
    return sorted(target.rglob("*.nbt"))


def structure_paths(path: Path) -> list[Path]:
    return sorted(path.rglob("*.nbt"))


def counter_for_paths(
    paths: list[Path],
    counter: Callable[[Path], Counter[str]],
) -> Counter[str]:
    total: Counter[str] = Counter()
    for path in paths:
        total.update(counter(path))
    return total


def transformed_or_original_paths(
    paths: list[Path],
    input_dir: Path,
    output_dir: Path,
) -> list[Path]:
    transformed = []
    for path in paths:
        out_path = output_dir / path.relative_to(input_dir)
        transformed.append(out_path if out_path.exists() else path)
    return transformed


def write_config(path: Path, body: str) -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / ".bz.toml").write_text(body.strip() + "\n", encoding="utf-8")
