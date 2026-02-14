"""
Platform-specific subprocess helpers.

On Windows, console applications (git, kicad-cli, gh, etc.) spawned via
subprocess open a visible console window that flashes and disappears.
This module provides a dict of extra kwargs to pass to subprocess.run()
(or Popen) that suppresses the window on Windows and is a no-op elsewhere.

Usage::

    from library_manager._subprocess import SUBPROCESS_NO_WINDOW

    subprocess.run(["git", "status"], **SUBPROCESS_NO_WINDOW)
"""
from __future__ import annotations

import subprocess
import sys

SUBPROCESS_NO_WINDOW: dict = {}

if sys.platform == "win32":
    # CREATE_NO_WINDOW (0x08000000) prevents the child process from
    # inheriting or creating a console window.
    SUBPROCESS_NO_WINDOW = {"creationflags": subprocess.CREATE_NO_WINDOW}
