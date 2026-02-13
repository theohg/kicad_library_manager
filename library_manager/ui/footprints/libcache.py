from __future__ import annotations

import os
import re
import threading
from typing import Any

import wx

from ...suggest import group_density_variants, list_footprints
from ..kicad_env import expand_kicad_uri, kicad_config_root, kicad_version_dir, prime_kicad_env_vars, project_root_from_repo


def _extract_lib_blocks(txt: str) -> list[str]:
    """
    Minimal s-expression block extraction for (lib ...) entries.
    """
    out: list[str] = []
    needle = "(lib"
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
    Parse fp-lib-table, returning {libName: {type, uri, descr}}.
    Ported in simplified form from ui.py.
    """
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            txt = f.read()
    except Exception:
        return {}

    libs: dict[str, dict[str, str]] = {}
    for blk in _extract_lib_blocks(txt):
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
    Return fp-lib-table paths in priority order (project first, then user/global).
    Ported from ui.py's approach.
    """
    proj = project_root_from_repo(repo_path)
    out: list[str] = []
    p_fp = os.path.join(proj, "fp-lib-table")
    if os.path.exists(p_fp):
        out.append(p_fp)

    root = kicad_config_root()
    if root:
        vdir = kicad_version_dir(root) or root
        cand_dirs = [vdir]
        if os.path.abspath(vdir) != os.path.abspath(root):
            cand_dirs.append(root)
        for d in cand_dirs:
            c_fp = os.path.join(d, "fp-lib-table")
            if os.path.exists(c_fp) and c_fp not in out:
                out.append(c_fp)
    return out


class FootprintLibraryCache:
    """
    Background-loaded combined (project + global) footprint index.
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
                "footprints": [],
                "footprint_groups": {},
                "fp_lib_dirs": {},
                "error": "",
            }
            self._state_by_repo[repo_path] = st

        def work():
            try:
                # Prime KiCad env vars so ${KICAD*_FOOTPRINT_DIR} expands correctly.
                try:
                    prime_kicad_env_vars()
                except Exception:
                    pass
                local_fps = list_footprints(repo_path)
                fps = list(local_fps)
                fp_dirs: dict[str, str] = {}

                for t in _lib_table_paths(repo_path):
                    for name, meta in _parse_lib_table(t, repo_path).items():
                        typ = (meta.get("type") or "").lower()
                        uri = meta.get("uri") or ""
                        if typ and "kicad" not in typ:
                            continue
                        if uri and uri.lower().endswith(".pretty") and os.path.isdir(uri):
                            fp_dirs[name] = uri

                for lib_name, pretty_dir in fp_dirs.items():
                    try:
                        for fn in os.listdir(pretty_dir):
                            if not fn.endswith(".kicad_mod"):
                                continue
                            fp = os.path.splitext(fn)[0]
                            fps.append(f"{lib_name}:{fp}")
                    except Exception:
                        continue

                fps = sorted(set(fps))
                groups = group_density_variants(fps)
                return (fps, groups, fp_dirs, "")
            except Exception as e:  # noqa: BLE001
                return ([], {}, {}, str(e))

        def done(res, err):
            fps, groups, fp_dirs, err_txt = res if res else ([], {}, {}, "load failed")
            with self._lock:
                st2 = self._state_by_repo.get(repo_path) or {}
                st2["loading"] = False
                st2["loaded"] = True if not err_txt else False
                st2["footprints"] = fps
                st2["footprint_groups"] = groups
                st2["fp_lib_dirs"] = fp_dirs
                st2["error"] = err_txt
                self._state_by_repo[repo_path] = st2

        def runner() -> None:
            res = None
            err = None
            try:
                res = work()
            except Exception as e:  # noqa: BLE001
                err = e
            try:
                wx.CallAfter(done, res, err)
            except Exception:
                return

        threading.Thread(target=runner, daemon=True).start()

    def snapshot(self, repo_path: str) -> dict[str, Any]:
        repo_path = os.path.abspath(repo_path or "")
        with self._lock:
            st = self._state_by_repo.get(repo_path) or {
                "loading": False,
                "loaded": False,
                "footprints": [],
                "footprint_groups": {},
                "fp_lib_dirs": {},
                "error": "",
            }
            return dict(st)


FP_LIBCACHE = FootprintLibraryCache()


def resolve_footprint_pretty_dir(repo_path: str, lib: str) -> str | None:
    """
    Prefer repo-local Footprints scan later; this is for preview/metadata lookups.
    """
    st = FP_LIBCACHE.snapshot(repo_path)
    return (st.get("fp_lib_dirs") or {}).get((lib or "").strip())

