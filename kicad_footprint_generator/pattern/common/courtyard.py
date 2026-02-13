def preamble(pattern, housing):
    line_width = pattern.settings['lineWidth']['courtyard']
    pattern.layer('topCourtyard').lineWidth(line_width)
    return pattern


def body(pattern, housing, courtyard=None):
    settings = pattern.settings
    if courtyard is None:
        courtyard = housing.get('courtyard', {'M': 0.5, 'N': 0.25, 'L': 0.12}[settings['densityLevel']])
    body_width = housing['bodyWidth']['nom']
    body_length = housing['bodyLength']['nom']
    x = body_width / 2 + courtyard
    y = body_length / 2 + courtyard
    preamble(pattern, housing).rectangle(-x, -y, x, y)


def connector(pattern, housing, courtyard):
    body_width = housing['bodyWidth']['nom']
    body_length = housing['bodyLength']['nom']
    x = body_width / 2 + courtyard
    y = body_length / 2 + courtyard
    preamble(pattern, housing).rectangle(-x, -y, x, y)


def boundary(pattern, housing, courtyard=None):
    settings = pattern.settings
    if courtyard is None:
        courtyard = housing.get('courtyard', {'M': 0.5, 'N': 0.25, 'L': 0.12}[settings['densityLevel']])
    pads = list(pattern.pads.values())
    xmin = -housing['bodyWidth']['nom'] / 2
    ymin = -housing['bodyLength']['nom'] / 2
    xmax = housing['bodyWidth']['nom'] / 2
    ymax = housing['bodyLength']['nom'] / 2
    for v in pads:
        xmin = min(xmin, v.x - v.width / 2)
        xmax = max(xmax, v.x + v.width / 2)
        ymin = min(ymin, v.y - v.height / 2)
        ymax = max(ymax, v.y + v.height / 2)
    preamble(pattern, housing).rectangle(xmin - courtyard, ymin - courtyard, xmax + courtyard, ymax + courtyard)


def boundary_flex(pattern, housing, courtyard=None):
    """
    Creates flexible courtyard that closely follows body and pad shapes.
    Step 2: Trace the contour of the union of body and pad rectangles.
    """
    settings = pattern.settings
    if courtyard is None:
        courtyard = housing.get('courtyard', {'M': 0.5, 'N': 0.25, 'L': 0.12}[settings['densityLevel']])
    
    preamble(pattern, housing)
    
    # Collect all rectangles (body + pads)
    rectangles = []
    
    # Add body rectangle
    body_width = housing['bodyWidth']['nom']
    body_length = housing['bodyLength']['nom']
    body_rect = {
        'x1': -body_width / 2 - courtyard,
        'y1': -body_length / 2 - courtyard,
        'x2': body_width / 2 + courtyard,
        'y2': body_length / 2 + courtyard
    }
    rectangles.append(body_rect)
    
    # Add pad rectangles
    pads = list(pattern.pads.values())
    for pad in pads:
        pad_rect = {
            'x1': pad.x - pad.width / 2 - courtyard,
            'y1': pad.y - pad.height / 2 - courtyard,
            'x2': pad.x + pad.width / 2 + courtyard,
            'y2': pad.y + pad.height / 2 + courtyard
        }
        rectangles.append(pad_rect)
    
    # Find all unique x and y coordinates
    x_coords = set()
    y_coords = set()
    for rect in rectangles:
        x_coords.update([rect['x1'], rect['x2']])
        y_coords.update([rect['y1'], rect['y2']])
    
    x_coords = sorted(x_coords)
    y_coords = sorted(y_coords)
    
    # Create a grid and mark cells that are covered by any rectangle
    grid = {}
    for i in range(len(x_coords) - 1):
        for j in range(len(y_coords) - 1):
            x_center = (x_coords[i] + x_coords[i + 1]) / 2
            y_center = (y_coords[j] + y_coords[j + 1]) / 2
            
            # Check if this cell center is inside any rectangle
            covered = False
            for rect in rectangles:
                if (rect['x1'] <= x_center <= rect['x2'] and 
                    rect['y1'] <= y_center <= rect['y2']):
                    covered = True
                    break
            
            grid[(i, j)] = covered
    
    # Trace the contour by finding boundary edges
    def is_covered(i, j):
        return grid.get((i, j), False)
    
    # Find horizontal edges (top and bottom of covered cells)
    horizontal_edges = []
    for i in range(len(x_coords) - 1):
        for j in range(len(y_coords)):
            # Check if there's a horizontal edge at y_coords[j]
            above_covered = is_covered(i, j) if j < len(y_coords) - 1 else False
            below_covered = is_covered(i, j - 1) if j > 0 else False
            
            if above_covered != below_covered:
                horizontal_edges.append({
                    'x1': x_coords[i], 'x2': x_coords[i + 1], 
                    'y': y_coords[j], 'direction': 'up' if above_covered else 'down'
                })
    
    # Find vertical edges (left and right of covered cells)
    vertical_edges = []
    for i in range(len(x_coords)):
        for j in range(len(y_coords) - 1):
            # Check if there's a vertical edge at x_coords[i]
            left_covered = is_covered(i - 1, j) if i > 0 else False
            right_covered = is_covered(i, j) if i < len(x_coords) - 1 else False
            
            if left_covered != right_covered:
                vertical_edges.append({
                    'y1': y_coords[j], 'y2': y_coords[j + 1], 
                    'x': x_coords[i], 'direction': 'right' if right_covered else 'left'
                })
    
    # Draw the contour lines
    for edge in horizontal_edges:
        pattern.line(edge['x1'], edge['y'], edge['x2'], edge['y'])
    
    for edge in vertical_edges:
        pattern.line(edge['x'], edge['y1'], edge['x'], edge['y2'])


def dual(pattern, housing, courtyard):
    body_width = housing['bodyWidth']['nom']
    body_length = housing['bodyLength']['nom']
    housing.setdefault('bodyPosition', '0, 0')
    bx, by = [float(v) for v in housing['bodyPosition'].replace(' ', '').split(',')]
    first_pad, last_pad = pattern.extreme_pads()

    x1 = first_pad.x - first_pad.width / 2 - courtyard
    x2 = -body_width / 2 - courtyard
    if x1 > x2:
        x1 = x2
    x3 = body_width / 2 + courtyard
    x4 = last_pad.x + last_pad.width / 2 + courtyard
    if x4 < x3:
        x4 = x3
    y1 = -body_length / 2 - courtyard
    yl2 = first_pad.y - first_pad.height / 2 - courtyard
    if y1 > yl2:
        y1 = yl2
    yr2 = last_pad.y - last_pad.height / 2 - courtyard
    if y1 > yr2:
        y1 = yr2
    yl3 = -yl2 - 2 * by
    yr3 = -yr2 - 2 * by
    y4 = body_length / 2 + courtyard

    preamble(pattern, housing)
    pattern.moveTo(x1, yl2).lineTo(x2, yl2).lineTo(x2, y1).lineTo(x3, y1).lineTo(x3, yr2).lineTo(x4, yr2).lineTo(x4, yr3).lineTo(x3, yr3).lineTo(x3, y4).lineTo(x2, y4).lineTo(x2, yl3).lineTo(x1, yl3).lineTo(x1, yl2)


def grid_array(pattern, housing, courtyard):
    body_width = housing['bodyWidth']['nom']
    body_length = housing['bodyLength']['nom']
    first_pad, last_pad = pattern.extreme_pads()
    x1 = min(-body_width / 2, first_pad.x - first_pad.width / 2) - courtyard
    y1 = min(-body_length / 2, first_pad.y - first_pad.height / 2) - courtyard
    x2 = max(body_width / 2, last_pad.x - last_pad.width / 2) + courtyard
    y2 = max(body_length / 2, last_pad.y - last_pad.height / 2) + courtyard
    preamble(pattern, housing).rectangle(x1, y1, x2, y2)


def pak(pattern, housing, courtyard):
    body_width = housing.get('bodyWidth', {}).get('nom', housing.get('bodyWidth', {}).get('max'))
    body_length = housing.get('bodyLength', {}).get('nom', housing.get('bodyLength', {}).get('max'))
    lead_span = housing['leadSpan']['nom']
    tab = housing.get('tabLedge')
    if isinstance(tab, dict):
        tab_ledge = tab.get('nom', tab.get('min', tab.get('max', 0)))
    else:
        tab_ledge = tab if tab is not None else 0
    first_pad, last_pad = pattern.extreme_pads()

    x1 = first_pad.x - first_pad.width / 2 - courtyard
    x2 = lead_span / 2 - tab_ledge - body_width - courtyard
    x3 = last_pad.x - last_pad.width / 2 - courtyard
    x4 = lead_span / 2 - tab_ledge + courtyard
    x5 = last_pad.x + last_pad.width / 2 + courtyard
    y1 = first_pad.y - first_pad.height / 2 - courtyard
    y2 = -body_length / 2 - courtyard
    y3 = last_pad.y - last_pad.height / 2 - courtyard
    ym = min(y2, y3)

    preamble(pattern, housing)
    pattern.moveTo(x1, y1).lineTo(x2, y1).lineTo(x2, y2).lineTo(x3, y2).lineTo(x3, ym).lineTo(x4, ym).lineTo(x4, y3).lineTo(x5, y3).lineTo(x5, -y3).lineTo(x4, -y3).lineTo(x4, -ym).lineTo(x3, -ym).lineTo(x3, -y2).lineTo(x2, -y2).lineTo(x2, -y1).lineTo(x1, -y1).lineTo(x1, y1)


def quad(pattern, housing, courtyard):
    body_width = housing['bodyWidth']['nom']
    body_length = housing['bodyLength']['nom']
    first_pad, last_pad = pattern.extreme_pads()

    x1 = first_pad.x - first_pad.width / 2 - courtyard
    x2 = -body_width / 2 - courtyard
    x3 = last_pad.x - last_pad.width / 2 - courtyard
    if x1 > x2:
        x1 = x2
    if x2 > x3:
        x2 = x3
    x4 = -x3
    x5 = -x2
    x6 = -x1

    y1 = last_pad.y - last_pad.height / 2 - courtyard
    y2 = -body_length / 2 - courtyard
    y3 = first_pad.y - first_pad.height / 2 - courtyard
    if y1 > y2:
        y1 = y2
    if y2 > y3:
        y2 = y3
    y4 = -y3
    y5 = -y2
    y6 = -y1

    preamble(pattern, housing)
    pattern.moveTo(x1, y3).lineTo(x2, y3).lineTo(x2, y2).lineTo(x3, y2).lineTo(x3, y1).lineTo(x4, y1).lineTo(x4, y2).lineTo(x5, y2).lineTo(x5, y3).lineTo(x6, y3).lineTo(x6, y4).lineTo(x5, y4).lineTo(x5, y5).lineTo(x4, y5).lineTo(x4, y6).lineTo(x3, y6).lineTo(x3, y5).lineTo(x2, y5).lineTo(x2, y4).lineTo(x1, y4).lineTo(x1, y3)


def two_pin(pattern, housing, courtyard):
    if 'bodyWidth' in housing and 'bodyLength' in housing:
        body_width = housing['bodyWidth']['nom']
        body_length = housing['bodyLength']['nom']
        pads = list(pattern.pads.values())
        first_pad = pads[0]
        last_pad = pads[-1]
        
        if housing.get('chip'):
            # For chip: rotated 90° CCW - swap x/y logic
            y1 = first_pad.height / 2 + courtyard
            y2 = body_width / 2 + courtyard
            ym = max(y1, y2)
            x1 = last_pad.x + last_pad.width / 2 + courtyard
            x2 = body_length / 2 + courtyard
            preamble(pattern, housing)
            pattern.moveTo(-x1, -y1).lineTo(-x2, -y1).lineTo(-x2, -ym).lineTo(x2, -ym).lineTo(x2, -y1).lineTo(x1, -y1).lineTo(x1, y1).lineTo(x2, y1).lineTo(x2, ym).lineTo(-x2, ym).lineTo(-x2, y1).lineTo(-x1, y1).lineTo(-x1, -y1)
        else:
            # Standard two-pin orientation
            x1 = first_pad.width / 2 + courtyard
            x2 = body_width / 2 + courtyard
            xm = max(x1, x2)
            y1 = last_pad.y + last_pad.height / 2 + courtyard
            y2 = body_length / 2 + courtyard
            preamble(pattern, housing)
            pattern.moveTo(-x1, -y1).lineTo(-x1, -y2).lineTo(-xm, -y2).lineTo(-xm, y2).lineTo(-x1, y2).lineTo(-x1, y1).lineTo(x1, y1).lineTo(x1, y2).lineTo(xm, y2).lineTo(xm, -y2).lineTo(x1, -y2).lineTo(x1, -y1).lineTo(-x1, -y1)
    elif 'bodyDiameter' in housing:
        preamble(pattern, housing)
        pattern.circle(0, 0, housing['bodyDiameter']['nom'] / 2 + courtyard)

