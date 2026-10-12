import json
import sys
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

REPO = Path(__file__).resolve().parents[1]


def test_committed_openapi_matches_the_app():
    """If this fails, run: python scripts/export_openapi.py && (cd packages/api-client && npm run generate)"""
    sys.path.insert(0, str(REPO / "scripts"))
    try:
        import export_openapi
    finally:
        sys.path.pop(0)
    committed = (REPO / "packages/api-client/openapi.json").read_text(encoding="utf-8")
    assert json.loads(committed) == json.loads(export_openapi.render())
