def preamble(pattern, housing):
    pattern.layer('topMask').lineWidth(pattern.settings['lineWidth']['courtyard'])
    return pattern


def rect(pattern, housing):
    if housing.get('maskcutout'):
        pads = list(pattern.pads.values())
        first = pads[0]
        last = pads[-1]
        width = max(first.width, last.width, housing['bodyWidth']['max'])
        height = max(first.height, last.height, housing['bodyLength']['max'])
        width += pattern.settings['clearance']['padToMask']
        height += pattern.settings['clearance']['padToMask']
        preamble(pattern, housing).fill(True).rectangle(-width / 2, -height / 2, width / 2, height / 2).fill(False)


def dual(pattern, housing):
    rect(pattern, housing)


def quad(pattern, housing):
    rect(pattern, housing)


def two_pin(pattern, housing):
    if housing.get('maskcutout'):
        if 'bodyWidth' in housing and 'bodyLength' in housing:
            rect(pattern, housing)
        elif 'bodyDiameter' in housing:
            preamble(pattern, housing).fill(True).circle(0, 0, housing['bodyDiameter']['max'] / 2 + housing['maskCutout']).fill(False)

