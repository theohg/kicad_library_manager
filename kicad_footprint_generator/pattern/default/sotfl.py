from ..common import assembly, calculator, copper, courtyard, mask, silkscreen


def build(pattern, element):
    housing = element['housing']
    housing['polarized'] = True
    housing['sot23'] = True  # Flag for SOT-23-specific silkscreen/assembly
    settings = pattern.settings
    flatlead = housing.get('flatlead', False)
    if not getattr(pattern, 'name', None):
        # SOTFL naming: SOTFL-{leadCount}P{pitch}_{leadSpan}X{bodyWidth}X{height}L{leadLength}X{leadWidth}{density}
        pitch_h = int(round(housing['pitch'] * 100))
        ls = int(round(housing['leadSpan']['nom'] * 100))
        bw = int(round(housing['bodyWidth']['nom'] * 100))
        bl = int(round(housing['bodyLength']['nom'] * 100))
        bh = int(round(housing['height']['max'] * 100))
        
        # Use nominal values for lead dimensions
        ll = housing.get('leadLength', {}).get('nom')
        if ll is None:
            # Calculate nominal from min/max if not provided
            ll_min = housing.get('leadLength', {}).get('min', 0)
            ll_max = housing.get('leadLength', {}).get('max', 0)
            ll = (ll_min + ll_max) / 2 if ll_max > 0 else 0
        
        lw = housing.get('leadWidth', {}).get('nom')
        if lw is None:
            # Calculate nominal from min/max if not provided
            lw_min = housing.get('leadWidth', {}).get('min', 0)
            lw_max = housing.get('leadWidth', {}).get('max', 0)
            lw = (lw_min + lw_max) / 2 if lw_max > 0 else 0
        
        # Get component type (ICSOFL or TRXSOFL)
        comp_type = housing.get('componentType', 'ICSOFL')
        pattern.name = f"{comp_type}{int(round(housing['leadCount']))}P{pitch_h:03d}_{ls:03d}X{bh:03d}L{int(round(ll*100)):03d}X{int(round(lw*100)):03d}{settings['densityLevel']}"
        
        # Generate description and tags
        pin_count = int(housing['leadCount'])
        pitch = housing['pitch']
        body_w = housing['bodyWidth']['nom']
        body_l = housing['bodyLength']['nom']
        h = housing['height']['max']
        density_desc = {'L': 'Least', 'N': 'Nominal', 'M': 'Most'}[settings['densityLevel']]
        
        pattern.description = (f"Small Outline Transistor Flat Lead (SOTFL), {pin_count} Pin "
                             f"({pitch:.2f}mm pitch), Body {body_l:.2f}mm x {body_w:.2f}mm x {h:.2f}mm, "
                             f"Lead {ll:.2f}mm x {lw:.2f}mm, {density_desc} Density")
        pattern.tags = "sotfl"

    if housing['leadCount'] % 2 == 0 and housing['leadCount'] != 6:
        from .sop import build as sop_build
        return sop_build(pattern, element)

    # Ensure leadWidth1 and leadWidth2 are set for sotfl() function
    if 'leadWidth1' not in housing:
        housing['leadWidth1'] = housing['leadWidth']
    if 'leadWidth2' not in housing:
        housing['leadWidth2'] = housing['leadWidth']
    
    # Use custom SOTFL calculator
    pad_params = calculator.sotfl(pattern.__dict__, housing)

    if housing['leadCount'] == 3:
        left_count, left_pitch = 2, housing['pitch'] * 2
        right_count, right_pitch = 1, housing['pitch']
    elif housing['leadCount'] == 5:
        left_count, left_pitch = 3, housing['pitch']
        right_count, right_pitch = 2, housing['pitch'] * 2
    elif housing['leadCount'] == 6:
        left_count, left_pitch = 3, housing['pitch']
        right_count, right_pitch = 3, housing['pitch']
    else:
        raise ValueError(f"Wrong lead count ({housing['leadCount']})")

    pad = {
        'type': 'smd',
        'shape': 'rectangle',
        'width': pad_params['width1'],
        'height': pad_params['height1'],
        'layer': ['topCopper', 'topMask', 'topPaste'],
    }

    pad_left = dict(pad)
    pad_left['x'] = -pad_params['distance'] / 2
    y = -left_pitch * (left_count / 2 - 0.5)
    for i in range(1, left_count + 1):
        pad_left['y'] = y
        pattern.pad(i, pad_left)
        y += left_pitch

    pad_right = dict(pad)
    pad_right['x'] = pad_params['distance'] / 2
    y = right_pitch * (right_count / 2 - 0.5)
    for i in range(1, right_count + 1):
        pad_right['y'] = y
        pattern.pad(left_count + i, pad_right)
        y -= right_pitch

    copper.mask(pattern)
    
    # Custom silkscreen for SOTFL
    _sotfl_silkscreen(pattern, housing)
    
    assembly.sot23(pattern, housing)
    courtyard.boundary_flex(pattern, housing, pad_params['courtyard'])
    mask.dual(pattern, housing)


def _sotfl_silkscreen(pattern, housing):
    """Custom silkscreen for SOTFL with special 3-lead corner lines"""
    s = pattern.settings
    lw = s['lineWidth']['silkscreen']
    w = housing['bodyWidth']['nom']
    l = housing['bodyLength']['nom']
    gap = lw / 2 + s['clearance']['padToSilk']
    
    # Basic silkscreen setup
    silkscreen.preamble(pattern, housing)
    
    # Body boundaries
    body_left = -w / 2
    body_right = w / 2
    body_bottom = -l / 2 - lw / 2
    body_top = l / 2 + lw / 2
    
    # Draw horizontal lines (top and bottom) like SOT23
    pattern.line(body_left, body_bottom, body_right, body_bottom)  # bottom line
    pattern.line(body_left, body_top, body_right, body_top)  # top line
    
    # Special case for 3-lead: add corner lines on the right side
    if housing['leadCount'] == 3:
        # Get the third pad (single pad on right side)
        pad3 = pattern.pads['3']  # pad numbering: 1,2 on left, 3 on right
        pad3_y_top = pad3.y + pad3.height / 2 + gap
        pad3_y_bottom = pad3.y - pad3.height / 2 - gap
        
        # Offset vertical lines outside body by half line width (0.12/2 = 0.06)
        line_offset = lw / 2
        right_line_x = body_right + line_offset
        
        # Right vertical line from body bottom to pad clearance
        pattern.line(right_line_x, body_bottom, right_line_x, pad3_y_bottom)
        
        # Right vertical line from pad clearance to body top  
        pattern.line(right_line_x, pad3_y_top, right_line_x, body_top)
        
        # Corner lines to connect with horizontal lines
        pattern.line(body_right, body_bottom, right_line_x, body_bottom)  # bottom corner
        pattern.line(body_right, body_top, right_line_x, body_top)  # top corner
    
    # Add pin 1 indicator for polarized components
    if housing.get('polarized'):
        pad1 = pattern.pads['1']
        pad1_x = pad1.x
        pad1_y = pad1.y
        pad1_size_y = pad1.height
        silk_to_pad_clearance = s['clearance']['silkToPad']
        
        # Pin 1 dot position (same as original implementation)
        dot1_y = pad1_y - pad1_size_y/2 - 0.25 - silk_to_pad_clearance
        dot1_x = pad1_x
        
        # Check for collision with silkscreen lines and maintain minimum distance
        min_silk_distance = 0.2  # 0.2mm minimum silk-to-silk distance
        dot_radius = 0.2    # dot radius
        dot_line_width = 0.1  # dot line width
        silk_line_width = lw  # silkscreen line width (typically 0.12mm)
        
        # Calculate required clearance from dot center to line center
        # This accounts for: dot radius + dot line width/2 + min clearance + silk line width/2
        dot_outer_radius = dot_radius + dot_line_width / 2
        required_clearance = dot_outer_radius + min_silk_distance + silk_line_width / 2
        
        # Check distance from dot center to line centers (top and bottom)
        distance_to_top = abs(dot1_y - body_top)
        distance_to_bottom = abs(dot1_y - body_bottom)
        
        # If too close to horizontal lines, move dot left to maintain clearance
        if distance_to_top < required_clearance or distance_to_bottom < required_clearance:
            # Move dot left by the amount needed to clear the minimum distance
            # Consider the closest horizontal line
            closest_line_distance = min(distance_to_top, distance_to_bottom)
            if closest_line_distance < required_clearance:
                # Calculate how much to move left to achieve required_clearance
                move_distance = required_clearance - closest_line_distance
                dot1_x = pad1_x - move_distance
        
        # For 3-lead packages, also check distance to vertical corner lines
        if housing['leadCount'] == 3:
            # Check distance to the right vertical lines (if they exist)
            line_offset = lw / 2
            right_line_x = body_right + line_offset
            distance_to_right_line = abs(dot1_x - right_line_x)
            
            # If too close to right vertical line, move dot further left
            if distance_to_right_line < required_clearance:
                move_distance = required_clearance - distance_to_right_line
                dot1_x = dot1_x - move_distance
        
        # Ensure dot doesn't go too far left (stay reasonable relative to pad)
        max_left_offset = pad1_x - 1.0  # Don't move more than 1mm left from pad center
        if dot1_x < max_left_offset:
            dot1_x = max_left_offset
        
        # Draw pin 1 dot (filled circle, 0.2mm radius like original)
        pattern.layer('topSilkscreen').lineWidth(0.1).fill(True).circle(dot1_x, dot1_y, 0.2).fill(False)

