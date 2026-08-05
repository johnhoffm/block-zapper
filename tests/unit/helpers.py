from pathlib import Path

from main import BZAllowlist, BZReplacementRules, BZRules, BZRun, BZState


def make_state(
    replace_block: dict[str, str] | None = None,
    replace_block_pattern: dict[str, str] | None = None,
    replace_block_regex: dict[str, str] | None = None,
    replace_string: dict[str, str] | None = None,
    replace_string_pattern: dict[str, str] | None = None,
    replace_string_regex: dict[str, str] | None = None,
    allow_overlaps: bool = False,
    allowlist: BZAllowlist | None = None,
) -> BZState:
    return BZState(
        rules=BZRules(
            block=BZReplacementRules(
                simple=replace_block or {},
                pattern=replace_block_pattern or {},
                regex=replace_block_regex or {},
            ),
            string=BZReplacementRules(
                simple=replace_string or {},
                pattern=replace_string_pattern or {},
                regex=replace_string_regex or {},
            ),
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
