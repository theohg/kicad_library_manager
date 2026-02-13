from ..common import assembly, calculator, copper, courtyard, silkscreen


def build(pattern, element):
    housing = element['housing']
    housing['polarized'] = True
    settings = pattern.settings
    if not getattr(pattern, 'name', None):
        pitch_h = int(round(housing['pitch'] * 100))
        ls = int(round(housing['leadSpan']['nom'] * 100))
        bw = int(round(housing['bodyWidth']['nom'] * 100))
        bh = int(round(housing['height']['max'] * 100))
        ll = housing.get('leadLength', {}).get('nom', housing.get('leadLength', {}).get('max', housing.get('leadLength', {}).get('min', 0)))
        lw = housing.get('leadWidth', {}).get('nom', housing.get('leadWidth', {}).get('max', housing.get('leadWidth', {}).get('min', 0)))
        pattern.name = f"SOT223{int(round(housing['leadCount']))}P{pitch_h}_{ls:03d}X{bw:03d}X{bh:03d}{int(round(ll*100)):03d}X{int(round(lw*100)):03d}{settings['densityLevel']}"

    pad_params = calculator.sot(pattern.__dict__, housing)

    pad = {
        'type': 'smd',
        'shape': 'rectangle',
        'width': pad_params['width1'],
        'height': pad_params['height1'],
        'layer': ['topCopper', 'topMask', 'topPaste'],
    }

    left_count = housing['leadCount'] - 1
    pad_left = dict(pad)
    pad_left['x'] = -pad_params['distance'] / 2
    y = -housing['pitch'] * (left_count / 2 - 0.5)
    for i in range(1, left_count + 1):
        pad_left['y'] = y
        pattern.pad(i, pad_left)
        y += housing['pitch']

    pad_right = dict(pad)
    pad_right['x'] = pad_params['distance'] / 2
    pad_right['y'] = 0
    pad_right['width'] = pad_params['width2']
    pad_right['height'] = pad_params['height2']
    pattern.pad(left_count + 1, pad_right)

    copper.mask(pattern)
    silkscreen.dual(pattern, housing)
    assembly.polarized(pattern, housing)
    courtyard.dual(pattern, housing, pad_params['courtyard'])

