from __future__ import annotations

import os
from dataclasses import dataclass

import wx

from ...suggest import group_density_variants, list_footprints
from ..assets.asset_browser_dialog import AssetBrowserDialogBase
from ..git_ops import git_status_entries
from .libcache import FP_LIBCACHE
from .ops import (
    extract_kicad_footprint_descr,
    find_footprint_mod_any,
    find_pretty_dir_repo_local,
    render_footprint_svg,
)


def _on_create_footprint(evt: wx.CommandEvent) -> None:
    """
    Delegate to the main window if possible (legacy behavior).
    """
    try:
        dlg = evt.GetEventObject().GetParent()
    except Exception:
        dlg = None
    try:
        parent = dlg.GetParent() if dlg else None
    except Exception:
        parent = None
    try:
        if parent and hasattr(parent, "_on_create_footprint"):
            parent._on_create_footprint(evt)  # type: ignore[misc]
            return
    except Exception:
        pass
    wx.MessageBox("Footprint generator unavailable.", "Create footprint", wx.OK | wx.ICON_WARNING)


@dataclass(frozen=True)
class _FootprintProvider:
    kind_title: str = "Browse footprints"
    kind_label: str = "Footprints"
    item_label: str = "footprint"
    tree_col1: str = "Footprint"
    tree_col2: str = "Description / tags"
    search_hint: str = "Search (name / description / tags)"
    preview_box_title: str = "Preview"
    empty_preview_label: str = "(select a footprint)"

    scope_dirs: list[str] = None  # type: ignore[assignment]
    scope_key: str = "footprints"
    preview_kind_dir: str = "fp"
    preview_cache_key_prefix: str = "fp_browse"

    index = FP_LIBCACHE
    snapshot_key_items: str = "footprints"

    create_button_label: str | None = "Create footprint..."
    on_create = staticmethod(_on_create_footprint)

    # Picker-only option shown when the browser is opened from add/edit dialogs.
    picker_show_all_densities: bool = True
    picker_all_densities_default: bool = True
    picker_all_densities_label: str = "All densities (N;L;M) when available"

    def __post_init__(self):
        object.__setattr__(self, "scope_dirs", ["Footprints"])

    def list_local_refs(self, repo_path: str) -> list[str]:
        # Include on-disk footprints plus locally deleted ones (so they can be shown
        # as "DELETED" placeholders, like component pending-delete rows).
        refs = set(list_footprints(repo_path))
        try:
            entries = git_status_entries(repo_path)
        except Exception:
            entries = []

        for st, p in entries:
            s = (st or "").strip()
            if "D" not in s:
                continue
            rp = (p or "").replace("\\", "/").strip()
            if not rp.startswith("Footprints/") or not rp.lower().endswith(".kicad_mod"):
                continue
            parts = rp.split("/")
            pretty = ""
            for seg in parts:
                if seg.lower().endswith(".pretty"):
                    pretty = seg
            if not pretty:
                continue
            lib = pretty[:-7] if pretty.lower().endswith(".pretty") else pretty
            fn = parts[-1] if parts else ""
            fp = fn[:-10] if fn.lower().endswith(".kicad_mod") else ""
            if lib and fp:
                refs.add(f"{lib}:{fp}")

        return sorted(refs)

    def group_variants(self, refs: list[str]) -> dict[str, list[str]]:
        return dict(group_density_variants(refs))

    def lib_is_repo_local(self, repo_path: str, lib: str) -> bool:
        p = find_pretty_dir_repo_local(repo_path, (lib or "").strip())
        return bool(p and os.path.isdir(p))

    def rel_prefix_for_lib(self, repo_path: str, lib: str) -> str:
        pretty = find_pretty_dir_repo_local(repo_path, (lib or "").strip())
        if not pretty or not os.path.isdir(pretty):
            return ""
        try:
            rel = os.path.relpath(pretty, repo_path).replace(os.sep, "/").rstrip("/") + "/"
            return rel
        except Exception:
            return ""

    def rel_path_for_ref(self, repo_path: str, ref: str) -> str:
        if ":" not in (ref or ""):
            return ""
        lib, fp = ref.split(":", 1)
        pretty = find_pretty_dir_repo_local(repo_path, lib)
        if not pretty:
            return ""
        # IMPORTANT: do not require the file to exist on disk.
        # We use this path for status icons vs origin/<branch>, which must reflect
        # remote deletions even if the working tree is missing the file.
        abs_p = os.path.join(pretty, f"{fp}.kicad_mod")
        try:
            rel = os.path.relpath(abs_p, repo_path)
            return rel.replace(os.sep, "/")
        except Exception:
            return ""

    def source_mtime_for_ref(self, repo_path: str, ref: str) -> str:
        if ":" not in (ref or ""):
            return "0"
        lib, fpname = ref.split(":", 1)
        mod = find_footprint_mod_any(repo_path, lib, fpname)
        try:
            return str(os.path.getmtime(mod)) if mod and os.path.exists(mod) else "0"
        except Exception:
            return "0"

    def extract_description_for_ref(self, repo_path: str, ref: str) -> str:
        if ":" not in (ref or ""):
            return ""
        lib, fpname = ref.split(":", 1)
        mod = find_footprint_mod_any(repo_path, lib, fpname)
        if not mod or not os.path.exists(mod):
            return ""
        return extract_kicad_footprint_descr(mod)

    def render_svg(self, repo_path: str, ref: str, out_svg_path: str) -> None:
        return render_footprint_svg(repo_path, ref, out_svg_path)

    def can_delete_ref(self, repo_path: str, base_ref: str) -> tuple[bool, str]:
        if ":" not in (base_ref or ""):
            return (False, "Select a footprint first.")
        lib = base_ref.split(":", 1)[0].strip()
        pretty = find_pretty_dir_repo_local(repo_path, lib)
        if not pretty:
            return (
                False,
                "This footprint comes from a global/system library.\n\n"
                "For safety, deletion is only supported for repo-local footprints under `Footprints/`.",
            )
        return (True, "")

    def delete_ref_and_variants(self, repo_path: str, base_ref: str, variants: list[str]) -> list[str]:
        failed: list[str] = []
        mods: list[str] = []
        for v in list(variants or []):
            if ":" not in (v or ""):
                continue
            vlib, vfp = v.split(":", 1)
            mod = find_footprint_mod_any(repo_path, vlib, vfp)
            if mod and os.path.exists(mod):
                mods.append(mod)
        for p in mods:
            try:
                os.remove(p)
            except Exception as e:
                failed.append(f"{os.path.basename(p)} ({e})")
        return failed


class FootprintBrowserDialog(AssetBrowserDialogBase):
    def __init__(self, parent: wx.Window, repo_path: str, *, picker_mode: bool = False):
        super().__init__(parent, repo_path, _FootprintProvider(), picker_mode=picker_mode)

