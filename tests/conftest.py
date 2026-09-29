import shutil
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def minimal(tmp_path) -> Path:
    """A private copy of the minimal workbook, so tests can write next to it."""
    target = tmp_path / "minimal.twb"
    shutil.copy(FIXTURES / "minimal.twb", target)
    return target
