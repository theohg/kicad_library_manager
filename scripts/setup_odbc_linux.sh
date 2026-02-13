#!/usr/bin/env bash
set -euo pipefail

SECTION_NAME="SQLite3 ODBC Driver"
ODBCINST_INI="/etc/odbcinst.ini"

# ---- helpers ----
need_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Error: required command not found: $1" >&2
    exit 1
  }
}

as_root() {
  if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
    sudo "$@"
  else
    "$@"
  fi
}

# ---- sanity ----
need_cmd apt-get
need_cmd dpkg
need_cmd grep
need_cmd awk
need_cmd mktemp

# ---- install packages ----
as_root apt-get update -y
as_root apt-get install -y unixodbc libsqliteodbc

# ---- find driver .so path ----
so_candidates="$(dpkg -L libsqliteodbc | grep -E '\.so($|[.])' || true)"

if [[ -z "$so_candidates" ]]; then
  echo "Error: No .so files found from 'dpkg -L libsqliteodbc'." >&2
  exit 1
fi

# Prefer the actual ODBC driver library if present; fall back to first .so found.
driver_path="$(
  echo "$so_candidates" | awk '
    /libsqlite3odbc\.so(\.|$)/ { print; found=1; exit }
    /libsqliteodbc\.so(\.|$)/  { print; found=1; exit }
    END { if (!found) exit 1 }
  ' || true
)"

if [[ -z "${driver_path:-}" ]]; then
  driver_path="$(echo "$so_candidates" | head -n1)"
fi

# Use same library for Setup unless you want to locate a separate setup lib
setup_path="$driver_path"

echo "Using Driver: $driver_path"
echo "Using Setup : $setup_path"

# ---- ensure /etc/odbcinst.ini exists ----
as_root touch "$ODBCINST_INI"

# ---- remove existing section (if any), then append fresh section ----
tmpfile="$(mktemp)"
trap 'rm -f "$tmpfile"' EXIT

# Remove an existing [SQLite3 ODBC Driver] block (until next [Section] or EOF)
awk -v section="[$SECTION_NAME]" '
  BEGIN { skip=0 }
  $0 == section { skip=1; next }
  skip && $0 ~ /^\[/ { skip=0 }   # next section starts
  !skip { print }
' "$ODBCINST_INI" > "$tmpfile"

cat >> "$tmpfile" <<EOF

[$SECTION_NAME]
Description=SQLite3 ODBC Driver
Driver=$driver_path
Setup=$setup_path
Threading=2
EOF

as_root cp "$tmpfile" "$ODBCINST_INI"
as_root chmod 644 "$ODBCINST_INI"

# ---- verify ----
echo
echo "Updated $ODBCINST_INI. Registered drivers now:"
odbcinst -q -d || true

echo
echo "Done."
echo "Your connection string should work as-is (driver name must match exactly):"
echo "  DRIVER={$SECTION_NAME};Database=./parts.sqlite"
