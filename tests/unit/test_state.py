from main import BZConfig, BZRules, merge_state, state_for_children
from tests.unit.helpers import make_state


class TestMergeState:
  def test_inherit_true_merges_parent_and_local_rules(self):
    base = make_state(
      replace_block={
        "minecraft:stone": "minecraft:deepslate",
        "minecraft:oak_planks": "minecraft:birch_planks",
      },
      replace_block_pattern={
        "minecraft:oak_{part}": "minecraft:dark_oak_{part}",
      },
    )
    config = BZConfig(
      replace_block={
        "minecraft:oak_planks": "minecraft:spruce_planks",
      },
      replace_string={
        "minecraft:cod": "minecraft:salmon",
      },
    )

    state = merge_state(base, config)

    assert state.rules.replace_block == {
      "minecraft:stone": "minecraft:deepslate",
      "minecraft:oak_planks": "minecraft:spruce_planks",
    }
    assert state.rules.replace_block_pattern == {
      "minecraft:oak_{part}": "minecraft:dark_oak_{part}",
    }
    assert state.rules.replace_string == {
      "minecraft:cod": "minecraft:salmon",
    }

  def test_inherit_false_replaces_parent_rules_with_local_rules(self):
    base = make_state(
      replace_block={
        "minecraft:stone": "minecraft:deepslate",
        "minecraft:oak_planks": "minecraft:birch_planks",
      },
      replace_block_pattern={
        "minecraft:oak_{part}": "minecraft:dark_oak_{part}",
      },
    )
    config = BZConfig(
      inherit=False,
      replace_block={
        "minecraft:oak_planks": "minecraft:spruce_planks",
      },
    )

    state = merge_state(base, config)

    assert state.rules.replace_block == {
      "minecraft:oak_planks": "minecraft:spruce_planks",
    }
    assert state.rules.replace_block_pattern == {}
    assert state.rules.replace_string == {}


class TestStateForChildren:
  def test_no_local_config_passes_local_state_to_children(self):
    parent = make_state(replace_block={"minecraft:stone": "minecraft:deepslate"})
    local = make_state(replace_block={"minecraft:dirt": "minecraft:grass_block"})

    child_state = state_for_children(parent, local, None)

    assert child_state.rules == local.rules

  def test_recursive_true_passes_local_state_to_children(self):
    parent = make_state(replace_block={"minecraft:stone": "minecraft:deepslate"})
    local = make_state(replace_block={"minecraft:dirt": "minecraft:grass_block"})

    child_state = state_for_children(parent, local, BZConfig(recursive=True))

    assert child_state.rules == local.rules

  def test_recursive_false_inherit_true_passes_parent_state_to_children(self):
    parent = make_state(replace_block={"minecraft:stone": "minecraft:deepslate"})
    local = make_state(replace_block={"minecraft:dirt": "minecraft:grass_block"})

    child_state = state_for_children(
      parent,
      local,
      BZConfig(recursive=False, inherit=True),
    )

    assert child_state.rules == parent.rules

  def test_recursive_false_inherit_false_passes_empty_rules_to_children(self):
    parent = make_state(replace_block={"minecraft:stone": "minecraft:deepslate"})
    local = make_state(replace_block={"minecraft:dirt": "minecraft:grass_block"})

    child_state = state_for_children(
      parent,
      local,
      BZConfig(recursive=False, inherit=False),
    )

    assert child_state.rules == BZRules()
