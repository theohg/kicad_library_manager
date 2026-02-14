from __future__ import annotations

import glob
import hashlib
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass

import wx

from ..._subprocess import SUBPROCESS_NO_WINDOW


PREVIEW_CACHE_VERSION = "4"


def cache_dir() -> str:
    base = os.environ.get("XDG_CACHE_HOME") or os.path.join(os.path.expanduser("~"), ".cache")
    d = os.path.join(base, "kicad_library_manager", "previews")
    os.makedirs(d, exist_ok=True)
    return d


def safe_name(s: str) -> str:
    s = (s or "").strip().replace(os.sep, "_")
    out: list[str] = []
    for ch in s:
        if ch.isalnum() or ch in ("-", "_", ".", "+"):
            out.append(ch)
        else:
            out.append("_")
    return ("".join(out)[:120] or "x").strip()


def hash_key(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8", errors="ignore")).hexdigest()[:16]


def _svg_intrinsic_wh(svg_path: str) -> tuple[float, float] | None:
    try:
        with open(svg_path, "r", encoding="utf-8", errors="ignore") as f:
            head = f.read(4096)
    except Exception:
        return None

    import re as _re

    m = _re.search(r'viewBox="([0-9eE+\-\.]+)\s+([0-9eE+\-\.]+)\s+([0-9eE+\-\.]+)\s+([0-9eE+\-\.]+)"', head)
    if m:
        try:
            w = float(m.group(3))
            h = float(m.group(4))
            if w > 0 and h > 0:
                return (w, h)
        except Exception:
            pass

    def _parse_len(attr: str) -> float | None:
        m2 = _re.search(attr + r'="([0-9eE+\-\.]+)', head)
        if not m2:
            return None
        try:
            v = float(m2.group(1))
            return v if v > 0 else None
        except Exception:
            return None

    w = _parse_len("width")
    h = _parse_len("height")
    if w and h:
        return (w, h)
    return None


def _fit_size(in_w: float, in_h: float, max_w: int, max_h: int) -> tuple[int, int]:
    mw = max(int(max_w), 100)
    mh = max(int(max_h), 100)
    if in_w <= 0 or in_h <= 0:
        return (mw, mh)
    s = min(mw / in_w, mh / in_h)
    w = max(int(in_w * s), 50)
    h = max(int(in_h * s), 50)
    return (w, h)


def wx_image_silent(path: str) -> wx.Image:
    null = None
    try:
        null = wx.LogNull()
    except Exception:
        null = None
    try:
        return wx.Image(path)
    finally:
        try:
            if null is not None:
                del null
        except Exception:
            pass


def svg_to_png(svg_path: str, out_png_path: str, width: int, height: int) -> None:
    """
    Port of ui.py `_svg_to_png`: tries rsvg-convert, inkscape, magick/convert.
    """
    w_req = max(int(width) if int(width) > 0 else 600, 100)
    h_req = max(int(height) if int(height) > 0 else 260, 100)
    intrinsic = _svg_intrinsic_wh(svg_path)
    if intrinsic:
        w, h = _fit_size(intrinsic[0], intrinsic[1], w_req, h_req)
    else:
        w, h = (w_req, h_req)

    out_dir = os.path.dirname(out_png_path)
    os.makedirs(out_dir, exist_ok=True)
    tmp_png = os.path.join(out_dir, f".tmp_{safe_name(os.path.basename(out_png_path))}.{os.getpid()}.png")
    try:
        if os.path.exists(tmp_png):
            os.remove(tmp_png)
    except Exception:
        pass

    rsvg = shutil.which("rsvg-convert")
    if rsvg:
        cp = subprocess.run([rsvg, "-w", str(w), "-h", str(h), "-o", tmp_png, svg_path], check=False, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, **SUBPROCESS_NO_WINDOW)
        if cp.returncode == 0 and os.path.exists(tmp_png) and os.path.getsize(tmp_png) > 0:
            os.replace(tmp_png, out_png_path)
            return
        raise RuntimeError((cp.stdout or "").strip() or "rsvg-convert failed")

    inkscape = shutil.which("inkscape")
    if inkscape:
        cp = subprocess.run([inkscape, svg_path, "-w", str(w), "-h", str(h), "-o", tmp_png], check=False, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, **SUBPROCESS_NO_WINDOW)
        if cp.returncode == 0 and os.path.exists(tmp_png) and os.path.getsize(tmp_png) > 0:
            os.replace(tmp_png, out_png_path)
            return
        raise RuntimeError((cp.stdout or "").strip() or "inkscape SVG export failed")

    magick = shutil.which("magick") or shutil.which("convert")
    if magick:
        cp = subprocess.run([magick, svg_path, "-resize", f"{w}x{h}", tmp_png], check=False, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, **SUBPROCESS_NO_WINDOW)
        if cp.returncode == 0 and os.path.exists(tmp_png) and os.path.getsize(tmp_png) > 0:
            os.replace(tmp_png, out_png_path)
            return
        raise RuntimeError((cp.stdout or "").strip() or "ImageMagick conversion failed")

    raise RuntimeError("No SVG->PNG converter found (install rsvg-convert or inkscape)")


def _file_ok(path: str) -> bool:
    try:
        return bool(path and os.path.exists(path) and os.path.getsize(path) > 0)
    except Exception:
        return False


def _crop_image_to_alpha(img: wx.Image, *, alpha_threshold: int = 5, pad_px: int = 2) -> wx.Image:
    """
    Crop an image to the bounding box of non-transparent pixels.
    """
    try:
        if not img or not img.IsOk():
            return img
        if not img.HasAlpha():
            return img
        w, h = int(img.GetWidth()), int(img.GetHeight())
        if w <= 0 or h <= 0:
            return img
        alpha = img.GetAlpha()
        if not alpha:
            return img
        mv = memoryview(alpha)
        thr = max(0, min(int(alpha_threshold), 255))
        minx, miny = w, h
        maxx, maxy = -1, -1
        for y in range(h):
            row = mv[y * w : (y + 1) * w]
            try:
                if max(row) <= thr:
                    continue
            except Exception:
                # Fallback: if max() fails for some buffer types, just scan.
                pass
            if y < miny:
                miny = y
            if y > maxy:
                maxy = y
            # Scan row to find left/right for this row.
            for x, a in enumerate(row):
                if int(a) > thr:
                    if x < minx:
                        minx = x
                    if x > maxx:
                        maxx = x
        if maxx < 0 or maxy < 0 or minx > maxx or miny > maxy:
            return img
        pad = max(int(pad_px), 0)
        minx = max(minx - pad, 0)
        miny = max(miny - pad, 0)
        maxx = min(maxx + pad, w - 1)
        maxy = min(maxy + pad, h - 1)
        rect = wx.Rect(int(minx), int(miny), int(maxx - minx + 1), int(maxy - miny + 1))
        return img.GetSubImage(rect)
    except Exception:
        return img


def letterbox_bitmap(
    src: wx.Bitmap,
    box_w: int,
    box_h: int,
    padding: float = 0.92,
    *,
    crop_to_alpha: bool = False,
) -> wx.Bitmap | None:
    """
    Port of ui.py `_letterbox_bitmap` with transparent background.
    """
    try:
        if not src or not src.IsOk():
            return None
        bw = max(int(box_w), 50)
        bh = max(int(box_h), 50)
        img = src.ConvertToImage()
        if not img.IsOk():
            return None
        sw, sh = img.GetWidth(), img.GetHeight()
        if sw <= 0 or sh <= 0:
            return None
        scale = min((bw * float(padding)) / sw, (bh * float(padding)) / sh)
        tw = max(int(sw * scale), 1)
        th = max(int(sh * scale), 1)
        img = img.Scale(tw, th, quality=wx.IMAGE_QUALITY_HIGH)
        if crop_to_alpha:
            img = _crop_image_to_alpha(img)
            try:
                tw, th = int(img.GetWidth()), int(img.GetHeight())
            except Exception:
                pass
        canvas = wx.Bitmap(bw, bh, 32)
        try:
            canvas.UseAlpha()
        except Exception:
            pass
        dc = wx.MemoryDC(canvas)
        dc.SetBackground(wx.Brush(wx.Colour(0, 0, 0, 0)))
        dc.Clear()
        x = (bw - tw) // 2
        y = (bh - th) // 2
        dc.DrawBitmap(wx.Bitmap(img), x, y, True)
        dc.SelectObject(wx.NullBitmap)
        return canvas
    except Exception:
        return None


def hires_target_px(win: wx.Window, want_w: int, want_h: int, quality_scale: float = 2.0) -> tuple[int, int]:
    try:
        sf = 1.0
        try:
            sf = float(win.GetContentScaleFactor())
        except Exception:
            sf = 1.0
        w = max(int(want_w * sf * quality_scale), 200)
        h = max(int(want_h * sf * quality_scale), 200)
        w = min(w, 2400)
        h = min(h, 1800)
        return (w, h)
    except Exception:
        return (max(int(want_w), 200), max(int(want_h), 200))


@dataclass(frozen=True)
class CachedRaster:
    png_path: str


def cached_svg_and_png(
    *,
    kind_dir: str,
    cache_key_prefix: str,
    ref: str,
    source_mtime: str,
    png_w: int,
    png_h: int,
    render_svg: callable,
) -> CachedRaster:
    """
    Shared caching strategy used by footprint/symbol browse and pick dialogs in ui.py.
    """
    key = hash_key(f"{cache_key_prefix}:{PREVIEW_CACHE_VERSION}:{ref}:{source_mtime}")
    out_svg = os.path.join(cache_dir(), kind_dir, safe_name(ref) + "_" + key + ".svg")
    if not _file_ok(out_svg):
        render_svg(ref, out_svg)

    png_key = hash_key(f"{cache_key_prefix}_png:{PREVIEW_CACHE_VERSION}:{ref}:{source_mtime}:{png_w}x{png_h}")
    out_png = os.path.join(cache_dir(), kind_dir, safe_name(ref) + "_" + png_key + ".png")
    if not _file_ok(out_png):
        svg_to_png(out_svg, out_png, png_w, png_h)
    return CachedRaster(png_path=out_png)

