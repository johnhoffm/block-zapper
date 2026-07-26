from pathlib import Path

import pytest

from tests.integration.helpers import cached_structure_dir


@pytest.fixture(scope="session")
def structure_dir() -> Path:
    path = cached_structure_dir()
    if not path.is_dir():
        pytest.skip(
            "Minecraft structure cache not found. Run "
            "`scripts/cache-mcmeta-structures.sh` or set BZ_MCMETA_STRUCTURE_DIR."
        )
    return path
