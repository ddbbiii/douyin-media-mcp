from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .redaction import redact_mapping


def write_manifest(path: Path, payload: dict[str, Any]) -> Path:
    cleaned = redact_mapping(payload)
    temporary = path.with_name(f".{path.name}.tmp")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary.write_text(
        json.dumps(cleaned, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)
    return path
