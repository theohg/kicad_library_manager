from ..common import assembly, calculator, copper, courtyard, silkscreen


def build(pattern, element):
    housing = element['housing']
    housing['polarized'] = True
    settings = pattern.settings
    if not getattr(pattern, 'name', None):
        # SOT143 naming like SOT23 style
        pitch_h = int(round(housing['pitch'] * 100))
        ls = int(round(housing['leadSpan']['nom'] * 100))
        bw = int(round(housing['bodyWidth']['nom'] * 100))
        bh = int(round(housing['height']['max'] * 100))
        ll = housing.get('leadLength', {}).get('nom', housing.get('leadLength', {}).get('max', housing.get('leadLength', {}).get('min', 0)))
        lw = housing.get('leadWidth', {}).get('nom', housing.get('leadWidth', {}).get('max', housing.get('leadWidth', {}).get('min', 0)))
        pattern.name = f"SOT143{int(round(housing['leadCount']))}P{pitch_h}_{ls:03d}X{bw:03d}X{bh:03d}{int(round(ll*100)):03d}X{int(round(lw*100)):03d}{settings['densityLevel']}"

    pad_params = calculator.sot(pattern.__dict__, housing)

    pad1 = {
        'type': 'smd',
        'shape': 'rectangle',
        'width': pad_params['width1'],
        'height': pad_params['height1'],
        'layer': ['topCopper', 'topMask', 'topPaste'],
    }
    pad2 = {
        'type': 'smd',
        'shape': 'rectangle',
        'width': pad_params['width2'],
        'height': pad_params['height2'],
        'layer': ['topCopper', 'topMask', 'topPaste'],
    }

    if housing.get('reversed'):
        pad1['x'] = -pad_params['distance'] / 2
        pad1['y'] = -housing['pitch'] / 2
        pattern.pad(1, pad1)

        pad2['x'] = -pad_params['distance'] / 2
        pad2['y'] = housing['pitch'] / 2 + pad_params['height1'] / 2 - pad_params['height2'] / 2
        pattern.pad(2, pad2)
    else:
        pad2['x'] = -pad_params['distance'] / 2
        pad2['y'] = -housing['pitch'] / 2 - pad_params['height1'] / 2 + pad_params['height2'] / 2
        pattern.pad(1, pad2)

        pad1['x'] = -pad_params['distance'] / 2
        pad1['y'] = housing['pitch'] / 2
        pattern.pad(2, pad1)

    pad1r = dict(pad1)
    pad1r['x'] = pad_params['distance'] / 2
    pad1r['y'] = housing['pitch'] / 2
    pattern.pad(3, pad1r)
    pad1r2 = dict(pad1)
    pad1r2['x'] = pad_params['distance'] / 2
    pad1r2['y'] = -housing['pitch'] / 2
    pattern.pad(4, pad1r2)

    copper.mask(pattern)
    silkscreen.dual(pattern, housing)
    assembly.polarized(pattern, housing)
    courtyard.dual(pattern, housing, pad_params['courtyard'])

