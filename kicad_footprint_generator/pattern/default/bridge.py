def build(pattern, element):
    housing = element['housing']
    if not getattr(pattern, 'name', None):
        pattern.name = element['name'].upper()
    pad = {
        'type': 'smd',
        'x': -housing['padWidth'] / 2,
        'y': 0,
        'width': housing['padWidth'],
        'height': housing['padHeight'],
        'shape': 'rectangle',
        'layer': ['topCopper'],
    }
    pattern.pad(1, pad)
    pad2 = dict(pad)
    pad2['x'] = -pad2['x']
    pattern.pad(2, pad2)

