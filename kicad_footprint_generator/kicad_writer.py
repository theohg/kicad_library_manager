from dataclasses import dataclass
from typing import List, Optional


@dataclass
class PatternShape:
    kind: str
    # Generic attributes used by writer, mirror of QedaPattern shapes
    x: float = 0.0
    y: float = 0.0
    x1: float = 0.0
    y1: float = 0.0
    x2: float = 0.0
    y2: float = 0.0
    radius: float = 0.0
    width: float = 0.0
    height: float = 0.0
    lineWidth: float = 0.0
    fill: bool = False
    layer: Optional[List[str]] = None
    # text/attributes
    name: Optional[str] = None
    text: Optional[str] = None
    fontSize: Optional[float] = None
    angle: Optional[float] = None
    visible: Optional[bool] = None
    # pad
    shape: Optional[str] = None
    type: Optional[str] = None
    hole: Optional[float] = None
    slotWidth: Optional[float] = None
    slotHeight: Optional[float] = None
    mask: Optional[float] = None
    paste: Optional[float] = None
    clearance: Optional[float] = None
    dieLength: Optional[float] = None
    chamfer: Optional[List[str]] = None
    property: Optional[str] = None
    # pad identity
    pad_name: Optional[str] = None


def _fmt(x: float, decimals: int) -> str:
    return f"{x:.{decimals}f}"


def _map_layers(layers: List[str]) -> str:
    table = {
        'topCopper': 'F.Cu',
        'topMask': 'F.Mask',
        'topPaste': 'F.Paste',
        'topSilkscreen': 'F.SilkS',
        'topAssembly': 'F.Fab',
        'topCourtyard': 'F.CrtYd',
        'intCopper': '*.Cu',
        'bottomCopper': 'B.Cu',
        'bottomMask': 'B.Mask',
        'bottomPaste': 'B.Paste',
        'bottomSilkscreen': 'B.SilkS',
        'bottomAssembly': 'B.Fab',
        'bottomCourtyard': 'B.CrtYd',
    }
    return " ".join(table[l] for l in layers)


def write_kicad_mod(module_name: str, shapes: List[PatternShape], pattern_type: str, decimals: int, model: Optional[dict] = None, descr: Optional[str] = None, tags: Optional[str] = None) -> str:
    lines: List[str] = []
    lines.append(f"(module {module_name} (layer F.Cu)")
    if descr:
        lines.append(f'  (descr "{descr}")')
    if tags:
        lines.append(f'  (tags "{tags}")')
    attrs = []
    if pattern_type == 'smd':
        attrs.append('smd')
    if attrs:
        lines.append(f"  (attr {' '.join(attrs)})")

    for s in shapes:
        if s.kind == 'attribute':
            # Map names like Coffee's _patternObj
            name_field = s.name
            text = s.text
            if name_field == 'refDes':
                name_field = 'reference'
                text = text or 'REF**'
            elif name_field == 'value':
                name_field = 'value'
            else:
                name_field = 'user'
            angle = f" {int(s.angle)}" if s.angle is not None else ""
            # Hide value field by default, or if explicitly set to hidden
            hide = " hide" if (name_field == 'value' or s.visible is False) else ""
            lines.append(
                f"  (fp_text {name_field} {text} (at {_fmt(s.x, decimals)} {_fmt(s.y, decimals)}{angle}){hide} (layer {_map_layers(s.layer)})"
            )
            lines.append(
                f"    (effects (font (size {_fmt(s.fontSize or 1.0, decimals)} {_fmt(s.fontSize or 1.0, decimals)}) (thickness {_fmt(s.lineWidth or 0.12, decimals)})))"
            )
            lines.append("  )")
        elif s.kind == 'circle':
            lines.append(
                f"  (fp_circle (center {_fmt(s.x, decimals)} {_fmt(s.y, decimals)}) (end {_fmt(s.x, decimals)} {_fmt(s.y + s.radius, decimals)}) (layer {_map_layers(s.layer)}) (width {_fmt(s.lineWidth, decimals)})"
            )
            if s.fill:
                lines[-1] += " (fill solid)"
            lines[-1] += ")"
        elif s.kind == 'line':
            lines.append(
                f"  (fp_line (start {_fmt(s.x1, decimals)} {_fmt(s.y1, decimals)}) (end {_fmt(s.x2, decimals)} {_fmt(s.y2, decimals)}) (layer {_map_layers(s.layer)}) (width {_fmt(s.lineWidth, decimals)}))"
            )
        elif s.kind == 'rectangle':
            lines.append(
                f"  (fp_rect (start {_fmt(s.x1, decimals)} {_fmt(s.y1, decimals)}) (end {_fmt(s.x2, decimals)} {_fmt(s.y2, decimals)}) (layer {_map_layers(s.layer)}) (width {_fmt(s.lineWidth, decimals)})"
            )
            if s.fill:
                lines[-1] += " (fill solid)"
            lines[-1] += ")"
        elif s.kind == 'pad':
            shape = s.shape or 'rect'
            if shape == 'rectangle':
                shape = 'rect'
            
            # Convert rectangular pads to round rectangles
            if shape == 'rect':
                shape = 'roundrect'
            
            pad_type = s.type
            if pad_type == 'through-hole':
                pad_type = 'thru_hole'
            elif pad_type == 'mounting-hole':
                pad_type = 'np_thru_hole'
            
            # KiCad 7 smooth corners and extras
            line = (
                f"  (pad {s.pad_name} {pad_type} {shape} (at {_fmt(s.x, decimals)} {_fmt(s.y, decimals)}) (size {_fmt(s.width, decimals)} {_fmt(s.height, decimals)}) (layers {_map_layers(s.layer)})"
            )
            
            # Add roundrect_rratio for roundrect pads
            if shape == 'roundrect':
                pad_w = s.width
                pad_h = s.height
                min_dimension = min(pad_w, pad_h)
                rratio = min(0.25, 0.1 / min_dimension)
                line += f"\n    (roundrect_rratio {_fmt(rratio, 10)})"
            
            if s.slotWidth is not None and s.slotHeight is not None:
                line += f"\n    (drill oval {_fmt(s.slotWidth, decimals)} {_fmt(s.slotHeight, decimals)})"
            elif s.hole is not None:
                line += f"\n    (drill {_fmt(s.hole, decimals)})"
            if s.mask is not None:
                line += f"\n    (solder_mask_margin {_fmt(s.mask, decimals)})"
            if s.paste is not None:
                line += f"\n    (solder_paste_margin {_fmt(s.paste, decimals)})"
            if s.clearance is not None:
                line += f"\n    (clearance {_fmt(s.clearance, decimals)})"
            if s.dieLength is not None:
                line += f"\n    (die_length {_fmt(s.dieLength, decimals)})"
            if s.property == 'testpoint':
                line += "\n    (property pad_prop_testpoint)"
            line += ")"
            lines.append(line)

    # Optional model block (STEP/VRML path provided by caller)
    if model:
        path = model.get('path')
        if path:
            lines.append(f"  (model {path}")
            at = model.get('at', (0, 0, 0))
            scale = model.get('scale', (1, 1, 1))
            rot = model.get('rotate', (0, 0, 0))
            lines.append(f"    (at (xyz {at[0]} {at[1]} {at[2]}))")
            lines.append(f"    (scale (xyz {scale[0]} {scale[1]} {scale[2]}))")
            lines.append(f"    (rotate (xyz {rot[0]} {rot[1]} {rot[2]}))")
            lines.append("  )")

    lines.append(")")
    return "\n".join(lines) + "\n"

