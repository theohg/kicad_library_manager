def preamble(pattern, element):
    housing = element['housing']
    body_position = housing.get('bodyPosition', '0, 0')
    x, y = [float(v) for v in body_position.replace(' ', '').split(',')]
    pattern.center(-x, -y)


def postscriptum(pattern):
    pattern.center(0, 0)
    mask(pattern)


def mask(pattern):
    settings = pattern.settings
    mask_width = settings['minimum'].get('maskWidth')
    if mask_width is None:
        return
    pads = list(pattern.pads.values())
    last = len(pads) - 1
    if last <= 0:
        if pads:
            pads[0].mask = settings['minimum']['maskWidth']
        return
    for i in range(0, last + 1):
        for j in range(i + 1, last + 1):
            p1 = pads[i]
            p2 = pads[j]
            mask_val = settings['clearance']['padToMask']
            if p1.type != 'mounting-hole' and p2.type != 'mounting-hole':
                hspace = abs(p2.x - p1.x) - (p1.width + p2.width) / 2
                vspace = abs(p2.y - p1.y) - (p1.height + p2.height) / 2
                space = max(hspace, vspace)
                if (space - 2 * mask_val) < settings['minimum']['maskWidth']:
                    mask_val = (space - settings['minimum']['maskWidth']) / 2
                    if mask_val < 0:
                        mask_val = 0
            if getattr(p1, 'mask', None) is None or mask_val < p1.mask:
                p1.mask = mask_val
            if getattr(p2, 'mask', None) is None or mask_val < p2.mask:
                p2.mask = mask_val


def dual(pattern, element, pad_params):
    housing = element['housing']
    pitch = housing['pitch']
    count = housing['leadCount']
    distance = pad_params['distance']
    pad = pad_params['pad']
    order = pad_params.get('order', 'round')
    mirror = pad_params.get('mirror', False)
    pins = element['pins']

    if order == 'round':
        numbers = list(range(1, count // 2 + 1)) + list(range(count, count // 2, -1))
    elif order == 'rows':
        numbers = list(range(1, count + 1, 2)) + list(range(2, count + 1, 2))
    elif order == 'custom':
        numbers = pad_params.get('custom_numbers', list(range(1, count + 1)))
    else:
        numbers = list(range(1, count + 1))

    preamble(pattern, element)

    pad_x_left = (distance / 2) if mirror else (-distance / 2)
    y = -pitch * (count / 4 - 0.5)
    for i in range(0, count // 2):
        pad_copy = dict(pad)
        pad_copy['x'] = pad_x_left
        pad_copy['y'] = y
        pad_copy['height'] = pad_params.get('height1', pad_params['height']) if numbers[i] == 1 else pad_params['height']
        n = numbers[i]
        if str(n) in pins:
            pattern.pad(n, pad_copy)
        y += pitch

    pad_x_right = (-distance / 2) if mirror else (distance / 2)
    y = -pitch * (count / 4 - 0.5)
    for i in range(count // 2, count):
        pad_copy = dict(pad)
        pad_copy['x'] = pad_x_right
        pad_copy['y'] = y
        pad_copy['height'] = pad_params.get('height1', pad_params['height']) if numbers[i] == 1 else pad_params['height']
        n = numbers[i]
        if str(n) in pins:
            pattern.pad(n, pad_copy)
        y += pitch

    postscriptum(pattern)


def grid_array(pattern, element, pad):
    housing = element['housing']
    v_pitch = housing['verticalPitch']
    h_pitch = housing['horizontalPitch']
    row_count = housing['rowCount']
    col_count = housing['columnCount']
    grid_letters = element['gridLetters']
    pins = element['pins']

    preamble(pattern, element)
    y = -v_pitch * (row_count / 2 - 0.5)
    for row in range(1, row_count + 1):
        x = -h_pitch * (col_count / 2 - 0.5)
        for col in range(1, col_count + 1):
            pad_copy = dict(pad)
            pad_copy['x'] = x
            pad_copy['y'] = y
            name = f"{grid_letters[row]}{col}"
            if name in pins:
                pattern.pad(name, pad_copy)
            x += h_pitch
        y += v_pitch
    postscriptum(pattern)


def quad(pattern, element, pad_params):
    housing = element['housing']
    pitch = housing['pitch']
    row_count = housing['rowCount']
    column_count = housing['columnCount']
    row_pad = dict(pad_params['rowPad'])
    column_pad = dict(pad_params['columnPad'])
    distance1 = pad_params['distance1']
    distance2 = pad_params['distance2']
    pins = element['pins']

    preamble(pattern, element)

    # left side
    row_pad['x'] = -distance1 / 2
    y = -pitch * (row_count / 2 - 0.5)
    num = 1
    for _ in range(1, row_count + 1):
        row_pad['y'] = y
        if str(num) in pins:
            pattern.pad(num, row_pad)
        num += 1
        y += pitch

    # bottom side
    x = -pitch * (column_count / 2 - 0.5)
    column_pad['y'] = distance2 / 2
    for _ in range(1, column_count + 1):
        column_pad['x'] = x
        if str(num) in pins:
            pattern.pad(num, column_pad)
        num += 1
        x += pitch

    # right side
    row_pad['x'] = distance1 / 2
    y -= pitch
    for _ in range(1, row_count + 1):
        row_pad['y'] = y
        if str(num) in pins:
            pattern.pad(num, row_pad)
        num += 1
        y -= pitch

    # top side
    x -= pitch
    column_pad['y'] = -distance2 / 2
    for _ in range(1, column_count + 1):
        column_pad['x'] = x
        if str(num) in pins:
            pattern.pad(num, column_pad)
        num += 1
        x -= pitch

    postscriptum(pattern)


def tab(pattern, element):
    housing = element['housing']
    has_tab = ('tabWidth' in housing) and ('tabLength' in housing)
    base_count = housing.get('leadCount')
    if base_count is None:
        rc = int(housing.get('rowCount', 0) or 0)
        cc = int(housing.get('columnCount', 0) or 0)
        base_count = 2 * (rc + cc)
        if base_count == 0:
            base_count = len(element['pins'])
    tab_number = int(base_count) + 1
    if has_tab:
        housing.setdefault('tabPosition', '0, 0')
        points = pattern.parse_position(housing['tabPosition'])
        # Resolve tab size; treat zero-sized as absent
        tw = housing.get('tabWidth')
        tl = housing.get('tabLength')
        if isinstance(tw, dict):
            tab_w = tw.get('nom', tw.get('min', tw.get('max', 0)))
        else:
            tab_w = float(tw or 0)
        if isinstance(tl, dict):
            tab_l = tl.get('nom', tl.get('min', tl.get('max', 0)))
        else:
            tab_l = float(tl or 0)
        if tab_w <= 0 or tab_l <= 0:
            return
        for i, p in enumerate(points):
            tab_pad = {
                'type': 'smd',
                'shape': 'rectangle',
                'width': tab_w,
                'height': tab_l,
                'layer': ['topCopper', 'topMask', 'topPaste'],
                'x': p['x'],
                'y': p['y'],
            }
            pattern.pad(tab_number + i, tab_pad)
        mask(pattern)
    if 'viaDiameter' in housing:
        via_diameter = housing['viaDiameter']
        points = pattern.parse_position(housing['viaPosition'])
        for p in points:
            via_pad = {
                'type': 'through-hole',
                'shape': 'circle',
                'hole': via_diameter,
                'width': via_diameter + 0.1,
                'height': via_diameter + 0.1,
                'layer': ['topCopper', 'intCopper', 'bottomCopper'],
                'x': p['x'],
                'y': p['y'],
            }
            pattern.pad(tab_number, via_pad)

