import nbtlib
import pytest

from main import BZAllowlist, BZReplacement, BZReplacementKind, replace_nbt_strings, transform_nbt
from tests.unit.helpers import make_state


class TestReplaceNbtStrings:
  def test_replaces_nested_item_id_strings(self):
    payload = nbtlib.Compound({
      "Items": nbtlib.tag.List[nbtlib.tag.Compound]([
        nbtlib.tag.Compound({
          "id": nbtlib.tag.String("minecraft:allium"),
        }),
        nbtlib.tag.Compound({
          "id": nbtlib.tag.String("minecraft:bone"),
        }),
      ]),
      "Item": nbtlib.tag.Compound({
        "id": nbtlib.tag.String("minecraft:allium"),
      }),
    })

    replacements = replace_nbt_strings(
      payload,
      {"minecraft:allium": "minecraft:poppy"},
      "blocks[0].nbt",
    )

    assert replacements == [
      BZReplacement(
        kind=BZReplacementKind.STRING,
        old_value="minecraft:allium",
        new_value="minecraft:poppy",
        location="blocks[0].nbt.Items[0].id",
      ),
      BZReplacement(
        kind=BZReplacementKind.STRING,
        old_value="minecraft:allium",
        new_value="minecraft:poppy",
        location="blocks[0].nbt.Item.id",
      ),
    ]
    assert str(payload["Items"][0]["id"]) == "minecraft:poppy"
    assert str(payload["Items"][1]["id"]) == "minecraft:bone"
    assert str(payload["Item"]["id"]) == "minecraft:poppy"

  def test_rejects_item_not_in_allowlist(self):
    payload = nbtlib.Compound({
      "id": nbtlib.tag.String("minecraft:allium"),
    })

    with pytest.raises(RuntimeError):
      replace_nbt_strings(
        payload,
        {"minecraft:allium": "minecraft:poppy"},
        "blocks[0].nbt",
        BZAllowlist(blocks=set(), items={"minecraft:allium"}),
      )

    assert str(payload["id"]) == "minecraft:allium"


class TestTransformNbt:
  def test_block_replacement_preserves_palette_properties(self):
    root = nbtlib.Compound({
      "palette": nbtlib.tag.List[nbtlib.tag.Compound]([
        nbtlib.tag.Compound({
          "Name": nbtlib.tag.String("minecraft:oak_stairs"),
          "Properties": nbtlib.tag.Compound({
            "facing": nbtlib.tag.String("north"),
            "half": nbtlib.tag.String("bottom"),
            "shape": nbtlib.tag.String("straight"),
          }),
        }),
      ]),
      "blocks": nbtlib.tag.List[nbtlib.tag.Compound]([]),
    })
    state = make_state(replace_block={
      "minecraft:oak_stairs": "minecraft:dark_oak_stairs",
    })

    replacements = transform_nbt(root, state)

    entry = root["palette"][0]
    assert str(entry["Name"]) == "minecraft:dark_oak_stairs"
    assert dict(entry["Properties"]) == {
      "facing": "north",
      "half": "bottom",
      "shape": "straight",
    }
    assert replacements == [
      BZReplacement(
        kind=BZReplacementKind.BLOCK,
        old_value="minecraft:oak_stairs",
        new_value="minecraft:dark_oak_stairs",
        location="palette[0].Name",
      ),
    ]

  def test_replaces_blocks_in_plural_palettes(self):
    root = nbtlib.Compound({
      "palettes": nbtlib.tag.List[nbtlib.tag.List[nbtlib.tag.Compound]]([
        nbtlib.tag.List[nbtlib.tag.Compound]([
          nbtlib.tag.Compound({
            "Name": nbtlib.tag.String("minecraft:oak_planks"),
          }),
        ]),
        nbtlib.tag.List[nbtlib.tag.Compound]([
          nbtlib.tag.Compound({
            "Name": nbtlib.tag.String("minecraft:spruce_planks"),
          }),
        ]),
      ]),
      "blocks": nbtlib.tag.List[nbtlib.tag.Compound]([]),
    })
    state = make_state(replace_block_pattern={
      "minecraft:{wood}_planks": "minecraft:bedrock",
    })

    replacements = transform_nbt(root, state)

    assert str(root["palettes"][0][0]["Name"]) == "minecraft:bedrock"
    assert str(root["palettes"][1][0]["Name"]) == "minecraft:bedrock"
    assert replacements == [
      BZReplacement(
        kind=BZReplacementKind.BLOCK,
        old_value="minecraft:oak_planks",
        new_value="minecraft:bedrock",
        location="palettes[0][0].Name",
      ),
      BZReplacement(
        kind=BZReplacementKind.BLOCK,
        old_value="minecraft:spruce_planks",
        new_value="minecraft:bedrock",
        location="palettes[1][0].Name",
      ),
    ]

  def test_string_replacement_does_not_modify_palette_block_states(self):
    root = nbtlib.Compound({
      "palette": nbtlib.tag.List[nbtlib.tag.Compound]([
        nbtlib.tag.Compound({
          "Name": nbtlib.tag.String("minecraft:skeleton_skull"),
          "Properties": nbtlib.tag.Compound({
            "rotation": nbtlib.tag.String("6"),
          }),
        }),
      ]),
      "blocks": nbtlib.tag.List[nbtlib.tag.Compound]([]),
    })

    # This should be a no-op
    state = make_state(replace_string={
      "rotation": "powered",
      "6": "7",
    })

    replacements = transform_nbt(root, state)

    properties = root["palette"][0]["Properties"]
    assert replacements == []
    assert "powered" not in properties
    assert "rotation" in properties
    assert "7" not in properties
    assert str(properties["rotation"]) == "6"
