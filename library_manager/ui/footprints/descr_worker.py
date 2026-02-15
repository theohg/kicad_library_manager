from __future__ import annotations

import json
import os
import re
import sys
from typing import Any


def _extract_kicad_footprint_descr(mod_path: str) -> str:
    """
    Extract description/tags from a `.kicad_mod` file (best-effort).
    Mirrors `extract_kicad_footprint_descr()` behavior but kept dependency-free for subprocess use.
    """
    try:
        with open(mod_path, "r", encoding="utf-8", errors="ignore") as f:
            txt = f.read(8000)
    except Exception:
        return ""
    m = re.search(r'\(descr\s+"([^"]+)"\)', txt)
    if m:
        return (m.group(1) or "").strip()
    m = re.search(r'\(tags\s+"([^"]+)"\)', txt)
    if m:
        return (m.group(1) or "").strip()
    return ""


def main(argv: list[str]) -> int:
    """
    Read jobs from stdin JSON and write results to stdout JSON.

    Input:
      { "items": [ {"ref": "Lib:FP", "path": "/abs/file.kicad_mod"}, ... ] }

    Output:
      { "version": 1, "map": { "Lib:FP": "descr", ... }, "errors": { "Lib:FP": "err", ... } }
    """
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except Exception:
        payload = {}
    items = payload.get("items") if isinstance(payload, dict) else None
    if not isinstance(items, list):
        items = []

    out: dict[str, str] = {}
    errors: dict[str, str] = {}

    for it in items:
        try:
            if not isinstance(it, dict):
                continue
            ref = str(it.get("ref") or "").strip()
            p = str(it.get("path") or "").strip()
            if not ref or not p:
                continue
            if not os.path.exists(p):
                errors[ref] = "file not found"
                out[ref] = ""
                continue
            out[ref] = _extract_kicad_footprint_descr(p)
        except Exception as e:  # noqa: BLE001
            try:
                errors[ref] = str(e)
            except Exception:
                pass
            try:
                out[ref] = ""
            except Exception:
                pass

    resp: dict[str, Any] = {"version": 1, "map": out, "errors": errors}
    sys.stdout.write(json.dumps(resp))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

