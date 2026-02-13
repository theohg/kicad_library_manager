from __future__ import annotations

import os
from dataclasses import dataclass

import wx

from ...suggest import list_symbols
from ..assets.asset_browser_dialog import AssetBrowserDialogBase
from .libcache import SYMBOL_LIBCACHE, resolve_symbol_lib_path
from .ops import extract_kicad_symbol_meta, remove_kicad_symbol_from_lib, render_symbol_svg


def _group_identity(refs: list[str]) -> dict[str, list[str]]:
    return {r: [r] for r in refs if r}


@dataclass(frozen=True)
class _SymbolProvider:
    kind_title: str = "Browse symbols"
    kind_label: str = "Symbols"
    item_label: str = "symbol"
    tree_col1: str = "Symbol"
    tree_col2: str = "Description / datasheet"
    search_hint: str = "Search (name / description / datasheet)"
    preview_box_title: str = "Preview"
    empty_preview_label: str = "(select a symbol)"

    scope_dirs: list[str] = None  # type: ignore[assignment]
    scope_key: str = "symbols"
    preview_kind_dir: str = "sym"
    preview_cache_key_prefix: str = "sym_browse"

    index = SYMBOL_LIBCACHE
    snapshot_key_items: str = "symbols"
    show_index_line: bool = True
    descr_prefetch_status_target: str = "index_line"

    create_button_label: str | None = None
    on_create = None

    def __post_init__(self):
        object.__setattr__(self, "scope_dirs", ["Symbols"])

    def list_local_refs(self, repo_path: str) -> list[str]:
        # IMPORTANT: avoid scanning/parsing local `.kicad_sym` files on the UI thread.
        # That can hitch KiCad for seconds on large libraries.
        #
        # We prefer using the background cache (SYMBOL_LIBCACHE) to provide refs.
        try:
            st = SYMBOL_LIBCACHE.snapshot(repo_path)
            if not bool(st.get("loaded")):
                # Cache is still loading (or failed). Do not block the UI here.
                return []
            syms = list(st.get("symbols") or [])
            sym_files = dict(st.get("sym_lib_files") or {})
            # Repo-local libs are under <repo>/Symbols/*.kicad_sym
            try:
                root = os.path.abspath(os.path.join(repo_path, "Symbols")) + os.sep
            except Exception:
                root = os.path.join(repo_path, "Symbols") + os.sep
            local_libs: set[str] = set()
            for lib, p in sym_files.items():
                try:
                    ap = os.path.abspath(str(p or ""))
                except Exception:
                    ap = str(p or "")
                if ap.startswith(root):
                    local_libs.add(str(lib or "").strip())
            if not local_libs:
                return []
            out = [r for r in syms if (r.split(":", 1)[0] if ":" in r else "") in local_libs]
            return sorted(set([x for x in out if x]))
        except Exception:
            # Best-effort fallback: keep old behavior only if needed.
            # Note: this may still be slow on huge symbol libs.
            return list_symbols(repo_path)

    def group_variants(self, refs: list[str]) -> dict[str, list[str]]:
        return _group_identity(refs)

    def lib_is_repo_local(self, repo_path: str, lib: str) -> bool:
        p = os.path.join(repo_path, "Symbols", f"{(lib or '').strip()}.kicad_sym")
        return os.path.exists(p)

    def rel_prefix_for_lib(self, repo_path: str, lib: str) -> str:
        # file-level asset: Symbols/<lib>.kicad_sym
        lib = (lib or "").strip()
        if not lib:
            return ""
        p = os.path.join(repo_path, "Symbols", f"{lib}.kicad_sym")
        if not os.path.exists(p):
            return ""
        try:
            rel = os.path.relpath(p, repo_path)
            return rel.replace(os.sep, "/")
        except Exception:
            return ""

    def rel_path_for_ref(self, repo_path: str, ref: str) -> str:
        # Symbol status is file-level: Symbols/<lib>.kicad_sym
        if ":" not in (ref or ""):
            return ""
        lib = ref.split(":", 1)[0].strip()
        p = os.path.join(repo_path, "Symbols", f"{lib}.kicad_sym")
        if not os.path.exists(p):
            return ""
        try:
            rel = os.path.relpath(p, repo_path)
            return rel.replace(os.sep, "/")
        except Exception:
            return ""

    def source_mtime_for_ref(self, repo_path: str, ref: str) -> str:
        if ":" not in (ref or ""):
            return "0"
        lib = ref.split(":", 1)[0].strip()
        p = resolve_symbol_lib_path(repo_path, lib) or ""
        try:
            return str(os.path.getmtime(p)) if p and os.path.exists(p) else "0"
        except Exception:
            return "0"

    def extract_description_for_ref(self, repo_path: str, ref: str) -> str:
        if ":" not in (ref or ""):
            return ""
        lib, sym = ref.split(":", 1)

        # Prefer cached metadata from SYMBOL_LIBCACHE (fast).
        try:
            st = SYMBOL_LIBCACHE.snapshot(repo_path)
            mm = (st.get("sym_meta") or {}).get(ref)
            if mm:
                d, ds = mm
                return " ".join([x for x in [str(d).strip(), str(ds).strip()] if str(x).strip()]).strip()
        except Exception:
            pass

        # If missing, lazily load meta for this library once (still off-UI-thread in our callers).
        try:
            SYMBOL_LIBCACHE.ensure_meta_loaded(repo_path, lib)
            st = SYMBOL_LIBCACHE.snapshot(repo_path)
            mm = (st.get("sym_meta") or {}).get(ref)
            if mm:
                d, ds = mm
                return " ".join([x for x in [str(d).strip(), str(ds).strip()] if str(x).strip()]).strip()
        except Exception:
            pass

        # Fallback: extract from file on demand (slower).
        lib_path = resolve_symbol_lib_path(repo_path, lib) or ""
        if not lib_path or not os.path.exists(lib_path):
            return ""
        d, ds = extract_kicad_symbol_meta(lib_path, sym)
        return " ".join([x for x in [d.strip(), ds.strip()] if x.strip()]).strip()

    def render_svg(self, repo_path: str, ref: str, out_svg_path: str) -> None:
        return render_symbol_svg(repo_path, ref, out_svg_path)

    def can_delete_ref(self, repo_path: str, base_ref: str) -> tuple[bool, str]:
        if ":" not in (base_ref or ""):
            return (False, "Select a symbol first.")
        lib = base_ref.split(":", 1)[0].strip()
        if not self.lib_is_repo_local(repo_path, lib):
            return (
                False,
                "This symbol comes from a global/system library.\n\n"
                "For safety, deletion is only supported for repo-local symbols under `Symbols/`.",
            )
        return (True, "")

    def delete_ref_and_variants(self, repo_path: str, base_ref: str, variants: list[str]) -> list[str]:
        # Symbols are stored per-library. Deleting a symbol edits the .kicad_sym file.
        failed: list[str] = []
        if ":" not in (base_ref or ""):
            return ["Bad symbol ref"]
        lib, sym = base_ref.split(":", 1)
        lib_path = resolve_symbol_lib_path(repo_path, lib) or ""
        if not lib_path or not os.path.exists(lib_path):
            return [f"Symbol library not found for '{lib}'"]
        try:
            remove_kicad_symbol_from_lib(lib_path, sym)
        except Exception as e:
            failed.append(f"{sym} ({e})")
        return failed


class SymbolBrowserDialog(AssetBrowserDialogBase):
    def __init__(self, parent: wx.Window, repo_path: str, *, picker_mode: bool = False):
        super().__init__(parent, repo_path, _SymbolProvider(), picker_mode=picker_mode)

