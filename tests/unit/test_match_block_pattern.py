import pytest
from main import match_block_pattern


class TestMatchBlockPattern:
    def test_simple_placeholder_match(self):
        patterns = {"minecraft:oak_{part}": "minecraft:dark_oak_{part}"}
        result, matches = match_block_pattern("minecraft:oak_stairs", patterns)
        assert result == "minecraft:dark_oak_stairs"
        assert matches == ["minecraft:oak_{part}"]

    def test_no_match(self):
        patterns = {"minecraft:oak_{part}": "minecraft:dark_oak_{part}"}
        result, matches = match_block_pattern("minecraft:birch_stairs", patterns)
        assert result is None
        assert matches == []

    def test_multiple_placeholders(self):
        patterns = {"{namespace}:{wood}_planks": "{namespace}:dark_{wood}_planks"}
        result, matches = match_block_pattern("minecraft:oak_planks", patterns)
        assert result == "minecraft:dark_oak_planks"
        assert matches == ["{namespace}:{wood}_planks"]

    def test_exact_pattern_no_placeholders(self):
        patterns = {"minecraft:stone": "minecraft:deepslate"}
        result, matches = match_block_pattern("minecraft:stone", patterns)
        assert result == "minecraft:deepslate"
        assert matches == ["minecraft:stone"]

    def test_multiple_patterns_match(self):
        patterns = {
            "minecraft:oak_{part}": "minecraft:dark_oak_{part}",
            "minecraft:{wood}_stairs": "minecraft:{wood}_slab",
        }
        result, matches = match_block_pattern("minecraft:oak_stairs", patterns)
        # Both patterns match
        assert len(matches) == 2
        assert "minecraft:oak_{part}" in matches
        assert "minecraft:{wood}_stairs" in matches
        # Result is from the first matching pattern
        assert result is not None

    def test_empty_patterns(self):
        result, matches = match_block_pattern("minecraft:oak_stairs", {})
        assert result is None
        assert matches == []

    def test_special_regex_characters_escaped(self):
        # Ensure colons and other special chars are matched literally
        patterns = {"minecraft:oak_{part}": "test:{part}"}
        result, matches = match_block_pattern("minecraft:oak_door", patterns)
        assert result == "test:door"

    def test_placeholder_captures_underscores(self):
        patterns = {"minecraft:{block}": "modded:{block}"}
        result, matches = match_block_pattern("minecraft:dark_oak_planks", patterns)
        assert result == "modded:dark_oak_planks"

    def test_placeholder_at_start(self):
        patterns = {"{namespace}:stone": "{namespace}:deepslate"}
        result, matches = match_block_pattern("minecraft:stone", patterns)
        assert result == "minecraft:deepslate"

    def test_placeholder_at_end(self):
        patterns = {"minecraft:oak_{x}": "minecraft:birch_{x}"}
        result, matches = match_block_pattern("minecraft:oak_log", patterns)
        assert result == "minecraft:birch_log"

    def test_no_result_group(self):
        patterns = {"minecraft:oak_{part}": "minecraft:dark_oak"}
        result, matches = match_block_pattern("minecraft:oak_stairs", patterns)
        assert result == "minecraft:dark_oak"
        assert matches == ["minecraft:oak_{part}"]

    def test_extra_group(self):
        patterns = {"minecraft:oak_{part}": "minecraft:dark_oak_{not_used}"}
        result, matches = match_block_pattern("minecraft:oak_stairs", patterns)
