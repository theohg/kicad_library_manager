from __future__ import annotations

import json
import os
import re
import sys
from typing import Any


def _extract_blocks(txt: str, needle: str) -> list[str]:
    """
    Minimal s-expression block extraction for entries like (symbol "...").
    This is intentionally dependency-free (no wx) and suitable for subprocess use.
    """
    out: list[str] = []
    i = 0
    while True:
        start = txt.find(needle, i)
        if start < 0:
            break
        depth = 0
        in_str = False
        esc = False
        j = start
        while j < len(txt):
            ch = txt[j]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
            else:
                if ch == '"':
                    in_str = True
                elif ch == "(":
                    depth += 1
                elif ch == ")":
                    depth -= 1
                    if depth == 0 and j > start:
                        out.append(txt[start : j + 1])
                        i = j + 1
                        break
            j += 1
        else:
            break
    return out


_SYMBOL_RE = re.compile(r'\(symbol\s+"([^"]+)"')
_UNIT_VARIANT_RE = re.compile(r".*_\d+_\d+$")


def _scan_kicad_sym_file_meta(sym_lib_path: str, lib_name: str) -> dict[str, tuple[str, str]]:
    """
    Return meta map for a .kicad_sym file: "Lib:Sym" -> (Description, Datasheet).
    """
    try:
        with open(sym_lib_path, "r", encoding="utf-8", errors="ignore") as f:
            txt = f.read()
    except Exception:
        return {}

    meta: dict[str, tuple[str, str]] = {}
    for blk in _extract_blocks(txt, '(symbol "'):
        m = _SYMBOL_RE.search(blk)
        if not m:
            continue
        name = (m.group(1) or "").strip()
        if not name or _UNIT_VARIANT_RE.match(name):
            continue
        desc = ""
        ds = ""
        try:
            mm = re.search(r'\(property\s+"Description"\s+"([^"]*)"', blk)
            desc = (mm.group(1).strip() if mm else "")
            mm2 = re.search(r'\(property\s+"Datasheet"\s+"([^"]*)"', blk)
            ds = (mm2.group(1).strip() if mm2 else "")
        except Exception:
            pass
        meta[f"{lib_name}:{name}"] = (desc, ds)
    return meta


def main(argv: list[str]) -> int:
    """
    Read jobs from stdin JSON and write results to stdout JSON.

    Input:
      { "libs": [ {"lib": "Nick", "path": "/abs/file.kicad_sym"}, ... ] }

    Output:
      {
        "version": 1,
        "loaded_libs": ["Nick", ...],
        "meta": { "Nick:Sym": ["desc", "ds"], ... },
        "errors": { "Nick": "error text", ... }
      }
    """
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except Exception:
        payload = {}
    jobs = payload.get("libs") if isinstance(payload, dict) else None
    if not isinstance(jobs, list):
        jobs = []

    out_meta: dict[str, list[str]] = {}
    loaded: list[str] = []
    errors: dict[str, str] = {}

    for j in jobs:
        try:
            if not isinstance(j, dict):
                continue
            lib = str(j.get("lib") or "").strip()
            p = str(j.get("path") or "").strip()
            if not lib or not p:
                continue
            if not os.path.exists(p):
                errors[lib] = "file not found"
                continue
            mm = _scan_kicad_sym_file_meta(p, lib)
            for k, (d, ds) in mm.items():
                out_meta[str(k)] = [str(d or ""), str(ds or "")]
            loaded.append(lib)
        except Exception as e:  # noqa: BLE001
            try:
                errors[str(j.get("lib") or lib or "?")] = str(e)
            except Exception:
                pass

    resp: dict[str, Any] = {"version": 1, "loaded_libs": sorted(set([x for x in loaded if x])), "meta": out_meta, "errors": errors}
    sys.stdout.write(json.dumps(resp))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

