from __future__ import annotations

import wx


def make_status_bitmap(color: wx.Colour) -> wx.Bitmap:
    """
    Render a small colored circle with a transparent background.

    Uses wx.Image with an explicit alpha channel so the background is
    truly transparent on all platforms (wx.MemoryDC + Clear does not
    produce a real alpha channel on Windows).  Anti-aliased via
    distance-based alpha blending at the circle edge.
    """
    import math

    size = 12
    cx = cy = (size - 1) / 2.0  # 5.5 for center of 12px
    radius = 4.8
    img = wx.Image(size, size)
    img.InitAlpha()
    cr, cg, cb = color.Red(), color.Green(), color.Blue()
    for y in range(size):
        for x in range(size):
            dist = math.sqrt((x - cx) ** 2 + (y - cy) ** 2)
            # 1.0 inside, 0.0 outside, smooth blend over ~1px at the edge
            coverage = max(0.0, min(1.0, radius + 0.5 - dist))
            if coverage > 0:
                img.SetRGB(x, y, cr, cg, cb)
                img.SetAlpha(x, y, int(coverage * 255 + 0.5))
            else:
                img.SetRGB(x, y, 0, 0, 0)
                img.SetAlpha(x, y, 0)
    return wx.Bitmap(img)
