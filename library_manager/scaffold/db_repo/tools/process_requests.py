#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import glob
import json
import os
import re
import sys
import tempfile
from dataclasses import dataclass


REQ_DIR = "Requests"
CAT_FIELDS_DIR = os.path.join("Database", "category_fields")
TMP_RE = re.compile(r"^TMP-")
IPN_RE = re.compile(r"^(?P<base>.+)-(?P<num>\d+)$")
SAFE_CAT_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_ ]*[A-Za-z0-9_]$|^[A-Za-z0-9_]+$")


@dataclass(frozen=True)
class PrefixSpec:
    prefix: str  # includes trailing '-'
    width: int


def _parse_simple_yaml(path: str) -> dict[str, PrefixSpec]:
    # same tiny-yaml parser style as tools/assign_ipn.py
    if not os.path.exists(path):
        return {}
    specs: dict[str, dict[str, str]] = {}
    current: str | None = None
    with open(path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.rstrip("\n")
            if not line.strip() or line.strip().startswith("#"):
                continue
            if not line.startswith(" ") and line.endswith(":"):
                current = line[:-1].strip()
                specs[current] = {}
                continue
            if current and line.startswith("  ") and ":" in line:
                k, v = line.strip().split(":", 1)
                v = v.strip().strip('"').strip("'")
                specs[current][k.strip()] = v
    out: dict[str, PrefixSpec] = {}
    for cat, d in specs.items():
        pfx = (d.get("prefix") or "").strip()
        w = (d.get("width") or "").strip()
        if not pfx or not w:
            continue
        try:
            width = int(w)
        except ValueError:
            continue
        if not pfx.endswith("-"):
            pfx += "-"
        out[cat] = PrefixSpec(prefix=pfx, width=width)
    return out


def _write_categories_yml(path: str, specs: dict[str, PrefixSpec]) -> None:
    lines = [
        "# Used by CI when a brand-new category has no existing IPNs yet.",
        "#",
        "# Format:",
        "# CategoryName:",
        '#   prefix: \"ABC-\"',
        "#   width: 7",
        "#",
        "# Most existing categories infer their prefix automatically from existing rows.",
        "",
    ]
    for cat in sorted(specs.keys()):
        s = specs[cat]
        lines.append(f"{cat}:")
        lines.append(f'  prefix: "{s.prefix}"')
        lines.append(f"  width: {s.width}")
        lines.append("")
    txt = "\n".join(lines).rstrip() + "\n"
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(txt)


def _upsert_category_prefix(db_dir: str, category: str, prefix: str, width: int) -> None:
    yml_path = os.path.join(db_dir, "categories.yml")
    specs = _parse_simple_yaml(yml_path)
    pfx = (prefix or "").strip()
    if not pfx:
        return
    if not pfx.endswith("-"):
        pfx = pfx + "-"
    specs[category] = PrefixSpec(prefix=pfx, width=int(width))
    _write_categories_yml(yml_path, specs)


def _remove_category_prefix(db_dir: str, category: str) -> None:
    yml_path = os.path.join(db_dir, "categories.yml")
    specs = _parse_simple_yaml(yml_path)
    if category in specs:
        del specs[category]
        _write_categories_yml(yml_path, specs)


def _write_csv_with_headers(csv_path: str, headers: list[str]) -> None:
    os.makedirs(os.path.dirname(csv_path), exist_ok=True)
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(headers)


def _write_category_fields_config(repo: str, category: str, fields: list[dict]) -> str:
    """
    Persist per-category field visibility config for tools/update_dbl.py.
    """
    cfg_dir = os.path.join(repo, "Database", "category_fields")
    os.makedirs(cfg_dir, exist_ok=True)
    cfg_path = os.path.join(cfg_dir, f"{category}.json")
    body = {"schema_version": 1, "category": category, "fields": fields}
    with open(cfg_path, "w", encoding="utf-8") as f:
        json.dump(body, f, indent=2, sort_keys=False)
        f.write("\n")
    return cfg_path


def _infer_prefix_spec(csv_path: str, yaml_specs: dict[str, PrefixSpec]) -> PrefixSpec:
    category = os.path.basename(csv_path)[3:-4]  # db-<cat>.csv
    with open(csv_path, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    existing: list[PrefixSpec] = []
    for r in rows:
        ipn = (r.get("IPN") or "").strip()
        if not ipn or TMP_RE.match(ipn):
            continue
        m = IPN_RE.match(ipn)
        if not m:
            continue
        base = m.group("base")
        num = m.group("num")
        existing.append(PrefixSpec(prefix=f"{base}-", width=len(num)))
    if existing:
        counts: dict[PrefixSpec, int] = {}
        for s in existing:
            counts[s] = counts.get(s, 0) + 1
        return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0].prefix))[0][0]
    if category in yaml_specs:
        return yaml_specs[category]
    raise RuntimeError(f"Cannot infer IPN prefix for new category '{category}'. Add it to Database/categories.yml")


def _read_headers(csv_path: str) -> list[str]:
    with open(csv_path, "r", newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        return next(reader)


def _append_row(csv_path: str, headers: list[str], row: dict[str, str]) -> None:
    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers, lineterminator="\n")
        writer.writerow({h: row.get(h, "") for h in headers})


def _rewrite_csv(csv_path: str, headers: list[str], rows: list[dict[str, str]]) -> None:
    dir_name = os.path.dirname(csv_path)
    fd, tmp_path = tempfile.mkstemp(prefix=os.path.basename(csv_path) + ".", suffix=".tmp", dir=dir_name)
    os.close(fd)
    try:
        with open(tmp_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=headers, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
        os.replace(tmp_path, csv_path)
    finally:
        try:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
        except Exception:
            pass


def _find_csv_rows_by_ipn(db_dir: str, ipn: str) -> list[tuple[str, list[str], list[dict[str, str]], int]]:
    """
    Returns list of matches:
      (csv_path, headers, rows, match_index)
    """
    matches: list[tuple[str, list[str], list[dict[str, str]], int]] = []
    for csv_path in sorted(glob.glob(os.path.join(db_dir, "db-*.csv"))):
        with open(csv_path, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            headers = list(reader.fieldnames or [])
            rows = list(reader)
        if not headers or "IPN" not in headers:
            continue
        for idx, r in enumerate(rows):
            if (r.get("IPN") or "").strip() == ipn:
                matches.append((csv_path, headers, rows, idx))
    return matches


def process(repo: str) -> int:
    repo = os.path.abspath(repo)
    db_dir = os.path.join(repo, "Database")
    req_dir = os.path.join(repo, REQ_DIR)
    if not os.path.isdir(req_dir):
        return 0

    req_files = sorted(glob.glob(os.path.join(req_dir, "*.json")))
    if not req_files:
        return 0

    yaml_specs = _parse_simple_yaml(os.path.join(db_dir, "categories.yml"))

    processed = 0
    for req_path in req_files:
        try:
            with open(req_path, "r", encoding="utf-8") as f:
                req = json.load(f)

            if int(req.get("schema_version", 0)) != 1:
                raise RuntimeError("Unsupported schema_version")

            # Backwards-compatible action inference:
            # - Older/handmade delete requests may only include {\"ipn\": \"...\"}.
            # - Older/handmade update requests may include {\"ipn\": \"...\", \"set\": {...}}.
            raw_action = (req.get("action") or "").strip().lower()
            if raw_action:
                action = raw_action
            else:
                if isinstance(req.get("set"), dict) and (req.get("ipn") or "").strip():
                    action = "update"
                elif (req.get("ipn") or "").strip() and not req.get("category"):
                    action = "delete"
                else:
                    action = "add"

            if action == "add":
                category = (req.get("category") or "").strip()
                fields = req.get("fields") or {}
                if not category or not isinstance(fields, dict):
                    raise RuntimeError("Invalid add request (missing category/fields)")

                csv_path = os.path.join(db_dir, f"db-{category}.csv")
                if not os.path.exists(csv_path):
                    raise RuntimeError(f"Missing CSV for category '{category}': {os.path.relpath(csv_path, repo)}")

                headers = _read_headers(csv_path)
                if "IPN" not in headers:
                    raise RuntimeError(f"CSV missing IPN column: {os.path.relpath(csv_path, repo)}")

                # Use a deterministic TMP key derived from the request filename.
                req_id = os.path.splitext(os.path.basename(req_path))[0]
                row: dict[str, str] = {k: str(v) for k, v in fields.items()}
                row["IPN"] = f"TMP-REQ-{req_id}"

                # Minimal required fields
                for required in ("Symbol", "Footprint", "Description"):
                    if required in headers and not (row.get(required) or "").strip():
                        raise RuntimeError(f"Request missing required field '{required}': {os.path.relpath(req_path, repo)}")

                _append_row(csv_path, headers, row)

                # Ensure prefix spec can be inferred (fail early for brand-new categories)
                _infer_prefix_spec(csv_path, yaml_specs)

            elif action == "category_add":
                category = (req.get("category") or "").strip()
                if not category or not SAFE_CAT_RE.match(category):
                    raise RuntimeError(f"Invalid category name '{category}' (use letters/numbers/underscore/spaces).")

                prefix = (req.get("prefix") or "").strip()
                width = int(req.get("width") or 7)
                if not prefix:
                    raise RuntimeError(
                        "category_add request is missing 'prefix'. "
                        "A prefix is required for brand-new categories so CI can assign IPNs."
                    )

                fields = req.get("fields") or []
                if not isinstance(fields, list) or not fields:
                    raise RuntimeError("Invalid category_add request (missing fields list)")

                # Normalize field defs -> DBL field objects (column/name/visible flags)
                out_fields: list[dict] = []
                headers2: list[str] = []
                seen: set[str] = set()
                for fdef in fields:
                    if not isinstance(fdef, dict):
                        continue
                    col = str(fdef.get("name") or fdef.get("column") or "").strip()
                    if not col:
                        continue
                    if col in seen:
                        continue
                    seen.add(col)
                    headers2.append(col)
                    out_fields.append(
                        {
                            "column": col,
                            "name": col,
                            "visible_on_add": bool(fdef.get("visible_on_add", False)),
                            "visible_in_chooser": bool(fdef.get("visible_in_chooser", True)),
                            "show_name": False,
                        }
                    )

                # Mandatory headers
                for req_h in ("IPN", "Symbol", "Footprint", "Value", "Description"):
                    if req_h not in seen:
                        headers2.insert(0 if req_h == "IPN" else len(headers2), req_h)
                        out_fields.insert(
                            0 if req_h == "IPN" else len(out_fields),
                            {
                                "column": req_h,
                                "name": req_h,
                                "visible_on_add": False,
                                "visible_in_chooser": True if req_h in {"IPN", "Value"} else False,
                                "show_name": False,
                            },
                        )
                        seen.add(req_h)

                # Ensure IPN first
                if headers2 and headers2[0] != "IPN" and "IPN" in headers2:
                    headers2 = ["IPN"] + [h for h in headers2 if h != "IPN"]
                    # keep out_fields order in sync
                    ipn_field = [x for x in out_fields if x.get("column") == "IPN"]
                    rest = [x for x in out_fields if x.get("column") != "IPN"]
                    out_fields = (ipn_field + rest) if ipn_field else out_fields

                csv_path = os.path.join(db_dir, f"db-{category}.csv")
                if os.path.exists(csv_path):
                    raise RuntimeError(f"Category already exists: {os.path.relpath(csv_path, repo)}")

                _write_csv_with_headers(csv_path, headers2)
                _write_category_fields_config(repo, category, out_fields)
                if prefix:
                    _upsert_category_prefix(db_dir, category, prefix, width)
                    # refresh yaml_specs for subsequent operations in same run
                    yaml_specs = _parse_simple_yaml(os.path.join(db_dir, "categories.yml"))

            elif action == "category_delete":
                category = (req.get("category") or "").strip()
                if not category:
                    raise RuntimeError("Invalid category_delete request (missing category)")
                csv_path = os.path.join(db_dir, f"db-{category}.csv")
                if os.path.exists(csv_path):
                    os.remove(csv_path)
                cfg_path = os.path.join(repo, "Database", "category_fields", f"{category}.json")
                if os.path.exists(cfg_path):
                    os.remove(cfg_path)
                _remove_category_prefix(db_dir, category)

            elif action == "category_update":
                category = (req.get("category") or "").strip()
                if not category or not SAFE_CAT_RE.match(category):
                    raise RuntimeError(f"Invalid category name '{category}'")
                csv_path = os.path.join(db_dir, f"db-{category}.csv")
                if not os.path.exists(csv_path):
                    raise RuntimeError(f"Missing CSV for category '{category}': {os.path.relpath(csv_path, repo)}")

                fields = req.get("fields") or []
                if not isinstance(fields, list) or not fields:
                    raise RuntimeError("Invalid category_update request (missing fields list)")

                # Normalize field defs -> DBL field objects (column/name/visible flags)
                out_fields2: list[dict] = []
                desired_cols: list[str] = []
                seen2: set[str] = set()
                for fdef in fields:
                    if not isinstance(fdef, dict):
                        continue
                    col = str(fdef.get("name") or fdef.get("column") or "").strip()
                    if not col or col in seen2:
                        continue
                    seen2.add(col)
                    desired_cols.append(col)
                    out_fields2.append(
                        {
                            "column": col,
                            "name": col,
                            "visible_on_add": bool(fdef.get("visible_on_add", False)),
                            "visible_in_chooser": bool(fdef.get("visible_in_chooser", True)),
                            "show_name": False,
                        }
                    )

                # Mandatory headers always kept
                for req_h in ("IPN", "Symbol", "Footprint", "Value", "Description"):
                    if req_h not in seen2:
                        desired_cols.insert(0 if req_h == "IPN" else len(desired_cols), req_h)
                        out_fields2.insert(
                            0 if req_h == "IPN" else len(out_fields2),
                            {
                                "column": req_h,
                                "name": req_h,
                                "visible_on_add": False,
                                "visible_in_chooser": True if req_h in {"IPN", "Value"} else False,
                                "show_name": False,
                            },
                        )
                        seen2.add(req_h)

                # Keep existing columns (no destructive removal) but append any new ones.
                existing_headers = _read_headers(csv_path)
                # Ensure IPN first.
                if existing_headers and existing_headers[0] != "IPN" and "IPN" in existing_headers:
                    existing_headers = ["IPN"] + [h for h in existing_headers if h != "IPN"]
                new_headers = list(existing_headers)
                for c in desired_cols:
                    if c not in new_headers:
                        new_headers.append(c)

                # Rewrite CSV if headers expanded.
                if new_headers != existing_headers:
                    with open(csv_path, "r", newline="", encoding="utf-8") as f:
                        rdr = csv.DictReader(f)
                        rows = [dict(r) for r in rdr]
                    # Preserve rows, fill missing with blanks.
                    _rewrite_csv(csv_path, new_headers, rows)

                _write_category_fields_config(repo, category, out_fields2)

                prefix = (req.get("prefix") or "").strip()
                width = int(req.get("width") or 7)
                if prefix:
                    _upsert_category_prefix(db_dir, category, prefix, width)
                    yaml_specs = _parse_simple_yaml(os.path.join(db_dir, "categories.yml"))

            elif action == "delete":
                ipn = (req.get("ipn") or "").strip()
                if not ipn:
                    raise RuntimeError(f"Invalid delete request (missing ipn): {os.path.relpath(req_path, repo)}")
                matches = _find_csv_rows_by_ipn(db_dir, ipn)
                if len(matches) == 0:
                    raise RuntimeError(f"Delete request: IPN not found: {ipn}")
                if len(matches) > 1:
                    raise RuntimeError(f"Delete request: IPN found in multiple CSVs: {ipn}")
                csv_path, headers3, rows3, idx = matches[0]
                del rows3[idx]
                _rewrite_csv(csv_path, headers3, rows3)

            elif action == "update":
                ipn = (req.get("ipn") or "").strip()
                set_fields = req.get("set") or {}
                if not ipn or not isinstance(set_fields, dict) or not set_fields:
                    raise RuntimeError(f"Invalid update request: {os.path.relpath(req_path, repo)}")
                if "IPN" in set_fields:
                    raise RuntimeError(f"Update request must not modify IPN: {os.path.relpath(req_path, repo)}")
                matches = _find_csv_rows_by_ipn(db_dir, ipn)
                if len(matches) == 0:
                    raise RuntimeError(f"Update request: IPN not found: {ipn}")
                if len(matches) > 1:
                    raise RuntimeError(f"Update request: IPN found in multiple CSVs: {ipn}")
                csv_path, headers4, rows4, idx = matches[0]
                row2 = rows4[idx]
                # Ensure requested columns exist
                for k in set_fields.keys():
                    if k not in headers4:
                        raise RuntimeError(f"Update request: column '{k}' not in {os.path.relpath(csv_path, repo)}")
                for k, v in set_fields.items():
                    row2[k] = str(v)
                rows4[idx] = row2
                _rewrite_csv(csv_path, headers4, rows4)

            else:
                raise RuntimeError(f"Unknown action '{action}'")

            os.remove(req_path)
            processed += 1

        except Exception as e:
            # Quarantine invalid requests so they don't block the entire pipeline.
            invalid_dir = os.path.join(req_dir, "invalid")
            os.makedirs(invalid_dir, exist_ok=True)
            dst = os.path.join(invalid_dir, os.path.basename(req_path))
            try:
                os.replace(req_path, dst)
            except Exception:
                pass
            print(
                f"Quarantined invalid request: {os.path.relpath(req_path, repo)} -> {os.path.relpath(dst, repo)}\n"
                f"Reason: {e}",
                file=sys.stderr,
            )

    return processed


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(
        description="Process Requests/*.json into Database/db-*.csv (append TMP rows, delete/update, category add/delete)."
    )
    ap.add_argument("--repo", default=".", help="Repo root")
    args = ap.parse_args(argv)

    n = process(args.repo)
    print(f"Processed requests: {n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

