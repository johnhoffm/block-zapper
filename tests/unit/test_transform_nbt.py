import nbtlib

from main import BZReplacement, BZReplacementKind, replace_nbt_strings, transform_nbt
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


class TestTransformNbt:
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
