#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import os
import re
import sys
import tempfile
from dataclasses import dataclass


TMP_RE = re.compile(r"^TMP-")
IPN_RE = re.compile(r"^(?P<base>.+)-(?P<num>\d+)$")


@dataclass(frozen=True)
class PrefixSpec:
    prefix: str  # includes trailing '-'
    width: int


def _parse_simple_yaml(path: str) -> dict[str, PrefixSpec]:
    """
    Parse a tiny subset of YAML:

    CategoryName:
      prefix: "CAP-"
      width: 7

    This avoids adding PyYAML as a dependency.
    """
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
                v = v.strip()
                if v.startswith('"') and v.endswith('"'):
                    v = v[1:-1]
                if v.startswith("'") and v.endswith("'"):
                    v = v[1:-1]
                specs[current][k.strip()] = v

    out: dict[str, PrefixSpec] = {}
    for cat, d in specs.items():
        prefix = (d.get("prefix") or "").strip()
        width_s = (d.get("width") or "").strip()
        if not prefix or not width_s:
            continue
        try:
            width = int(width_s)
        except ValueError:
            continue
        if not prefix.endswith("-"):
            prefix = prefix + "-"
        out[cat] = PrefixSpec(prefix=prefix, width=width)
    return out


def _table_from_csv_filename(filename: str) -> str:
    # db-Resistors.csv -> Resistors
    base = os.path.basename(filename)
    if base.startswith("db-") and base.endswith(".csv"):
        return base[3:-4]
    return os.path.splitext(base)[0]


def _infer_prefix_spec(rows: list[dict[str, str]], category: str, yaml_specs: dict[str, PrefixSpec]) -> PrefixSpec:
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
        # If multiple shapes exist (unlikely), prefer the most common.
        counts: dict[PrefixSpec, int] = {}
        for s in existing:
            counts[s] = counts.get(s, 0) + 1
        return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0].prefix))[0][0]

    if category in yaml_specs:
        return yaml_specs[category]

    raise RuntimeError(
        f"Cannot infer IPN prefix for category '{category}' (no existing IPNs found) "
        f"and no entry in Database/categories.yml"
    )


def assign_file(csv_path: str, yaml_specs: dict[str, PrefixSpec], dry_run: bool = False) -> int:
    category = _table_from_csv_filename(csv_path)

    with open(csv_path, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            return 0
        if "IPN" not in reader.fieldnames:
            return 0
        fieldnames = list(reader.fieldnames)
        rows = list(reader)

    spec = _infer_prefix_spec(rows, category, yaml_specs)

    max_num = -1
    for r in rows:
        ipn = (r.get("IPN") or "").strip()
        if not ipn or TMP_RE.match(ipn):
            continue
        m = IPN_RE.match(ipn)
        if not m:
            continue
        base = m.group("base")
        if f"{base}-" != spec.prefix:
            continue
        try:
            n = int(m.group("num"))
        except ValueError:
            continue
        max_num = max(max_num, n)

    changed = 0
    next_num = max_num + 1
    for r in rows:
        ipn = (r.get("IPN") or "").strip()
        if not ipn or TMP_RE.match(ipn):
            r["IPN"] = f"{spec.prefix}{next_num:0{spec.width}d}"
            next_num += 1
            changed += 1

    if changed == 0 or dry_run:
        return changed

    # Rewrite atomically.
    dir_name = os.path.dirname(csv_path)
    fd, tmp_path = tempfile.mkstemp(prefix=os.path.basename(csv_path) + ".", suffix=".tmp", dir=dir_name)
    os.close(fd)
    try:
        with open(tmp_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        os.replace(tmp_path, csv_path)
    finally:
        try:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
        except Exception:
            pass

    return changed


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description="Assign sequential IPNs for TMP placeholders in db-*.csv files.")
    p.add_argument("--repo", default=".", help="Repo root (default: .)")
    p.add_argument("--dry-run", action="store_true", help="Compute changes but do not rewrite files.")
    args = p.parse_args(argv)

    repo = os.path.abspath(args.repo)
    db_dir = os.path.join(repo, "Database")
    yaml_path = os.path.join(db_dir, "categories.yml")
    yaml_specs = _parse_simple_yaml(yaml_path)

    import glob

    pattern = os.path.join(db_dir, "db-*.csv")
    csv_files = sorted([p for p in glob.glob(pattern)])
    if not csv_files:
        print("No db-*.csv files found.", file=sys.stderr)
        return 1

    total = 0
    for csv_path in csv_files:
        try:
            changed = assign_file(csv_path, yaml_specs, dry_run=args.dry_run)
            if changed:
                print(f"{os.path.relpath(csv_path, repo)}: assigned {changed} IPN(s)")
            total += changed
        except Exception as e:
            print(f"{os.path.relpath(csv_path, repo)}: ERROR: {e}", file=sys.stderr)
            return 2

    print(f"Total assigned: {total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

