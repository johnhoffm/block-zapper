from pathlib import Path

from main import (
    BZReplacement,
    BZTreeDirectory,
    BZTreeFile,
    add_tree_directory,
    add_tree_file_replacements,
    create_tree_summary,
    render_tree_summary,
    tree_directory_id,
    tree_file_id,
    tree_replacement_id,
)


def test_tree_summary_keeps_structured_node_data():
    tree, root_node_id = create_tree_summary(Path("/structures"))

    file_node_id = add_tree_file_replacements(
        tree,
        root_node_id,
        Path("/structures/root.nbt"),
        [("minecraft:stone", "minecraft:deepslate")],
    )

    assert tree.get_node(root_node_id).data == BZTreeDirectory(Path("/structures"))
    assert tree.get_node(file_node_id).data == BZTreeFile(Path("/structures/root.nbt"))
    assert tree.get_node(tree_replacement_id(Path("/structures/root.nbt"), 0)).data == (
        BZReplacement(
            old_block="minecraft:stone",
            new_block="minecraft:deepslate",
        )
    )


def test_render_tree_summary_outputs_plain_text_tree():
    tree, root_node_id = create_tree_summary(Path("/structures"))
    add_tree_file_replacements(
        tree,
        root_node_id,
        Path("/structures/root.nbt"),
        [("minecraft:stone", "minecraft:deepslate")],
    )

    child_node_id = add_tree_directory(tree, root_node_id, Path("/structures/houses"))
    add_tree_file_replacements(
        tree,
        child_node_id,
        Path("/structures/houses/cottage.nbt"),
        [
            ("minecraft:oak_log", "minecraft:spruce_log"),
            ("minecraft:oak_planks", "minecraft:spruce_planks"),
        ],
    )

    output = render_tree_summary(tree)

    assert output == (
        "/structures\n"
        "|-- root.nbt\n"
        "|   +-- minecraft:stone -> minecraft:deepslate\n"
        "+-- houses/\n"
        "    +-- cottage.nbt\n"
        "        |-- minecraft:oak_log -> minecraft:spruce_log\n"
        "        +-- minecraft:oak_planks -> minecraft:spruce_planks\n"
    )
    assert tree.get_node(tree_directory_id(Path("/structures/houses"))).tag == "houses/"
    assert (
        tree.get_node(tree_file_id(Path("/structures/houses/cottage.nbt"))).tag
        == "cottage.nbt"
    )
