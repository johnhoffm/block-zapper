from pathlib import Path

from main import BZAllowlist, BZRules, BZRun, BZState


def make_state(
    replace_block: dict[str, str] | None = None,
    replace_block_pattern: dict[str, str] | None = None,
    replace_block_regex: dict[str, str] | None = None,
    replace_string: dict[str, str] | None = None,
    allow_overlaps: bool = False,
    allowlist: BZAllowlist | None = None,
) -> BZState:
    return BZState(
        rules=BZRules(
            replace_block=replace_block or {},
            replace_block_pattern=replace_block_pattern or {},
            replace_block_regex=replace_block_regex or {},
            replace_string=replace_string or {},
        ),
        run=BZRun(
            output_root_dir=Path("."),
            input_root_dir=Path("."),
            dry_run=False,
            allow_overlaps=allow_overlaps,
            allowlist=allowlist,
        ),
        tree=None,
    )
