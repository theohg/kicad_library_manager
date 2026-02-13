from __future__ import annotations

import csv
import os
from dataclasses import dataclass

from ..repo import Category
from ..suggest import list_footprints, list_symbols


@dataclass(frozen=True)
class CsvTable:
    headers: list[str]
    rows: list[dict[str, str]]


REQUIRED_COLUMNS = ("IPN", "Symbol", "Footprint")


def load_csv_table(csv_path: str) -> CsvTable:
    with open(csv_path, "r", newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        headers = list(reader.fieldnames or [])
        rows: list[dict[str, str]] = []
        for row in reader:
            normalized: dict[str, str] = {}
            for h in headers:
                normalized[h] = str((row or {}).get(h, "") or "")
            rows.append(normalized)
    return CsvTable(headers=headers, rows=rows)


def save_csv_table(csv_path: str, headers: list[str], rows: list[dict[str, str]]) -> None:
    tmp_path = csv_path + ".tmp"
    with open(tmp_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=headers)
        writer.writeheader()
        for src in rows:
            writer.writerow({h: str(src.get(h, "") or "") for h in headers})
    os.replace(tmp_path, csv_path)


def validate_row(headers: list[str], row: dict[str, str], *, editing_ipn: str | None = None, existing_rows: list[dict[str, str]] | None = None) -> list[str]:
    errs: list[str] = []
    for col in REQUIRED_COLUMNS:
        if col not in headers:
            errs.append(f"CSV is missing required column: {col}")

    for col in ("Symbol", "Footprint"):
        if col in headers and not str(row.get(col, "")).strip():
            errs.append(f"Field is required: {col}")

    ipn = str(row.get("IPN", "")).strip()
    # IPN is assigned by CI/GitHub Actions in this workflow.
    # - For new rows (editing_ipn is None), allow it to be blank.
    # - For existing rows, keep requiring it (it identifies the row).
    if "IPN" in headers and editing_ipn is not None and not ipn:
        errs.append("Field is required: IPN")

    if existing_rows is not None and ipn:
        for existing in existing_rows:
            existing_ipn = str(existing.get("IPN", "")).strip()
            if not existing_ipn:
                continue
            if existing_ipn == ipn and existing_ipn != (editing_ipn or "").strip():
                errs.append(f"Duplicate IPN already exists: {ipn}")
                break

    for key, value in row.items():
        if "\n" in str(value) or "\r" in str(value):
            errs.append(f"Field contains newline characters: {key}")
    return errs


def resolve_asset_lists(repo_path: str) -> tuple[list[str], list[str]]:
    """
    Returns (symbols, footprints) as sorted unique KiCad refs.
    """
    syms = sorted(set(list_symbols(repo_path)))
    fps = sorted(set(list_footprints(repo_path)))
    return syms, fps


def row_label(row: dict[str, str], headers: list[str]) -> str:
    ipn = str(row.get("IPN", "")).strip()
    sym = str(row.get("Symbol", "")).strip()
    fp = str(row.get("Footprint", "")).strip()
    if ipn:
        return ipn
    if sym or fp:
        return f"{sym} | {fp}"
    for h in headers:
        v = str(row.get(h, "")).strip()
        if v:
            return v
    return "<empty>"


def category_title(category: Category) -> str:
    return category.display_name or category.filename
