from ..common import assembly, calculator, copper, courtyard
from ..common import silkscreen


def build(pattern, element):
    housing = element['housing']
    housing['polarized'] = True
    housing['flatlead'] = True
    housing.setdefault('leadCount', 5)
    settings = pattern.settings
    if not getattr(pattern, 'name', None):
        pattern.name = (
            f"SOTFL{int(round(housing['pitch']*100))}P{int(round(housing['leadSpan']['nom']*100))}X{int(round(housing['height']['max']*100))}-{int(round(housing['leadCount']))}{settings['densityLevel']}"
        )

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
        'x': 0,
        'y': 0,
        'width': pad_params['width2'] + pad_params['distance'],
        'height': pad_params['height2'],
        'layer': ['topCopper', 'topMask', 'topPaste'],
    }

    p1 = dict(pad1)
    p1['x'] = -pad_params['distance'] / 2
    p1['y'] = -housing['pitch']
    pattern.pad(1, p1)

    pattern.pad(2, pad2)

    p3 = dict(pad1)
    p3['x'] = -pad_params['distance'] / 2
    p3['y'] = housing['pitch']
    pattern.pad(3, p3)

    p4 = dict(pad1)
    p4['x'] = pad_params['distance'] / 2
    p4['y'] = housing['pitch']
    pattern.pad(4, p4)

    p5 = dict(pad1)
    p5['x'] = pad_params['distance'] / 2
    p5['y'] = -housing['pitch']
    pattern.pad(5, p5)

    copper.mask(pattern)
    silkscreen.dual(pattern, housing)
    assembly.polarized(pattern, housing)
    courtyard.dual(pattern, housing, pad_params['courtyard'])

