#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import glob
import os
import sqlite3
import sys


def qident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def table_from_csv_path(csv_path: str) -> str:
    base = os.path.basename(csv_path)
    if base.startswith("db-") and base.endswith(".csv"):
        return base[3:-4]
    return os.path.splitext(base)[0]


def read_csv(csv_path: str) -> tuple[list[str], list[dict[str, str]]]:
    with open(csv_path, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            return [], []
        rows = list(reader)
        return list(reader.fieldnames), rows


def rebuild(repo: str) -> None:
    repo = os.path.abspath(repo)
    db_dir = os.path.join(repo, "Database")
    out_db = os.path.join(db_dir, "parts.sqlite")

    csv_files = sorted(glob.glob(os.path.join(db_dir, "db-*.csv")))
    if not csv_files:
        raise RuntimeError("No Database/db-*.csv files found")

    # Ensure directory exists
    os.makedirs(db_dir, exist_ok=True)

    con = sqlite3.connect(out_db)
    try:
        cur = con.cursor()
        for csv_path in csv_files:
            table = table_from_csv_path(csv_path)
            headers, rows = read_csv(csv_path)
            if not headers:
                continue

            cur.execute(f"DROP TABLE IF EXISTS {qident(table)}")

            cols = ", ".join([f"{qident(h)} TEXT" for h in headers])
            if "IPN" in headers:
                # KiCad DBL uses IPN as key; enforce uniqueness on the main branch DB.
                cols = cols + f", PRIMARY KEY({qident('IPN')})"

            cur.execute(f"CREATE TABLE {qident(table)} ({cols})")

            placeholders = ", ".join(["?"] * len(headers))
            insert_sql = f"INSERT INTO {qident(table)} ({', '.join(qident(h) for h in headers)}) VALUES ({placeholders})"

            values = []
            for r in rows:
                values.append([r.get(h, "") for h in headers])
            if values:
                cur.executemany(insert_sql, values)

        con.commit()
    finally:
        con.close()


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description="Rebuild Database/parts.sqlite from Database/db-*.csv")
    p.add_argument("--repo", default=".", help="Repo root (default: .)")
    args = p.parse_args(argv)

    rebuild(args.repo)
    print("Database/parts.sqlite rebuilt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

