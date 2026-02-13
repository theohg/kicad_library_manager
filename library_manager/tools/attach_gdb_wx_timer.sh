#!/usr/bin/env bash
set -euo pipefail

PID_FILE="${XDG_CACHE_HOME:-$HOME/.cache}/kicad_library_manager/ipc_plugin_pid.json"

if [[ -f "$PID_FILE" ]]; then
  PID="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["pid"])' "$PID_FILE")"
else
  # Best-effort fallback (may match multiple; pick newest PID).
  PID="$(pgrep -n -f 'library_manager/plugin\.py' || true)"
fi

if [[ -z "${PID:-}" ]]; then
  echo "Could not find plugin PID."
  echo "Start the plugin first, or ensure $PID_FILE exists."
  exit 2
fi

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
GDB_SCRIPT="$SCRIPT_DIR/wx_timer_trace.gdb"

echo "Attaching gdb to PID=$PID"
echo "Logging to /tmp/kicad_library_manager_timer.log"
echo "GDB script: $GDB_SCRIPT"
echo
echo "After it crashes, paste /tmp/kicad_library_manager_timer.log"
echo

exec gdb -q -p "$PID" -x "$GDB_SCRIPT"

