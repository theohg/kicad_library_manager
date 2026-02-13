from ..common import assembly, calculator, copper, courtyard, silkscreen


_pin_number = 0
_mounting_hole = 1
_nc_pad = 1


def _parse_numbers(element, housing, suffix):
    key = f"numbers{suffix}"
    if key in housing and housing[key]:
        # Format in Coffee accepts strings like "1-4,6,8"; our GUI/CLI can pass list already
        if isinstance(housing[key], str):
            parts = housing[key].replace(' ', '').split(',')
            out = []
            for p in parts:
                if '-' in p:
                    a, b = p.split('-')
                    out.extend([str(i) for i in range(int(a), int(b) + 1)])
                else:
                    out.append(p)
            housing[key] = out
        return housing[key]
    return list(element['pins'].keys())


def _copper_pads(pattern, element, suffix=''):
    global _pin_number, _mounting_hole, _nc_pad
    housing = element['housing']
    pins = element['pins']
    pin_number_group = 0
    numbers = _parse_numbers(element, housing, suffix)
    has_pads = False
    # choose which pad definition path
    slot_w = housing.get(f'slotWidth{suffix}')
    slot_h = housing.get(f'slotHeight{suffix}')
    hole_d = housing.get(f'holeDiameter{suffix}')
    pad_d = housing.get(f'padDiameter{suffix}')
    pad_w = housing.get(f'padWidth{suffix}')
    pad_h = housing.get(f'padHeight{suffix}')

    pad = None
    if slot_w is not None and slot_h is not None:
        hole_diam = max(slot_w, slot_h)
        if slot_w > slot_h:
            pad_height = pad_h if pad_h is not None else calculator.pad_diameter(pattern.__dict__, housing, slot_h)
            pad_width = pad_w if pad_w is not None else slot_w + (pad_height - slot_h)
            pad_diam = pad_d if pad_d is not None else hole_diam + (pad_height - slot_h)
        else:
            pad_width = pad_w if pad_w is not None else calculator.pad_diameter(pattern.__dict__, housing, slot_w)
            pad_height = pad_h if pad_h is not None else slot_h + (pad_width - slot_w)
            pad_diam = pad_d if pad_d is not None else hole_diam + (pad_width - slot_w)
        pad = {
            'type': 'through-hole',
            'slotWidth': slot_w,
            'slotHeight': slot_h,
            'width': pad_width,
            'height': pad_height,
            'shape': housing.get(f'padShape{suffix}') or ('rectangle' if (_pin_number == 0 and housing.get('polarized')) else 'circle'),
            'layer': ['topCopper', 'topMask', 'intCopper', 'bottomCopper', 'bottomMask'],
        }
        if housing.get(f'pinInPaste{suffix}'):
            if housing.get(f'padBottom{suffix}'):
                pad['layer'].append('bottomPaste')
            else:
                pad['layer'].append('topPaste')
        if (pad_width < slot_w) and (pad_height < slot_h):
            pad['type'] = 'mounting-hole'
            pad['layer'] = ['topMask', 'bottomMask']
            pad['width'] = slot_w
            pad['height'] = slot_h
            pad['shape'] = housing.get(f'padShape{suffix}') or 'circle'
    elif hole_d is not None:
        pad_diam = pad_d if pad_d is not None else calculator.pad_diameter(pattern.__dict__, housing, hole_d)
        pad_width = pad_w if pad_w is not None else pad_diam
        pad_height = pad_h if pad_h is not None else pad_diam
        pad = {
            'type': 'through-hole',
            'hole': hole_d,
            'width': pad_width,
            'height': pad_height,
            'shape': housing.get(f'padShape{suffix}') or ('rectangle' if (_pin_number == 0 and housing.get('polarized')) else 'circle'),
            'layer': ['topCopper', 'topMask', 'intCopper', 'bottomCopper', 'bottomMask'],
        }
        if housing.get(f'pinInPaste{suffix}'):
            if housing.get(f'padBottom{suffix}'):
                pad['layer'].append('bottomPaste')
            else:
                pad['layer'].append('topPaste')
        if (pad_width < hole_d) or (pad_height < hole_d):
            pad['type'] = 'mounting-hole'
            pad['layer'] = ['topMask', 'bottomMask']
            pad['width'] = hole_d
            pad['height'] = hole_d
            pad['shape'] = housing.get(f'padShape{suffix}') or 'circle'
    elif (pad_d is not None) or (pad_w is not None and pad_h is not None):
        pad_diam = pad_d
        pad_width = pad_w if pad_w is not None else pad_diam
        pad_height = pad_h if pad_h is not None else pad_diam
        nopaste = housing.get('nopaste') or housing.get(f'noPaste{suffix}')
        layers = ['bottomCopper', 'bottomMask'] if housing.get(f'padBottom{suffix}') else ['topCopper', 'topMask']
        if not nopaste:
            layers = layers + (['bottomPaste'] if housing.get(f'padBottom{suffix}') else ['topPaste'])
        pad = {
            'type': 'smd',
            'width': pad_width,
            'height': pad_height,
            'shape': 'circle' if pad_diam is not None else 'rectangle',
            'layer': layers,
        }
    else:
        return False

    if f'padPosition{suffix}' in housing and housing[f'padPosition{suffix}']:
        has_pads = True
        points = pattern.parse_position(housing[f'padPosition{suffix}'])
        for idx, p in enumerate(points):
            pad['x'] = p['x']
            pad['y'] = p['y']
            if pad['type'] == 'mounting-hole':
                number = f"MH{_mounting_hole}"
                _mounting_hole += 1
            else:
                if f'numbers{suffix}' in housing:
                    number = numbers[pin_number_group]
                    pin_number_group += 1
                else:
                    number = numbers[_pin_number + pin_number_group] if (_pin_number + pin_number_group) < len(numbers) else f"NC{_nc_pad}"
                    if number.startswith('NC'):
                        _nc_pad += 1
                    pin_number_group += 1
            pattern.pad(number, pad)
            if hole_d is not None:
                pad['shape'] = housing.get(f'padShape{suffix}') or 'circle'
    elif f'rowCount{suffix}' in housing and f'columnCount{suffix}' in housing:
        has_pads = True
        row_count = housing[f'rowCount{suffix}']
        v_pitch = 0 if row_count == 1 else housing.get(f'verticalPitch{suffix}', housing.get(f'pitch{suffix}'))
        row_dxs = pattern.settings.get('parseArray', lambda x: [0])(housing.get(f'rowDX{suffix}')) if False else [0]
        row_dys = pattern.settings.get('parseArray', lambda x: [0])(housing.get(f'rowDY{suffix}')) if False else [0]
        column_counts = [housing.get(f'columnCount{suffix}')] if isinstance(housing.get(f'columnCount{suffix}'), (int, float)) else housing.get(f'columnCount{suffix}', [])
        h_pitch = housing.get(f'horizontalPitch{suffix}', housing.get(f'pitch{suffix}'))
        column_dxs = [0]
        column_dys = [0]
        y = -v_pitch * (row_count - 1) / 2
        for row in range(0, row_count):
            column_count = column_counts[row] if row < len(column_counts) and column_counts[row] is not None else column_counts[0]
            row_dx = row_dxs[row] if row < len(row_dxs) and row_dxs[row] is not None else row_dxs[0]
            row_dy = row_dys[row] if row < len(row_dys) and row_dys[row] is not None else row_dys[0]
            x = -h_pitch * (column_count - 1) / 2
            for column in range(0, column_count):
                column_dx = column_dxs[column] if column < len(column_dxs) and column_dxs[column] is not None else column_dxs[0]
                column_dy = column_dys[column] if column < len(column_dys) and column_dys[column] is not None else column_dys[0]
                pad['x'] = x + row_dx + column_dx
                pad['y'] = y + row_dy + column_dy
                if pad['type'] == 'mounting-hole':
                    number = f"MH{_mounting_hole}"
                    _mounting_hole += 1
                else:
                    if f'numbers{suffix}' in housing:
                        number = numbers[pin_number_group]
                        pin_number_group += 1
                    else:
                        idx = _pin_number + pin_number_group
                        number = numbers[idx] if idx < len(numbers) else f"NC{_nc_pad}"
                        if number.startswith('NC'):
                            _nc_pad += 1
                        pin_number_group += 1
                pattern.pad(number, pad)
                if hole_d is not None:
                    pad['shape'] = housing.get(f'padShape{suffix}') or 'circle'
                x += h_pitch
            y += v_pitch

    _pin_number += pin_number_group
    return has_pads


def build(pattern, element):
    global _pin_number, _mounting_hole, _nc_pad
    housing = element['housing']
    pattern.name = getattr(pattern, 'name', None) or f"{element.get('group','custom')}_{element['name'].upper()}"
    housing.setdefault('bodyPosition', '0, 0')
    body_pos = pattern.parse_position(housing['bodyPosition'])[0]
    housing.setdefault('basePoint', '0, 0')
    base = pattern.parse_position(housing['basePoint'])[0]
    pattern.center(-body_pos['x'] + base['x'], -body_pos['y'] + base['y'])
    _pin_number = 0
    _mounting_hole = 1
    _nc_pad = 1
    _copper_pads(pattern, element)
    i = 1
    while True:
        if not _copper_pads(pattern, element, i):
            break
    pattern.center(0, 0)
    copper.mask(pattern)
    silkscreen.body(pattern, housing)
    if housing.get('polarized'):
        assembly.polarized(pattern, housing)
    else:
        assembly.body(pattern, housing)
    courtyard.boundary(pattern, housing)

