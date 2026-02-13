"""
Debug helpers for the KiCad Library Manager plugin.

When KiCad's embedded Python process segfaults (often due to C/C++ extensions),
regular Python exception handling can't help. Python's `faulthandler` can still
dump the Python traceback of all threads on fatal signals, which is often enough
to pinpoint which plugin code path triggers the crash.
"""

from __future__ import annotations

import faulthandler
import os
import platform
import signal
import sys
import tempfile
import time
from typing import TextIO

_ENABLED = False
_LOG_FH: TextIO | None = None


def _truthy_env(name: str) -> bool:
    v = os.environ.get(name, "")
    return v.strip().lower() in {"1", "true", "yes", "y", "on"}


def _open_log_file() -> TextIO:
    # Use a tempdir path so we can always write even if the project is read-only.
    #
    # IMPORTANT: default to a stable filename so users don't have to hunt for the PID.
    # If multiple KiCad instances run concurrently, logs will interleave (acceptable in debug mode).
    path = (os.environ.get("KICAD_LIBRARY_MANAGER_DEBUG_LOG") or "").strip()
    if not path:
        path = os.path.join(tempfile.gettempdir(), "kicad_library_manager_fault.log")
    fh = open(path, "a", buffering=1, encoding="utf-8", errors="replace")

    fh.write("\n")
    fh.write("=" * 80 + "\n")
    fh.write(f"KiCad Library Manager debug log (pid={os.getpid()})\n")
    fh.write(f"timestamp: {time.strftime('%Y-%m-%d %H:%M:%S %z')}\n")
    fh.write(f"python: {sys.version.replace(os.linesep, ' ')}\n")
    fh.write(f"platform: {platform.platform()}\n")
    fh.write(f"argv: {sys.argv!r}\n")
    fh.write(f"KICAD_LIBRARY_MANAGER_DEBUG={os.environ.get('KICAD_LIBRARY_MANAGER_DEBUG', '')!r}\n")
    fh.write(f"log_path: {path}\n")
    fh.write("=" * 80 + "\n")
    fh.flush()
    return fh


def enable_debug_segfault_trace() -> str | None:
    """
    Enable traceback dumps for fatal signals (SIGSEGV, SIGABRT, ...).

    Returns the log file path if enabled, else None.
    """
    global _ENABLED, _LOG_FH
    if _ENABLED:
        try:
            return getattr(_LOG_FH, "name", None)
        except Exception:
            return None

    if not _truthy_env("KICAD_LIBRARY_MANAGER_DEBUG"):
        return None

    try:
        _LOG_FH = _open_log_file()
        try:
            _LOG_FH.write("[debug] fault handler enabled\n")
            _LOG_FH.flush()
        except Exception:
            pass
        # Install handlers for fatal errors and dump all threads.
        faulthandler.enable(file=_LOG_FH, all_threads=True)

        # Be explicit about signals and chain to any existing handlers.
        for sig in (
            signal.SIGSEGV,
            signal.SIGABRT,
            signal.SIGFPE,
            signal.SIGILL,
        ):
            try:
                faulthandler.register(sig, file=_LOG_FH, all_threads=True, chain=True)
            except Exception:
                # Some platforms may not expose all signals.
                pass

        # SIGBUS isn't available on all platforms, but is on Linux.
        if hasattr(signal, "SIGBUS"):
            try:
                faulthandler.register(signal.SIGBUS, file=_LOG_FH, all_threads=True, chain=True)
            except Exception:
                pass

        # Optional: allow manual traceback dump without crashing:
        #   kill -USR2 <kicad-pid>
        if hasattr(signal, "SIGUSR2"):
            try:
                faulthandler.register(signal.SIGUSR2, file=_LOG_FH, all_threads=True, chain=True)
            except Exception:
                pass

        _ENABLED = True
        try:
            return _LOG_FH.name  # type: ignore[attr-defined]
        except Exception:
            return None
    except Exception:
        # Never break KiCad startup due to debug logging.
        _ENABLED = False
        try:
            if _LOG_FH:
                _LOG_FH.close()
        except Exception:
            pass
        _LOG_FH = None
        return None


def install_debug_hooks_if_requested() -> str | None:
    """
    Convenience wrapper for calling early at import time.
    """
    return enable_debug_segfault_trace()


def enable_segfault_trace_always(*, path: str | None = None) -> str | None:
    """
    Always-on variant (ignores env vars). Writes to a stable file by default.
    Intended for debugging hard crashes in IPC plugin process.
    """
    global _ENABLED, _LOG_FH
    if _ENABLED:
        try:
            return getattr(_LOG_FH, "name", None)
        except Exception:
            return None
    try:
        if not path:
            base = os.environ.get("XDG_CACHE_HOME") or os.path.join(os.path.expanduser("~"), ".cache")
            d = os.path.join(base, "kicad_library_manager")
            try:
                os.makedirs(d, exist_ok=True)
            except Exception:
                pass
            path = os.path.join(d, "fault_handler.log")
        _LOG_FH = open(path, "a", buffering=1, encoding="utf-8", errors="replace")
        _LOG_FH.write("\n" + "=" * 80 + "\n")
        _LOG_FH.write(f"KiCad Library Manager fault handler (pid={os.getpid()})\n")
        _LOG_FH.write(f"timestamp: {time.strftime('%Y-%m-%d %H:%M:%S %z')}\n")
        _LOG_FH.write(f"python: {sys.version.replace(os.linesep, ' ')}\n")
        _LOG_FH.write(f"platform: {platform.platform()}\n")
        _LOG_FH.write(f"argv: {sys.argv!r}\n")
        _LOG_FH.write(f"log_path: {path}\n")
        _LOG_FH.write("=" * 80 + "\n")
        _LOG_FH.flush()

        faulthandler.enable(file=_LOG_FH, all_threads=True)
        for sig in (signal.SIGSEGV, signal.SIGABRT, signal.SIGFPE, signal.SIGILL):
            try:
                faulthandler.register(sig, file=_LOG_FH, all_threads=True, chain=True)
            except Exception:
                pass
        if hasattr(signal, "SIGBUS"):
            try:
                faulthandler.register(signal.SIGBUS, file=_LOG_FH, all_threads=True, chain=True)
            except Exception:
                pass
        if hasattr(signal, "SIGUSR2"):
            try:
                faulthandler.register(signal.SIGUSR2, file=_LOG_FH, all_threads=True, chain=True)
            except Exception:
                pass

        _ENABLED = True
        return path
    except Exception:
        _ENABLED = False
        try:
            if _LOG_FH:
                _LOG_FH.close()
        except Exception:
            pass
        _LOG_FH = None
        return None


def debug_log(msg: str) -> None:
    """
    Best-effort breadcrumb logging into the same fault log.
    Safe to call from anywhere; does nothing unless debug mode is enabled.
    """
    global _LOG_FH
    # Lazy-enable so breadcrumbs work even if the bootstrap entrypoint changed.
    if (not _ENABLED) or (not _LOG_FH):
        if _truthy_env("KICAD_LIBRARY_MANAGER_DEBUG"):
            enable_debug_segfault_trace()
    if not _ENABLED or not _LOG_FH:
        return
    try:
        ts = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        _LOG_FH.write(f"[debug {ts}] {msg}\n")
        _LOG_FH.flush()
    except Exception:
        pass

