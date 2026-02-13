def _centroid(pattern):
    line_width = pattern.settings['lineWidth']['assembly']
    return (
        pattern.layer('topAssembly')
        .lineWidth(line_width)
        # Centroid markings removed per request
    )


def preamble(pattern, housing):
    settings = pattern.settings
    if 'bodyWidth' in housing and isinstance(housing['bodyWidth'], dict):
        w = housing['bodyWidth']['nom']
    elif 'bodyDiameter' in housing and isinstance(housing['bodyDiameter'], dict):
        w = housing['bodyDiameter']['nom']
    else:
        # Fallback for DIP: approximate width by lead span if body width absent
        w = housing.get('leadSpan', {}).get('nom', 0)
    if 'bodyLength' in housing and isinstance(housing['bodyLength'], dict):
        h = housing['bodyLength']['nom']
    elif 'bodyDiameter' in housing and isinstance(housing['bodyDiameter'], dict):
        h = housing['bodyDiameter']['nom']
    else:
        h = 0
    line_width = settings['lineWidth']['assembly']
    angle = 90 if w < h else 0
    # Rotate fabrication layer texts 90 degrees clockwise
    fab_angle = angle
    
    # Calculate reference text size based on component length
    component_length = max(w, h)  # Use the longer dimension as component length
    ref_text_size = min(component_length / 4, 0.8)
    
    # Font size is computed from text size as usual
    font_size = ref_text_size
    max_font = 0.66 * min(w, h)
    if font_size > max_font:
        font_size = max_font
    text_line_width = min(line_width, font_size / 5)
    
    # Calculate text position for VALUE (below component)
    body_y = max(w, h) / 2
    pad_y = 0.7  # estimated pad height/2 + margin
    courtyard = settings.get('clearance', {}).get('courtyard', 0.25)
    value_text_y = max(body_y, pad_y) + courtyard + 0.75
    
    (
        _centroid(pattern)
        .layer('topAssembly')
        .lineWidth(text_line_width)
        .attribute(
            'reference',
            {
                'text': '${REFERENCE}',
                'x': 0,
                'y': 0,
                'angle': fab_angle,
                'fontSize': font_size,
                'halign': 'center',
                'valign': 'center',
            },
        )
        .attribute(
            'value',
            {
                'text': pattern.name,
                'x': 0,
                'y': value_text_y,
                'angle': fab_angle,
                'fontSize': font_size,
                'halign': 'center',
                'valign': 'center',
            },
        )
        .attribute(
            'user',
            {
                'text': 'REF**',
                'x': 0,
                'y': 0,
                'angle': angle,
                'fontSize': font_size,
                'halign': 'center',
                'valign': 'center',
                'visible': False,
            },
        )
        .lineWidth(line_width)
    )
    return pattern


def body(pattern, housing):
    bw = housing['bodyWidth']['nom']
    bl = housing['bodyLength']['nom']
    x = bw / 2
    y = bl / 2
    preamble(pattern, housing).rectangle(-x, -y, x, y)


def polarized(pattern, housing):
    bw = housing.get('bodyWidth', {}).get('nom', housing.get('bodyWidth', {}).get('max', 0))
    bl = housing.get('bodyLength', {}).get('nom', housing.get('bodyLength', {}).get('max', 0))
    x = bw / 2
    y = bl / 2
    d = min(1, bw / 2, bl / 2)
    preamble(pattern, housing)
    pattern.moveTo(-x + d, -y).lineTo(x, -y).lineTo(x, y).lineTo(-x, y).lineTo(-x, -y + d).lineTo(-x + d, -y)


def pak(pattern, element):
    housing = element['housing']
    bw = housing.get('bodyWidth', {}).get('nom', housing.get('bodyWidth', {}).get('max', 0))
    bl = housing.get('bodyLength', {}).get('nom', housing.get('bodyLength', {}).get('max', 0))
    ls = housing['leadSpan']['nom']
    tl = housing.get('tabLedge')
    if isinstance(tl, dict):
        tab_ledge = tl.get('nom', tl.get('min', tl.get('max', 0)))
    else:
        tab_ledge = tl if tl is not None else 0
    tw = housing.get('tabWidth')
    if isinstance(tw, dict):
        tab_width = tw.get('nom', tw.get('min', tw.get('max', 0)))
    else:
        tab_width = tw if tw is not None else 0
    x1 = ls / 2 - tab_ledge
    x2 = x1 - bw
    preamble(pattern, housing).rectangle(x1, -bl / 2, x2, bl / 2).rectangle(x1, -tab_width / 2, x1 + tab_ledge, tab_width / 2)
    pins = element['pins']
    y = -housing['pitch'] * (housing['leadCount'] / 2 - 0.5)
    for i in range(1, housing['leadCount'] + 1):
        if str(i) in pins:
            pattern.line(-ls / 2, y, x2, y)
        y += housing['pitch']


def quad(pattern, housing):
    """Assembly outline for quad packages with pin 1 dot marker instead of chamfered edge"""
    bw = housing['bodyWidth']['nom']
    bl = housing['bodyLength']['nom']
    x = bw / 2
    y = bl / 2
    
    preamble(pattern, housing)
    # Draw simple rectangle (no chamfered edge)
    pattern.rectangle(-x, -y, x, y)
    
    # Add pin 1 dot marker 0.8mm from corner toward center
    dot_offset = 0.8
    dot_x = -x + dot_offset  # 0.8mm from left edge toward center
    dot_y = -y + dot_offset  # 0.8mm from top edge toward center
    
    # Draw the dot (circle with 0.2mm radius, 0.1mm line width, filled)
    pattern.layer('topAssembly').lineWidth(0.1).fill(True).circle(dot_x, dot_y, 0.2).fill(False)


def son(pattern, housing):
    """Assembly outline for SON packages with pin 1 dot marker instead of chamfered edge"""
    bw = housing['bodyWidth']['nom']
    bl = housing['bodyLength']['nom']
    x = bw / 2
    y = bl / 2
    
    preamble(pattern, housing)
    # Draw simple rectangle (no chamfered edge)
    pattern.rectangle(-x, -y, x, y)
    
    # Add pin 1 dot marker 0.5mm from corner toward center
    dot_offset = 0.5
    dot_x = -x + dot_offset  # 0.5mm from left edge toward center
    dot_y = -y + dot_offset  # 0.5mm from top edge toward center
    
    # Draw the dot (circle with 0.2mm radius, 0.1mm line width, filled)
    pattern.layer('topAssembly').lineWidth(0.1).fill(True).circle(dot_x, dot_y, 0.2).fill(False)


def sot23(pattern, housing):
    """Assembly outline for SOT-23 packages with pin 1 dot marker instead of chamfered edge"""
    bw = housing['bodyWidth']['nom']
    bl = housing['bodyLength']['nom']
    x = bw / 2
    y = bl / 2
    
    # Custom preamble for SOT-23 with smaller reference text
    settings = pattern.settings
    w = bw
    h = bl
    line_width = settings['lineWidth']['assembly']
    angle = 90 if w < h else 0
    # Rotate fabrication layer texts 90 degrees clockwise
    fab_angle = angle
    
    # Text size scaled by body length (not width)
    ref_text_size = 0.4
    
    # Font size is computed from text size as usual
    font_size = ref_text_size
    max_font = 0.66 * min(w, h)
    if font_size > max_font:
        font_size = max_font
    text_line_width = min(line_width, font_size / 5)
    
    # Calculate text position for VALUE (below component) and REFERENCE (above component)
    body_y = max(w, h) / 2
    pad_y = 0.7  # estimated pad height/2 + margin
    courtyard = settings.get('clearance', {}).get('courtyard', 0.25)
    value_text_y = max(body_y, pad_y) + courtyard + 0.75
    
    (
        _centroid(pattern)
        .layer('topAssembly')
        .lineWidth(text_line_width)
        .attribute(
            'reference',
            {
                'text': '${REFERENCE}',
                'x': 0,
                'y': 0,
                'angle': fab_angle,
                'fontSize': font_size,
                'halign': 'center',
                'valign': 'center',
            },
        )
        .attribute(
            'value',
            {
                'text': pattern.name,
                'x': 0,
                'y': value_text_y,
                'angle': fab_angle,
                'fontSize': font_size,
                'halign': 'center',
                'valign': 'center',
            },
        )
        .attribute(
            'user',
            {
                'text': 'REF**',
                'x': 0,
                'y': 0,
                'angle': angle,
                'fontSize': font_size,
                'halign': 'center',
                'valign': 'center',
                'visible': False,
            },
        )
        .lineWidth(line_width)
    )
    
    # Draw simple rectangle (no chamfered edge)
    pattern.rectangle(-x, -y, x, y)
    
    # Add pin 1 dot marker 0.5mm from corner toward center (same as SON)
    dot_offset = 0.5
    dot_x = -x + dot_offset  # 0.5mm from left edge toward center
    dot_y = -y + dot_offset  # 0.5mm from top edge toward center
    
    # Draw the dot (circle with 0.2mm radius, 0.1mm line width, filled)
    pattern.layer('topAssembly').lineWidth(0.1).fill(True).circle(dot_x, dot_y, 0.2).fill(False)


def sop(pattern, housing):
    """Assembly outline for SOP packages with pin 1 dot marker instead of chamfered edge"""
    bw = housing['bodyWidth']['nom']
    bl = housing['bodyLength']['nom']
    x = bw / 2
    y = bl / 2
    
    # Custom preamble for SOP with reference text scaled by body length
    settings = pattern.settings
    w = bw
    h = bl
    line_width = settings['lineWidth']['assembly']
    angle = 90 if w < h else 0
    # Rotate fabrication layer texts 90 degrees clockwise
    fab_angle = angle
    
    # Text size scaled by body length (not width)
    component_length = bl  # Use body length for SOP
    ref_text_size = min(component_length / 4, 0.8)
    
    # Font size is computed from text size as usual
    font_size = ref_text_size
    max_font = 0.66 * min(w, h)
    if font_size > max_font:
        font_size = max_font
    text_line_width = min(line_width, font_size / 5)
    
    # Calculate text position for VALUE (below component) and REFERENCE (above component)
    body_y = max(w, h) / 2
    pad_y = 0.7  # estimated pad height/2 + margin
    courtyard = settings.get('clearance', {}).get('courtyard', 0.25)
    value_text_y = max(body_y, pad_y) + courtyard + 0.75
    
    (
        _centroid(pattern)
        .layer('topAssembly')
        .lineWidth(text_line_width)
        .attribute(
            'reference',
            {
                'text': '${REFERENCE}',
                'x': 0,
                'y': 0,
                'angle': fab_angle,
                'fontSize': font_size,
                'halign': 'center',
                'valign': 'center',
            },
        )
        .attribute(
            'value',
            {
                'text': pattern.name,
                'x': 0,
                'y': value_text_y,
                'angle': fab_angle,
                'fontSize': font_size,
                'halign': 'center',
                'valign': 'center',
            },
        )
        .attribute(
            'user',
            {
                'text': 'REF**',
                'x': 0,
                'y': 0,
                'angle': angle,
                'fontSize': font_size,
                'halign': 'center',
                'valign': 'center',
                'visible': False,
            },
        )
        .lineWidth(line_width)
    )
    
    # Draw simple rectangle (no chamfered edge)
    pattern.rectangle(-x, -y, x, y)
    
    # Add pin 1 dot marker 0.5mm from corner toward center (same as SON)
    dot_offset = 0.5
    dot_x = -x + dot_offset  # 0.5mm from left edge toward center
    dot_y = -y + dot_offset  # 0.5mm from top edge toward center
    
    # Draw the dot (circle with 0.2mm radius, 0.1mm line width, filled)
    pattern.layer('topAssembly').lineWidth(0.1).fill(True).circle(dot_x, dot_y, 0.2).fill(False)


def corner_concave(pattern, housing):
    """Assembly outline for corner concave oscillator with pin 1 dot marker instead of chamfered edge"""
    bw = housing['bodyWidth']['nom']
    bl = housing['bodyLength']['nom']
    x = bw / 2
    y = bl / 2
    
    preamble(pattern, housing)
    # Draw simple rectangle (no chamfered edge)
    pattern.rectangle(-x, -y, x, y)
    
    # Add pin 1 dot marker 0.5mm from corner toward center (pin 1 is top-left with [4,1,3,2] ordering)
    dot_offset = 0.5
    dot_x = -x + dot_offset  # 0.5mm from left edge toward center
    dot_y = y - dot_offset   # 0.5mm from top edge toward center (top-left corner)
    
    # Draw the dot (circle with 0.2mm radius, 0.1mm line width, filled)
    pattern.layer('topAssembly').lineWidth(0.1).fill(True).circle(dot_x, dot_y, 0.2).fill(False)


def sodfl_preamble(pattern, housing):
    """Preamble for SODFL components with proper text rotation (90° counterclockwise from chip)"""
    settings = pattern.settings
    
    # For SODFL, body dimensions are swapped like chip (bl/bw become x/y)
    bw = housing['bodyWidth']['nom']  # actual body width
    bl = housing['bodyLength']['nom']  # actual body length
    
    line_width = settings['lineWidth']['assembly']
    
    # For SODFL: rotate reference text 90 degrees counterclockwise (relative to chip's 90° clockwise)
    # This means 0 degrees (no rotation) since chip is 90° clockwise
    fab_angle = 0
    
    # Text size scaled by body length (longer dimension)
    component_length = bl  # Use body length for SODFL
    ref_text_size = min(component_length / 4, 0.8)
    
    # Font size is computed from text size as usual
    font_size = ref_text_size
    max_font = 0.66 * min(bw, bl)
    if font_size > max_font:
        font_size = max_font
    text_line_width = min(line_width, font_size / 5)
    
    # Calculate text position using real pad positions (similar to chip)
    if pattern.pads:
        pad_extent = 0
        for pad in pattern.pads.values():
            # Calculate the farthest point of each pad from center
            pad_extent = max(pad_extent, abs(pad.y) + pad.height / 2)
        
        if pad_extent == 0:
            pad_extent = 0.7  # fallback if no pads found
        
        # Use SODFL-specific positioning - reference text above component
        body_y = bw / 2  # Use body width for Y extent in SODFL coordinates
        courtyard = settings.get('clearance', {}).get('courtyard', 0.25)
        reference_text_y = -(max(body_y, pad_extent) + courtyard + 0.75)
    else:
        reference_text_y = -1.5  # fallback
    
    # Calculate value text position (below component)
    body_y = max(bw, bl) / 2
    pad_y = 0.7  # estimated pad height/2 + margin
    courtyard = settings.get('clearance', {}).get('courtyard', 0.25)
    value_text_y = max(body_y, pad_y) + courtyard + 0.75
    
    (
        _centroid(pattern)
        .layer('topAssembly')
        .lineWidth(text_line_width)
        .attribute(
            'reference',
            {
                'text': '${REFERENCE}',
                'x': 0,
                'y': 0,
                'angle': fab_angle,  # 0 degrees for SODFL
                'fontSize': font_size,
                'halign': 'center',
                'valign': 'center',
            },
        )
        .attribute(
            'value',
            {
                'text': pattern.name,
                'x': 0,
                'y': value_text_y,
                'angle': fab_angle,  # 0 degrees for SODFL
                'fontSize': font_size,
                'halign': 'center',
                'valign': 'center',
            },
        )
        .attribute(
            'user',
            {
                'text': 'REF**',
                'x': 0,
                'y': 0,
                'angle': 0,  # Keep user text at 0 degrees
                'fontSize': font_size,
                'halign': 'center',
                'valign': 'center',
                'visible': False,
            },
        )
        .lineWidth(line_width)
    )


def sodfl(pattern, housing):
    """Assembly outline for SODFL packages with pin 1 dot marker instead of chamfered edge (similar to SON)"""
    # For SODFL, use the chip coordinates (swapped x/y due to 90° rotation)
    bw = housing['bodyWidth']['nom']
    bl = housing['bodyLength']['nom']
    
    # Since SODFL is rotated like chip: x = bl/2, y = bw/2
    x = bl / 2  # Use body length for X extent
    y = bw / 2  # Use body width for Y extent
    
    sodfl_preamble(pattern, housing)
    # Draw simple rectangle (no chamfered edge)
    pattern.rectangle(-x, -y, x, y)
    
    # Add pin 1 dot marker 0.5mm from corner toward center (pin 1 is on the left in horizontal layout)
    dot_offset = 0.4
    dot_x = -x + dot_offset  # 0.5mm from left edge toward center
    dot_y = -y + dot_offset  # 0.5mm from bottom edge toward center (bottom-left corner)
    
    # Draw the dot (circle with 0.2mm radius, 0.1mm line width, filled)
    pattern.layer('topAssembly').lineWidth(0.1).fill(True).circle(dot_x, dot_y, 0.2).fill(False)


def molded_preamble(pattern, housing):
    """Preamble for molded components with proper text rotation (same as SODFL - 90° counterclockwise from chip)"""
    settings = pattern.settings
    
    # For molded, body dimensions are swapped like chip (bl/bw become x/y)
    bw = housing['bodyWidth']['nom']  # actual body width
    bl = housing['bodyLength']['nom']  # actual body length
    
    line_width = settings['lineWidth']['assembly']
    
    # For molded: rotate reference text 90 degrees counterclockwise (same as SODFL)
    fab_angle = 0
    
    # Text size scaled by body length (longer dimension)
    component_length = bl  # Use body length for molded
    ref_text_size = min(component_length / 4, 0.8)
    
    # Font size is computed from text size as usual
    font_size = ref_text_size
    max_font = 0.66 * min(bw, bl)
    if font_size > max_font:
        font_size = max_font
    text_line_width = min(line_width, font_size / 5)
    
    # Calculate text position using real pad positions (similar to chip)
    if pattern.pads:
        pad_extent = 0
        for pad in pattern.pads.values():
            # Calculate the farthest point of each pad from center
            pad_extent = max(pad_extent, abs(pad.y) + pad.height / 2)
        
        if pad_extent == 0:
            pad_extent = 0.7  # fallback if no pads found
        
        # Use molded-specific positioning - reference text above component
        body_y = bw / 2  # Use body width for Y extent in molded coordinates
        courtyard = settings.get('clearance', {}).get('courtyard', 0.25)
        reference_text_y = -(max(body_y, pad_extent) + courtyard + 0.75)
    else:
        reference_text_y = -1.5  # fallback
    
    # Calculate value text position (below component)
    body_y = max(bw, bl) / 2
    pad_y = 0.7  # estimated pad height/2 + margin
    courtyard = settings.get('clearance', {}).get('courtyard', 0.25)
    value_text_y = max(body_y, pad_y) + courtyard + 0.75
    
    (
        _centroid(pattern)
        .layer('topAssembly')
        .lineWidth(text_line_width)
        .attribute(
            'reference',
            {
                'text': '${REFERENCE}',
                'x': 0,
                'y': 0,
                'angle': fab_angle,  # 0 degrees for molded
                'fontSize': font_size,
                'halign': 'center',
                'valign': 'center',
            },
        )
        .attribute(
            'value',
            {
                'text': pattern.name,
                'x': 0,
                'y': value_text_y,
                'angle': fab_angle,  # 0 degrees for molded
                'fontSize': font_size,
                'halign': 'center',
                'valign': 'center',
            },
        )
        .attribute(
            'user',
            {
                'text': 'REF**',
                'x': 0,
                'y': 0,
                'angle': 0,  # Keep user text at 0 degrees
                'fontSize': font_size,
                'halign': 'center',
                'valign': 'center',
                'visible': False,
            },
        )
        .lineWidth(line_width)
    )


def molded(pattern, housing):
    """Assembly outline for molded packages with pin 1 dot marker instead of chamfered edge (similar to SODFL)"""
    # For molded, use the chip coordinates (swapped x/y due to 90° rotation)
    bw = housing['bodyWidth']['nom']
    bl = housing['bodyLength']['nom']
    
    # Since molded is rotated like chip: x = bl/2, y = bw/2
    x = bl / 2  # Use body length for X extent
    y = bw / 2  # Use body width for Y extent
    
    molded_preamble(pattern, housing)
    # Draw simple rectangle (no chamfered edge)
    pattern.rectangle(-x, -y, x, y)
    
    # Add pin 1 dot marker 0.4mm from corner toward center (pin 1 is on the left in horizontal layout)
    dot_offset = 0.4
    dot_x = -x + dot_offset  # 0.4mm from left edge toward center
    dot_y = -y + dot_offset  # 0.4mm from bottom edge toward center (bottom-left corner)
    
    # Draw the dot (circle with 0.2mm radius, 0.1mm line width, filled)
    pattern.layer('topAssembly').lineWidth(0.1).fill(True).circle(dot_x, dot_y, 0.2).fill(False)


def chip_preamble(pattern, housing):
    """Preamble for chip components with 90-degree clockwise rotated ${REFERENCE} text"""
    settings = pattern.settings
    
    # For chips, body dimensions are already swapped in the assembly function (bl/bw become x/y)
    # Use raw dimensions for text calculations
    bw = housing['bodyWidth']['nom']  # actual body width
    bl = housing['bodyLength']['nom']  # actual body length
    
    line_width = settings['lineWidth']['assembly']
    
    # For chip: always rotate reference text 90 degrees clockwise
    fab_angle = 90
    
    # Text size scaled by body length (longer dimension)
    component_length = bl  # Use body length for chip
    ref_text_size = min(component_length / 4, 0.8)
    
    # Font size is computed from text size as usual
    font_size = ref_text_size
    max_font = 0.66 * min(bw, bl)
    if font_size > max_font:
        font_size = max_font
    text_line_width = min(line_width, font_size / 5)
    
    # Calculate text position using real pad positions (similar to QFP)
    if pattern.pads:
        pad_extent = 0
        for pad in pattern.pads.values():
            # Calculate the farthest point of each pad from center
            pad_extent = max(pad_extent, abs(pad.y) + pad.height / 2)
        
        if pad_extent == 0:
            pad_extent = 0.7  # fallback if no pads found
        
        # Use chip-specific positioning - reference text above component
        body_y = bl / 2  # Use body length for Y extent in chip coordinates
        courtyard = settings.get('clearance', {}).get('courtyard', 0.25)
        reference_text_y = -(max(body_y, pad_extent) + courtyard + 0.75)
    else:
        reference_text_y = -1.5  # fallback
    
    # Calculate value text position (below component)
    body_y = max(bw, bl) / 2
    pad_y = 0.7  # estimated pad height/2 + margin
    courtyard = settings.get('clearance', {}).get('courtyard', 0.25)
    value_text_y = max(body_y, pad_y) + courtyard + 0.75
    
    (
        _centroid(pattern)
        .layer('topAssembly')
        .lineWidth(text_line_width)
        .attribute(
            'reference',
            {
                'text': '${REFERENCE}',
                'x': 0,
                'y': 0,
                'angle': 0,  # 90 degrees clockwise for chip
                'fontSize': font_size,
                'halign': 'center',
                'valign': 'center',
            },
        )
        .attribute(
            'value',
            {
                'text': pattern.name,
                'x': 0,
                'y': value_text_y,
                'angle': fab_angle,  # 90 degrees clockwise for chip
                'fontSize': font_size,
                'halign': 'center',
                'valign': 'center',
            },
        )
        .attribute(
            'user',
            {
                'text': 'REF**',
                'x': 0,
                'y': 0,
                'angle': 0,  # Keep user text at 0 degrees
                'fontSize': font_size,
                'halign': 'center',
                'valign': 'center',
                'visible': False,
            },
        )
        .lineWidth(line_width)
    )


def two_pin(pattern, housing):
    # Use SODFL-specific assembly logic for SODFL components
    if housing.get('sodfl'):
        sodfl(pattern, housing)
        return  # Early return since sodfl() handles everything
    # Use molded-specific assembly logic for molded components
    elif housing.get('molded'):
        molded(pattern, housing)
        return  # Early return since molded() handles everything
    # Use chip-specific assembly logic if it's a chip component
    elif housing.get('chip'):
        chip_preamble(pattern, housing)
    else:
        preamble(pattern, housing)
    
    if 'bodyWidth' in housing and 'bodyLength' in housing:
        bw = housing['bodyWidth']['nom']
        bl = housing['bodyLength']['nom']
        
        if housing.get('chip'):
            # For chip: rotated 90° CCW - swap x/y coordinates
            x = bl / 2
            y = bw / 2
            if housing.get('polarized'):
                d = min(1, bl / 2, bw / 2)
                pattern.moveTo(-x + d, -y).lineTo(x, -y).lineTo(x, y).lineTo(-x, y).lineTo(-x, -y + d).lineTo(-x + d, -y)
            else:
                pattern.rectangle(-x, -y, x, y)
        else:
            # Standard two-pin orientation
            x = bw / 2
            y = bl / 2
            if housing.get('cae'):
                # Use custom chamfer if provided, otherwise use default
                custom_chamfer = housing.get('chamfer')
                if custom_chamfer and str(custom_chamfer).strip():
                    try:
                        d = float(custom_chamfer)
                    except (ValueError, TypeError):
                        d = min(bw / 4, bl / 4)  # Fallback to default
                else:
                    d = min(bw / 4, bl / 4)  # Default chamfer size
                
                diam = housing.get('bodyDiameter', {}).get('nom', housing.get('bodyDiameter'))
                # Rotate 90° CCW: chamfer should be on the left, not the top
                # Left side: chamfer at top-left
                pattern.moveTo(-x, -y + d).lineTo(-x + d, -y).lineTo(x, -y).lineTo(x, y).lineTo(-x + d, y).lineTo(-x, y - d).lineTo(-x, -y + d)
                if diam is not None:
                    pattern.circle(0, 0, diam / 2)
                
                # Add "+" symbol below pad 1
                # Get pad 1 position (left pad)
                pads = list(pattern.pads.values())
                if len(pads) >= 1:
                    pad1 = pads[0]  # Left pad
                    plus_size = 0.7 / 2  # Half of 0.7mm line length
                    plus_y = pad1.y - pad1.height / 2 - 0.5  # Position below pad1 with 0.5mm spacing
                    plus_x = pad1.x  # Centered on pad1
                    
                    # Draw horizontal line of "+"
                    pattern.line(plus_x - plus_size, plus_y, plus_x + plus_size, plus_y)
                    # Draw vertical line of "+"
                    pattern.line(plus_x, plus_y - plus_size, plus_x, plus_y + plus_size)
            elif housing.get('polarized'):
                d = min(1, bw / 2, bl / 2)
                pattern.moveTo(-x + d, -y).lineTo(x, -y).lineTo(x, y).lineTo(-x, y).lineTo(-x, -y + d).lineTo(-x + d, -y)
            else:
                pattern.rectangle(-x, -y, x, y)
    elif 'bodyDiameter' in housing:
        pattern.circle(0, 0, housing['bodyDiameter']['nom'] / 2)


def dfn_molded_style(pattern, housing):
    """DFN-specific assembly outline matching molded style: no chamfer, pin 1 dot bottom-left, 0° fab_angle."""
    # Use molded preamble for text rotation/placement (same behavior requested)
    molded_preamble(pattern, housing)
    # Draw rectangle using DFN horizontal orientation (x = bl/2, y = bw/2)
    bw = housing['bodyWidth']['nom']
    bl = housing['bodyLength']['nom']
    x = bl / 2
    y = bw / 2
    pattern.rectangle(-x, -y, x, y)
    # Pin 1 dot at bottom-left similar to molded
    dot_offset = 0.4
    dot_x = -x + dot_offset
    dot_y = -y + dot_offset
    pattern.layer('topAssembly').lineWidth(0.1).fill(True).circle(dot_x, dot_y, 0.2).fill(False)

