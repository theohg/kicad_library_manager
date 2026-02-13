from __future__ import annotations

import wx


def make_status_bitmap(color: wx.Colour) -> wx.Bitmap:
    """
    Match legacy icon rendering from ui.py (transparent background).
    """
    bmp = wx.Bitmap(12, 12)
    dc = wx.MemoryDC(bmp)
    dc.SetBackground(wx.Brush(wx.Colour(0, 0, 0, 0)))
    dc.Clear()
    dc.SetBrush(wx.Brush(color))
    dc.SetPen(wx.Pen(color))
    dc.DrawCircle(6, 6, 5)
    dc.SelectObject(wx.NullBitmap)
    return bmp
