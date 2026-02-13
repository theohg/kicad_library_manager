"""
Refactored, modular wx UI for the library manager.

This package intentionally replaces the old monolithic `ui.py` while keeping
the same external entry points used by `plugin.py`.
"""

from .dialogs import RepoSettingsDialog
from .main_window import MainDialog

__all__ = ["MainDialog", "RepoSettingsDialog"]
