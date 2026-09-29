"""Round-trip every workbook in the local corpus. Skipped unless TAM_CORPUS points at a folder.

The corpus holds real workbooks and never enters the repo, so this runs locally, not in CI.
"""

import os
from pathlib import Path

import pytest

from tableau_authoring_mcp.cli import _files
from tableau_authoring_mcp.twb.document import Document

CORPUS = os.environ.get("TAM_CORPUS")
pytestmark = [pytest.mark.corpus, pytest.mark.skipif(not CORPUS, reason="set TAM_CORPUS to a folder")]


def corpus_files() -> list[Path]:
    return _files(CORPUS.split(os.pathsep)) if CORPUS else []


@pytest.mark.parametrize("path", corpus_files(), ids=lambda p: p.name)
@pytest.mark.parametrize("level", ["root", "structure"])
def test_corpus_round_trip(path, level):
    doc = Document.load(path)
    doc.force_reemit(level)
    assert doc.to_bytes() == doc.raw
