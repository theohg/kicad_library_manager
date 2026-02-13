from ..common import copper, courtyard


def build(pattern, element):
    housing = element['housing']
    settings = pattern.settings
    if not getattr(pattern, 'name', None):
        pattern.name = element['name'].upper()

    pad = {
        'x': 0,
        'y': 0,
        'hole': housing['holeDiameter'],
        'shape': 'circle' if ('padDiameter' in housing) else 'rectangle',
    }

    if ('padDiameter' in housing) or ('padWidth' in housing) or ('padHeight' in housing):
        housing.setdefault('padWidth', housing.get('padDiameter'))
        housing.setdefault('padHeight', housing.get('padDiameter'))
        pad['type'] = 'through-hole'
        pad['layer'] = ['topCopper', 'topMask', 'intCopper', 'bottomCopper', 'bottomMask']
        pad['width'] = housing.get('padDiameter', housing.get('padWidth'))
        pad['height'] = housing.get('padDiameter', housing.get('padHeight'))
    else:
        pad['type'] = 'mounting-hole'
        pad['layer'] = ['topCopper', 'topMask', 'intCopper', 'bottomCopper', 'bottomMask']
        pad['width'] = housing['holeDiameter']
        pad['height'] = housing['holeDiameter']
        pad['shape'] = 'circle'
    if housing.get('toppaste'):
        pad['layer'].append('topPaste')
    if housing.get('bottompaste'):
        pad['layer'].append('bottomPaste')

    pattern.pad(1, pad)
    copper.mask(pattern)

    if 'viaDiameter' in housing:
        d = housing.get('padDiameter', min(housing.get('padWidth', 0), housing.get('padHeight', 0)))
        via_pad = {
            'type': 'through-hole',
            'shape': 'circle',
            'hole': housing['viaDiameter'],
            'width': housing['viaDiameter'] + settings['minimum']['ringWidth'],
            'height': housing['viaDiameter'] + settings['minimum']['ringWidth'],
            'layer': ['topCopper', 'bottomCopper'],
        }
        count = housing.get('viaCount', 8)
        r = housing['holeDiameter'] / 2 + (d - housing['holeDiameter']) / 4
        import math
        for i in range(0, count):
            angle = i * 2 * math.pi / count
            via_pad['x'] = r * math.cos(angle)
            via_pad['y'] = r * math.sin(angle)
            pattern.pad(1, via_pad)

    housing.setdefault('keepout', {'M': 0.5, 'N': 0.25, 'L': 0.12}[settings['densityLevel']])
    housing.setdefault('bodyWidth', housing.get('bodyDiameter'))
    csize = {
        'radius': (housing.get('bodyWidth', {}).get('max', pad['width'])) / 2,
        'halfwidth': (housing.get('bodyWidth', {}).get('max', pad['width'])) / 2,
        'halfheight': (housing.get('bodyHeight', {}).get('max', pad['height'])) / 2,
    }
    courtyard.preamble(pattern, housing)
    if pad['shape'] == 'circle':
        pattern.circle(0, 0, csize['radius'] + housing['keepout'])
    else:
        pattern.rectangle(
            -csize['halfwidth'] - housing['keepout'],
            -csize['halfheight'] - housing['keepout'],
            csize['halfwidth'] / 2 + housing['keepout'],
            csize['halfheight'] + housing['keepout'],
        )

    pattern.layer('topAssembly').lineWidth(settings['lineWidth']['assembly']).attribute(
        'refDes', {'x': 0, 'y': 0, 'halign': 'center', 'valign': 'center'}
    ).attribute(
        'value', {'text': pattern.name, 'x': 0, 'y': 0, 'halign': 'center', 'valign': 'center', 'visible': False}
    )

