from __future__ import annotations

import os
import re
import threading
from typing import Any

import wx

from ...suggest import list_symbols
from ..kicad_env import expand_kicad_uri, kicad_config_root, kicad_version_dir, prime_kicad_env_vars, project_root_from_repo


def _extract_blocks(txt: str, needle: str) -> list[str]:
    """
    Minimal s-expression block extraction for entries like (lib ...) or (symbol ...).
    """
    out: list[str] = []
    i = 0
    while True:
        start = txt.find(needle, i)
        if start < 0:
            break
        depth = 0
        in_str = False
        esc = False
        j = start
        while j < len(txt):
            ch = txt[j]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
            else:
                if ch == '"':
                    in_str = True
                elif ch == "(":
                    depth += 1
                elif ch == ")":
                    depth -= 1
                    if depth == 0 and j > start:
                        out.append(txt[start : j + 1])
                        i = j + 1
                        break
            j += 1
        else:
            break
    return out


def _parse_lib_table(path: str, repo_path: str) -> dict[str, dict[str, str]]:
    """
    Parse sym-lib-table, returning {libName: {type, uri, descr}}.
    """
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            txt = f.read()
    except Exception:
        return {}

    libs: dict[str, dict[str, str]] = {}
    for blk in _extract_blocks(txt, "(lib"):

        def _field(key: str) -> str:
            m = re.search(r'\(%s\s+"([^"]+)"\)' % re.escape(key), blk)
            if m:
                return (m.group(1) or "").strip()
            m = re.search(r"\(%s\s+([^\s\)]+)\)" % re.escape(key), blk)
            if m:
                return (m.group(1) or "").strip()
            return ""

        name = _field("name")
        typ = _field("type")
        uri = _field("uri")
        m_descr = re.search(r'\(descr\s+"([^"]*)"\)', blk)
        descr = (m_descr.group(1).strip() if m_descr else _field("descr"))
        if not name or not uri:
            continue
        libs[name] = {"type": typ, "uri": expand_kicad_uri(uri, repo_path), "descr": descr}
    return libs


def _lib_table_paths(repo_path: str) -> list[str]:
    """
    Return sym-lib-table paths in priority order (project first, then user/global).
    """
    proj = project_root_from_repo(repo_path)
    out: list[str] = []
    p_sym = os.path.join(proj, "sym-lib-table")
    if os.path.exists(p_sym):
        out.append(p_sym)

    root = kicad_config_root()
    if root:
        vdir = kicad_version_dir(root) or root
        cand_dirs = [vdir]
        if os.path.abspath(vdir) != os.path.abspath(root):
            cand_dirs.append(root)
        for d in cand_dirs:
            c_sym = os.path.join(d, "sym-lib-table")
            if os.path.exists(c_sym) and c_sym not in out:
                out.append(c_sym)
    return out


_SYMBOL_RE = re.compile(r'\(symbol\s+"([^"]+)"')
_UNIT_VARIANT_RE = re.compile(r".*_\d+_\d+$")


def _scan_kicad_sym_file_names(sym_lib_path: str, lib_name: str) -> list[str]:
    """
    Return symbol refs for a .kicad_sym file.

    This is intentionally fast (name-only), similar to how footprints index by
    listing `.kicad_mod` filenames. Metadata (Description/Datasheet) is loaded
    lazily per-library when needed.
    """
    try:
        with open(sym_lib_path, "r", encoding="utf-8", errors="ignore") as f:
            txt = f.read()
    except Exception:
        return []

    refs: list[str] = []
    for m in _SYMBOL_RE.finditer(txt):
        try:
            name = (m.group(1) or "").strip()
        except Exception:
            name = ""
        if not name or _UNIT_VARIANT_RE.match(name):
            continue
        refs.append(f"{lib_name}:{name}")
    return sorted(set(refs))


def _scan_kicad_sym_file_meta(sym_lib_path: str, lib_name: str) -> dict[str, tuple[str, str]]:
    """
    Return meta map for a .kicad_sym file: "Lib:Sym" -> (Description, Datasheet).
    Loaded lazily per-library.
    """
    try:
        with open(sym_lib_path, "r", encoding="utf-8", errors="ignore") as f:
            txt = f.read()
    except Exception:
        return {}

    meta: dict[str, tuple[str, str]] = {}
    for blk in _extract_blocks(txt, '(symbol "'):
        m = _SYMBOL_RE.search(blk)
        if not m:
            continue
        name = (m.group(1) or "").strip()
        if not name or _UNIT_VARIANT_RE.match(name):
            continue
        desc = ""
        ds = ""
        try:
            mm = re.search(r'\(property\s+"Description"\s+"([^"]*)"', blk)
            desc = (mm.group(1).strip() if mm else "")
            mm2 = re.search(r'\(property\s+"Datasheet"\s+"([^"]*)"', blk)
            ds = (mm2.group(1).strip() if mm2 else "")
        except Exception:
            pass
        meta[f"{lib_name}:{name}"] = (desc, ds)
    return meta


class SymbolLibraryCache:
    """
    Background-loaded combined (project + global) symbol index.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._state_by_repo: dict[str, dict[str, Any]] = {}

    def ensure_started(self, repo_path: str) -> None:
        repo_path = os.path.abspath(repo_path or "")
        with self._lock:
            st = self._state_by_repo.get(repo_path)
            if st and st.get("loading"):
                return
            if st and st.get("loaded"):
                return
            st = {
                "loading": True,
                "loaded": False,
                "symbols": [],
                "sym_meta": {},  # ref -> (descr, datasheet) (lazy per library)
                "sym_lib_files": {},  # lib -> .kicad_sym abs path
                "sym_meta_loaded_libs": set(),  # libs whose meta has been loaded
                "sym_meta_events": {},  # lib -> threading.Event for in-flight meta load
                "error": "",
            }
            self._state_by_repo[repo_path] = st

        def work():
            try:
                try:
                    prime_kicad_env_vars()
                except Exception:
                    pass

                local_syms = list_symbols(repo_path)
                syms = list(local_syms)

                sym_files: dict[str, str] = {}

                # Repo-local libraries: Symbols/<lib>.kicad_sym
                sym_dir = os.path.join(repo_path, "Symbols")
                try:
                    for fn in os.listdir(sym_dir):
                        if not fn.endswith(".kicad_sym"):
                            continue
                        lib = os.path.splitext(fn)[0]
                        p = os.path.join(sym_dir, fn)
                        sym_files[lib] = p
                except Exception:
                    pass

                # Global/project libraries from sym-lib-table
                for t in _lib_table_paths(repo_path):
                    for name, meta in _parse_lib_table(t, repo_path).items():
                        uri = (meta.get("uri") or "").strip()
                        if not uri:
                            continue
                        if uri.lower().endswith(".kicad_sym") and os.path.exists(uri):
                            sym_files.setdefault(name, uri)

                # Scan each lib file once for symbol NAMES only (fast path).
                for lib_name, lib_path in list(sym_files.items()):
                    syms.extend(_scan_kicad_sym_file_names(lib_path, lib_name))

                syms = sorted(set(syms))
                return (syms, sym_files, "")
            except Exception as e:  # noqa: BLE001
                return ([], {}, str(e))

        def done(res, _err):
            syms, sym_files, err_txt = res if res else ([], {}, "load failed")
            with self._lock:
                st2 = self._state_by_repo.get(repo_path) or {}
                st2["loading"] = False
                st2["loaded"] = True if not err_txt else False
                st2["symbols"] = syms
                st2["sym_lib_files"] = sym_files
                st2.setdefault("sym_meta", {})
                st2.setdefault("sym_meta_loaded_libs", set())
                st2.setdefault("sym_meta_events", {})
                st2["error"] = err_txt
                self._state_by_repo[repo_path] = st2

        def runner() -> None:
            res = None
            try:
                res = work()
            except Exception as e:  # noqa: BLE001
                res = ([], {}, {}, str(e))
            try:
                wx.CallAfter(done, res, None)
            except Exception:
                return

        threading.Thread(target=runner, daemon=True).start()

    def ensure_meta_loaded(self, repo_path: str, lib: str, *, wait_s: float = 10.0) -> None:
        """
        Ensure Description/Datasheet metadata is loaded for a library nickname.
        Safe to call from background threads; will block up to wait_s if another
        thread is already loading the same library.
        """
        repo_path = os.path.abspath(repo_path or "")
        lib = (lib or "").strip()
        if not repo_path or not lib:
            return

        do_load = False
        ev: threading.Event | None = None
        lib_path = ""
        with self._lock:
            st = self._state_by_repo.get(repo_path) or {}
            loaded_libs = st.get("sym_meta_loaded_libs")
            if isinstance(loaded_libs, set) and lib in loaded_libs:
                return

            lib_path = ((st.get("sym_lib_files") or {}) or {}).get(lib) or ""
            if not lib_path or not os.path.exists(lib_path):
                return

            ev_map = st.get("sym_meta_events")
            if not isinstance(ev_map, dict):
                ev_map = {}
            ev = ev_map.get(lib)
            if isinstance(ev, threading.Event):
                # someone else is loading; we'll wait below
                do_load = False
            else:
                ev = threading.Event()
                ev_map[lib] = ev
                st["sym_meta_events"] = ev_map
                if not isinstance(loaded_libs, set):
                    loaded_libs = set()
                    st["sym_meta_loaded_libs"] = loaded_libs
                self._state_by_repo[repo_path] = st
                do_load = True

        if not ev:
            return

        if not do_load:
            try:
                ev.wait(timeout=max(0.0, float(wait_s)))
            except Exception:
                return
            return

        # We are the loader for this library.
        meta_map: dict[str, tuple[str, str]] = {}
        try:
            meta_map = _scan_kicad_sym_file_meta(lib_path, lib)
        except Exception:
            meta_map = {}

        with self._lock:
            st = self._state_by_repo.get(repo_path) or {}
            try:
                mm = st.get("sym_meta")
                if not isinstance(mm, dict):
                    mm = {}
                    st["sym_meta"] = mm
                mm.update(meta_map)
            except Exception:
                pass
            try:
                loaded_libs = st.get("sym_meta_loaded_libs")
                if not isinstance(loaded_libs, set):
                    loaded_libs = set()
                    st["sym_meta_loaded_libs"] = loaded_libs
                loaded_libs.add(lib)
            except Exception:
                pass
            try:
                ev_map = st.get("sym_meta_events")
                if isinstance(ev_map, dict):
                    ev_map.pop(lib, None)
            except Exception:
                pass
            self._state_by_repo[repo_path] = st
        try:
            ev.set()
        except Exception:
            pass

    def snapshot(self, repo_path: str) -> dict[str, Any]:
        repo_path = os.path.abspath(repo_path or "")
        with self._lock:
            st = self._state_by_repo.get(repo_path) or {
                "loading": False,
                "loaded": False,
                "symbols": [],
                "sym_meta": {},
                "sym_lib_files": {},
                "sym_meta_loaded_libs": set(),
                "sym_meta_events": {},
                "error": "",
            }
            return dict(st)


SYMBOL_LIBCACHE = SymbolLibraryCache()


def resolve_symbol_lib_path(repo_path: str, lib: str) -> str | None:
    """
    Resolve a lib nickname to a .kicad_sym file path (repo-local first, else indexed).
    """
    lib = (lib or "").strip()
    if not lib:
        return None
    p = os.path.join(repo_path, "Symbols", f"{lib}.kicad_sym")
    if os.path.exists(p):
        return p
    st = SYMBOL_LIBCACHE.snapshot(repo_path)
    return (st.get("sym_lib_files") or {}).get(lib)

