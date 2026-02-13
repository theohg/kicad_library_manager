"""
Python footprint generator (IPC-7351) with a minimal GUI.

This package is intended to be executed as a module:
  - GUI:    python -m python.gui
  - CLI:    python -m python.generate --kind soic --element element.json --out ./kicad/footprints

Folder structure mirrors `src/pattern/default` CoffeeScript modules so math and
pad placement remain identical.
"""

