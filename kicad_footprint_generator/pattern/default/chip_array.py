from ..common import assembly, calculator, copper, courtyard, silkscreen


def build(pattern, element):
    settings = pattern.settings
    housing = element['housing']
    housing.setdefault('leadSpan', housing['bodyWidth'])

    # Naming per table for arrays (CAV/CAF variants)
    if not getattr(pattern, 'name', None):
        comp_type = element['housing'].get('componentType', 'CAPCAV')
        pins = int(round(housing['leadCount']))
        pitch_h = int(round(housing['pitch'] * 100))
        bl = int(round(housing['bodyLength']['nom'] * 100))
        bw = int(round(housing['bodyWidth']['nom'] * 100))
        bh = int(round(housing['height']['max'] * 100))
        ll = housing.get('leadLength', {}).get('nom', housing.get('leadLength', {}).get('max', housing.get('leadLength', {}).get('min', 0)))
        lw = housing.get('leadWidth', {}).get('nom', housing.get('leadWidth', {}).get('max', housing.get('leadWidth', {}).get('min', 0)))
        pattern.name = f"{comp_type}{pins}P{pitch_h}_{bl:03d}X{bw:03d}X{bh:03d}{int(round(ll*100)):03d}X{int(round(lw*100)):03d}{settings['densityLevel']}"

    pad_params = calculator.chip_array(pattern.__dict__, housing)
    pad_params['order'] = 'round'
    pad_params['pad'] = {
        'type': 'smd',
        'shape': 'rectangle',
        'width': pad_params['width'],
        'height': pad_params['height'],
        'layer': ['topCopper', 'topMask', 'topPaste'],
    }

    copper.dual(pattern, element, pad_params)
    silkscreen.dual(pattern, housing)
    assembly.body(pattern, housing)
    courtyard.boundary(pattern, housing, pad_params['courtyard'])

