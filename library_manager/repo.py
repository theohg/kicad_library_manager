from __future__ import annotations

import glob
import os
import csv
from dataclasses import dataclass


@dataclass(frozen=True)
class Category:
    filename: str        # db-Resistors.csv
    display_name: str    # Resistors
    csv_path: str        # /abs/.../Database/db-Resistors.csv


def is_repo_root(path: str) -> bool:
    if not path:
        return False
    # Accept either the explicit categories.yml sentinel OR any KiCad DBL definition file
    # under Database/ (to avoid hardcoding a specific DBL filename).
    try:
        has_any_dbl = bool(glob.glob(os.path.join(path, "Database", "*.kicad_dbl")))
    except Exception:
        has_any_dbl = False
    return (
        os.path.isdir(os.path.join(path, "Database"))
        and (
            os.path.isfile(os.path.join(path, "Database", "categories.yml"))
            or has_any_dbl
        )
        and os.path.isdir(os.path.join(path, "Footprints"))
        and os.path.isdir(os.path.join(path, "Symbols"))
    )


def _walk_up_dirs(start_path: str) -> list[str]:
    """
    Return directories from `start_path` up to filesystem root (inclusive).
    """
    if not start_path:
        return []
    p = start_path
    try:
        if os.path.isfile(p):
            p = os.path.dirname(p)
    except Exception:
        pass
    try:
        p = os.path.abspath(p)
    except Exception:
        p = str(p or "")
    out: list[str] = []
    while p and p not in out:
        out.append(p)
        parent = os.path.dirname(p)
        if parent == p:
            break
        p = parent
    return out


def find_repo_root_auto(start_paths: list[str]) -> str | None:
    """
    Best-effort discovery of the local database repo root without hardcoding `Libraries/`.

    For each start path, walk up to root and return the first directory that matches `is_repo_root`.
    """
    seen: set[str] = set()
    for sp in list(start_paths or []):
        for d in _walk_up_dirs(str(sp or "").strip()):
            if not d or d in seen:
                continue
            seen.add(d)
            if is_repo_root(d):
                return d
    return None


def list_categories(repo_path: str) -> list[Category]:
    db_dir = os.path.join(repo_path, "Database")
    pattern = os.path.join(db_dir, "db-*.csv")
    cats: list[Category] = []
    for csv_path in sorted(glob.glob(pattern)):
        filename = os.path.basename(csv_path)
        display = filename[3:-4]  # strip db- and .csv
        cats.append(Category(filename=filename, display_name=display, csv_path=csv_path))
    return cats


def find_repo_root_from_project(start_path: str) -> str | None:
    """
    Try to locate the repo root from a KiCad project/board path by walking up
    directories and looking for a per-project submodule layout under:

      <project>/Libraries
    """
    if not start_path:
        return None

    p = start_path
    if os.path.isfile(p):
        p = os.path.dirname(p)
    p = os.path.abspath(p)

    while True:
        # If we started inside the repo itself, accept it.
        if is_repo_root(p):
            return p
        libs = os.path.join(p, "Libraries")
        if is_repo_root(libs):
            return libs
        # Also accept a nested submodule under Libraries/<anything>/...
        try:
            if os.path.isdir(libs):
                for name in os.listdir(libs):
                    cand = os.path.join(libs, name)
                    if is_repo_root(cand):
                        return cand
        except Exception:
            pass

        parent = os.path.dirname(p)
        if parent == p:
            break
        p = parent

    return None


def find_part_by_ipn(repo_path: str, ipn: str) -> tuple[Category, list[str], dict[str, str]] | None:
    """
    Search all Database/db-*.csv for a matching IPN and return:
      (category, headers, row)
    """
    db_dir = os.path.join(repo_path, "Database")
    pattern = os.path.join(db_dir, "db-*.csv")
    for csv_path in sorted(glob.glob(pattern)):
        with open(csv_path, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            headers = list(reader.fieldnames or [])
            for row in reader:
                if (row.get("IPN") or "").strip() == ipn:
                    filename = os.path.basename(csv_path)
                    display = filename[3:-4]
                    cat = Category(filename=filename, display_name=display, csv_path=csv_path)
                    return cat, headers, dict(row)
    return None

