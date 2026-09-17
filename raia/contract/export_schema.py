"""
Write the published JSON Schemas of the RAIA record to ``docs/schema/``.

    python -m raia.contract.export_schema

One file per agent (the full record, computed fields included and marked
``"computed": true``). Tools outside RAIA validate exports against these files;
``tests/test_contract.py`` fails when they fall out of date.
"""

import json
from pathlib import Path
from typing import Dict

from .schema import EXTENSIONS, full_schema
from .vocab import SCHEMA_VERSION

OUT = Path(__file__).resolve().parents[2] / "docs" / "schema"


def generated() -> Dict[str, str]:
    files = {}
    for key in EXTENSIONS:
        schema = {"$id": f"{SCHEMA_VERSION}/{key}", "title": f"RAIA record — {key}", **full_schema(key)}
        files[f"{key}.schema.json"] = json.dumps(schema, indent=2, ensure_ascii=False) + "\n"
    return files


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, text in generated().items():
        (OUT / name).write_text(text, encoding="utf-8")
        print(f"wrote docs/schema/{name}")


if __name__ == "__main__":
    main()
