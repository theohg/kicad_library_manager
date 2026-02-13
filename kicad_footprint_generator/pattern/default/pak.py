from ..common import assembly, calculator, copper, courtyard, silkscreen


def build(pattern, element):
    housing = element['housing']
    settings = pattern.settings
    # Normalize fields that may be provided as scalars or missing 'nom'
    def ensure_range(key: str, prefer: str = 'max'):
        val = housing.get(key)
        if val is None:
            return
        if isinstance(val, dict):
            if 'nom' not in val:
                if prefer in val:
                    val['nom'] = val[prefer]
                elif 'min' in val:
                    val['nom'] = val['min']
        else:
            housing[key] = {'min': val, 'nom': val, 'max': val}
    for k in ('bodyWidth', 'bodyLength', 'tabWidth', 'tabLength', 'tabLedge'):
        ensure_range(k, prefer='max' if k in ('bodyWidth', 'bodyLength') else 'min')
    if not getattr(pattern, 'name', None):
        bl = housing.get('bodyLength', {})
        bw = housing.get('bodyWidth', {})
        blv = bl.get('nom', bl.get('max', 0)) if isinstance(bl, dict) else bl
        bwv = bw.get('nom', bw.get('max', 0)) if isinstance(bw, dict) else bw
        pattern.name = (
            f"TO{int(round(housing['pitch']*100))}P{int(round(blv*100))}X{int(round(bwv*100))}X{int(round(housing['height']['max']*100))}-{int(round(housing['leadCount']))}{settings['densityLevel']}"
        )

    pad_params = calculator.pak(pattern.__dict__, housing)

    pad = {
        'type': 'smd',
        'shape': 'rectangle',
        'width': pad_params['width1'],
        'height': pad_params['height1'],
        'layer': ['topCopper', 'topMask', 'topPaste'],
    }
    pitch = housing['pitch']
    lead_count = housing['leadCount']

    pins = element['pins']
    pad_left = dict(pad)
    pad_left['x'] = -pad_params['distance1'] / 2
    y = -pitch * (lead_count / 2 - 0.5)
    for i in range(1, lead_count + 1):
        pad_left['y'] = y
        if str(i) in pins:
            pattern.pad(i, pad_left)
        y += pitch

    pad_tab = dict(pad)
    pad_tab['width'] = pad_params['width2']
    pad_tab['height'] = pad_params['height2']
    pad_tab['x'] = pad_params['distance2'] / 2
    pad_tab['y'] = 0
    pattern.pad(lead_count + 1, pad_tab)

    copper.mask(pattern)
    silkscreen.pak(pattern, housing)
    assembly.pak(pattern, element)
    courtyard.pak(pattern, housing, pad_params['courtyard'])

