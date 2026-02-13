from ..common import assembly, calculator, copper, courtyard, silkscreen


def build(pattern, element):
    housing = element['housing']
    settings = pattern.settings
    housing['polarized'] = True
    housing.setdefault('leadWidth', housing.get('leadDiameter'))
    housing.setdefault('leadHeight', housing.get('leadDiameter'))

    lead_count = 0
    for i in range(0, housing['leadCount'] + 1):
        if str(i) in element['pins']:
            lead_count += 1

    if not getattr(pattern, 'name', None):
        c = 'C' if housing.get('ceramic') else ''
        s = 'S' if housing.get('socket') else ''
        pattern.name = (
            f"{c}DIP{s}{int(round(housing['leadSpan']['nom']*100))}W{int(round(housing['leadWidth']['nom']*100))}P{int(round(housing['pitch']*100))}L{int(round(housing['bodyLength']['nom']*100))}H{int(round(housing['height']['nom']*100))}Q{lead_count}"
        )

    # Round-off per IPC table
    pattern.sizeRoundoff = 0.05
    pad_params = calculator.through_hole(pattern.__dict__, housing)
    pad_params['distance'] = housing['leadSpan']['nom']
    pad_params['pitch'] = housing['pitch']
    pad_params['count'] = housing['leadCount']
    pad_params['order'] = 'round'
    pad_params['pad'] = {
        'type': 'through-hole',
        'shape': 'circle',
        'hole': pad_params['hole'],
        'width': pad_params['width'],
        'height': pad_params['height'],
        'layer': ['topCopper', 'topMask', 'intCopper', 'bottomCopper', 'bottomMask'],
    }
    copper.dual(pattern, element, pad_params)
    # first pad rectangular
    first_key = sorted(pattern.pads.keys(), key=lambda k: int(k) if k.isdigit() else k)[0]
    pattern.pads[first_key].shape = 'rect'

    # For DIP, body outline may be absent; approximate body dims for silkscreen/assembly
    if 'bodyWidth' not in housing:
        bw = housing['leadSpan']['nom'] - (housing.get('leadWidth', {}).get('nom', housing.get('leadDiameter', {}).get('max', 0)) * 2)
        housing['bodyWidth'] = {'nom': max(bw, 0)}
    if 'bodyLength' not in housing:
        housing['bodyLength'] = {'nom': housing.get('bodyLength', {}).get('nom', 0)}
    silkscreen.dual(pattern, housing)
    assembly.polarized(pattern, housing)
    cy = {'M': 1.5, 'N': 0.8, 'L': 0.2}[settings['densityLevel']]
    courtyard.dual(pattern, housing, cy)

