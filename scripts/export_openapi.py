"""Write the API's OpenAPI schema to packages/api-client/openapi.json.

    python scripts/export_openapi.py            # write
    python scripts/export_openapi.py --check    # exit 1 if the committed file is out of date (used by CI)

The TypeScript client types are generated from that file (`npm run generate` in packages/api-client).
"""
import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.api import app  # noqa: E402

TARGET = PROJECT_ROOT / "packages" / "api-client" / "openapi.json"


# Python 3.13 renamed these HTTPStatus phrases, which FastAPI copies into the schema. Pin them so the
# output is the same on every Python version.
STATUS_PHRASES = {"413": "Request Entity Too Large", "422": "Unprocessable Entity"}


def render() -> str:
    schema = app.openapi()
    for path_item in schema.get("paths", {}).values():
        for operation in path_item.values():
            for code, phrase in STATUS_PHRASES.items():
                response = operation.get("responses", {}).get(code)
                if response is not None:
                    response["description"] = phrase
    return json.dumps(schema, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    text = render()
    if args.check:
        if not TARGET.exists() or TARGET.read_text(encoding="utf-8") != text:
            print(f"{TARGET.relative_to(PROJECT_ROOT)} is out of date. Run: python scripts/export_openapi.py")
            return 1
        print("openapi.json is up to date")
        return 0
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(text, encoding="utf-8")
    print(f"wrote {TARGET.relative_to(PROJECT_ROOT)} ({len(text)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
