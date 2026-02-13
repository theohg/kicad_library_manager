from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from ..kicad_writer import PatternShape


@dataclass
class QedaPattern:
    settings: dict
    decimals: int
    name: str
    type: str = 'smd'
    shapes: List[PatternShape] = field(default_factory=list)
    pads: Dict[str, PatternShape] = field(default_factory=dict)
    current_layer: List[str] = field(default_factory=lambda: ['topCopper'])
    current_line_width: float = 0.0
    current_fill: bool = False
    cx: float = 0.0
    cy: float = 0.0

    def attribute(self, name: str, attr: dict) -> 'QedaPattern':
        self.shapes.append(
            PatternShape(
                kind='attribute',
                name=name,
                x=self.cx + attr.get('x', 0.0),
                y=self.cy + attr.get('y', 0.0),
                text=attr.get('text'),
                fontSize=attr.get('fontSize', self.settings['fontSize']['default']),
                angle=attr.get('angle'),
                visible=attr.get('visible', True),
                lineWidth=self.current_line_width,
                layer=self.current_layer,
            )
        )
        return self

    def center(self, x: float, y: float) -> 'QedaPattern':
        self.cx = x
        self.cy = y
        return self

    def circle(self, x: float, y: float, radius: float) -> 'QedaPattern':
        self.shapes.append(
            PatternShape(kind='circle', x=self.cx + x, y=self.cy + y, radius=radius, lineWidth=self.current_line_width, layer=self.current_layer, fill=self.current_fill)
        )
        return self

    def fill(self, enable: bool) -> 'QedaPattern':
        self.current_fill = enable
        return self

    def layer(self, layer: List[str] | str) -> 'QedaPattern':
        if not isinstance(layer, list):
            layer = [layer]
        self.current_layer = layer
        return self

    def line(self, x1: float, y1: float, x2: float, y2: float) -> 'QedaPattern':
        if (x1 != x2) or (y1 != y2):
            self.shapes.append(
                PatternShape(kind='line', x1=self.cx + x1, y1=self.cy + y1, x2=self.cx + x2, y2=self.cy + y2, lineWidth=self.current_line_width, layer=self.current_layer)
            )
        return self

    def lineWidth(self, line_width: float) -> 'QedaPattern':
        self.current_line_width = line_width
        return self

    def moveTo(self, x: float, y: float) -> 'QedaPattern':
        self.x = x
        self.y = y
        return self

    def lineTo(self, x: float, y: float) -> 'QedaPattern':
        self.line(self.x, self.y, x, y)
        return self.moveTo(x, y)

    def pad(self, name: str | int, pad: dict) -> 'QedaPattern':
        n = str(name)
        shape = PatternShape(
            kind='pad',
            pad_name=n,
            x=self.cx + pad.get('x', 0.0),
            y=self.cy + pad.get('y', 0.0),
            width=pad['width'],
            height=pad['height'],
            type=pad['type'],
            shape=pad.get('shape', 'rect'),
            hole=pad.get('hole'),
            slotWidth=pad.get('slotWidth'),
            slotHeight=pad.get('slotHeight'),
            mask=pad.get('mask'),
            paste=pad.get('paste'),
            clearance=pad.get('clearance'),
            dieLength=pad.get('dieLength'),
            chamfer=pad.get('chamfer'),
            property=pad.get('property'),
            layer=pad.get('layer', self.current_layer),
        )
        self.pads[n] = shape
        self.shapes.append(shape)
        if shape.type not in ('smd', 'mounting-hole'):
            self.type = 'through-hole'
        return self

    def rectangle(self, x1: float, y1: float, x2: float, y2: float) -> 'QedaPattern':
        if (x1 != x2) or (y1 != y2):
            self.shapes.append(
                PatternShape(kind='rectangle', x1=self.cx + x1, y1=self.cy + y1, x2=self.cx + x2, y2=self.cy + y2, lineWidth=self.current_line_width, layer=self.current_layer, fill=self.current_fill)
            )
        return self

    def extreme_pads(self) -> Tuple[PatternShape, PatternShape]:
        if not self.pads:
            return None, None
        # sort by numeric if possible
        def keyfn(k: str) -> Tuple[int, str]:
            try:
                return (0, int(k))
            except Exception:
                return (1, k)

        keys = sorted(self.pads.keys(), key=keyfn)
        return self.pads[keys[0]], self.pads[keys[-1]]

    def parse_position(self, value: str):
        values = [float(v) for v in value.replace(' ', '').split(',') if v]
        points = []
        for i in range(0, len(values), 2):
            x = values[i]
            y = values[i + 1] if i + 1 < len(values) else 0.0
            points.append({'x': x, 'y': y})
        return points

