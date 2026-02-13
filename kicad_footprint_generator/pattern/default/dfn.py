
from ..common import calculator, courtyard, silkscreen, assembly, copper


def _resolve_range(val, prefer='nom'):
    if isinstance(val, dict):
        return val.get(prefer, val.get('max', val.get('min', 0)))
    return float(val or 0)


def _get_dfn_component_prefix_and_details(comp_type, lead_count):
    """Get component prefix and description details based on component type"""
    # Component mapping with prefix, description, and tag
    component_map = {
        'capacitor': ('CAPDFN', 'Capacitor, DFN', 'capacitor'),
        'capacitor_polarized': ('CAPPDFN', 'Capacitor, Polarized, DFN', 'capacitor polarized'),
        'crystal': ('XTALDFN', 'Crystal, DFN', 'crystal'),
        'diode': ('DIODFN', 'Diode, DFN', 'diode'),
        'diode_non_polarized': ('DIONDFN', 'Diode, Non-polarized, DFN', 'diode non-polarized'),
        'fuse': ('FUSDFN', 'Fuse, DFN', 'fuse'),
        'inductor': ('INDDFN', 'Inductor, DFN', 'inductor'),
        'led': ('LEDDFN', 'LED, DFN', 'led'),
        'resistor': ('RESDFN', 'Resistor, DFN', 'resistor'),
        'transistor': ('TRXDFN', 'Transistor, DFN', 'transistor')
    }
    
    prefix, description_name, tag = component_map.get(comp_type, ('DIODFN', 'Diode, DFN', 'diode'))
    
    # Add pin count for multi-pin components 
    if comp_type in ['diode', 'diode_non_polarized', 'resistor', 'transistor'] and lead_count > 2:
        prefix += f"{lead_count}"
    
    return prefix, description_name, tag


def build(pattern, element):
    housing = element['housing']
    settings = pattern.settings
    lead_count = int(housing.get('leadCount', 2))
    if lead_count not in (2, 3, 4):
        lead_count = 2

    # Name
    if not getattr(pattern, 'name', None):
        # Get component type from housing
        comp_type = housing.get('componentType', 'diode')
        prefix, description_name, tag = _get_dfn_component_prefix_and_details(comp_type, lead_count)
        
        # Extract dimensions for naming
        bl = int(round(housing['bodyLength']['nom'] * 100))
        bw = int(round(housing['bodyWidth']['nom'] * 100))
        bh = int(round(housing.get('height', {}).get('max', 0) * 100))
        ll = housing.get('leadLength', {}).get('nom', (housing.get('leadLength', {}).get('min', 0) + housing.get('leadLength', {}).get('max', 0)) / 2)
        lw = housing.get('leadWidth', {}).get('nom', (housing.get('leadWidth', {}).get('min', 0) + housing.get('leadWidth', {}).get('max', 0)) / 2)
        
        # DFN component naming: PREFIX + BodyLength X BodyWidth X Height + L LeadLength X LeadWidth  
        pattern.name = f"{prefix}{bl:03d}X{bw:03d}X{bh:03d}L{int(round(ll*100)):03d}X{int(round(lw*100)):03d}{settings['densityLevel']}"
        
        # Generate description and tags
        density_desc = {'L': 'Least', 'N': 'Nominal', 'M': 'Most'}[settings['densityLevel']]
        
        bl_mm = housing['bodyLength']['nom']
        bw_mm = housing['bodyWidth']['nom']
        bh_mm = housing.get('height', {}).get('max', 0)
        ll_mm = ll
        lw_mm = lw
        
        pattern.description = (
            f"{description_name}, {lead_count} Pin, "
            f"Body {bl_mm:.2f}mm x {bw_mm:.2f}mm x {bh_mm:.2f}mm, "
            f"Lead {ll_mm:.2f}mm x {lw_mm:.2f}mm, "
            f"{density_desc} Density"
        )
        pattern.tags = tag

    # Compute small pad size via SON calculator for consistency with IPC
    son_housing = dict(housing)
    # Use e1 (pitch along length) for SON pitch context if provided
    e1 = housing.get('pitch1', housing.get('pitch'))
    if e1:
        son_housing['pitch'] = e1
    pad_params = calculator.son(pattern.__dict__, son_housing)
    small_w = pad_params['width']
    small_h = pad_params['height']
    cy = pad_params['courtyard']

    # Pitches
    # e: vertical distance between small pads (used for 4-pin configurations)
    # e1: horizontal distance between pads (pitch along length - main spacing for 2/3-pin)
    # e2: absolute X position for large pad center (optional override)
    e = float(housing.get('pitch', 0.0))
    e1 = float(housing.get('pitch1', 0.0))
    e2 = float(housing.get('pitch2', 0.0))

    # Place pads based on lead count
    pads = []
    if lead_count == 2:
        # 2-pin DFN: horizontal layout like chip components (pin 1 left, pin 2 right)
        # Use e1 (pitch along length) for horizontal spacing
        spacing = e1 if e1 > 0 else 2.0  # Default 2.0mm if e1 not specified
        x_left = -spacing / 2.0
        x_right = spacing / 2.0
        
        pads.append({'name': '1', 'x': x_left, 'y': 0.0, 'w': small_w, 'h': small_h})
        pads.append({'name': '2', 'x': x_right, 'y': 0.0, 'w': small_w, 'h': small_h})
        
    elif lead_count == 3:
        # 3-pin DFN: pin 1 and 2 on left, pin 3 (large) on right
        # Use e1 for horizontal spacing between left column and right pad
        spacing = e1 if e1 > 0 else 2.0  # Default 2.0mm if e1 not specified
        x_left = -spacing / 2.0
        x_right = spacing / 2.0
        
        # Vertical spacing for pins 1 and 2 (use e if specified, otherwise small spacing)
        vertical_spacing = e if e > 0 else 0.8  # Default 0.8mm vertical spacing
        y_offset = vertical_spacing / 2.0
        
        pads.append({'name': '1', 'x': x_left, 'y': -y_offset, 'w': small_w, 'h': small_h})
        pads.append({'name': '2', 'x': x_left, 'y': y_offset, 'w': small_w, 'h': small_h})
        
        # Large pad (pad 3) on the right side
        tab_w = _resolve_range(housing.get('largePadWidth', {'nom': 1.2}))  # Default 1.2mm if not specified
        tab_l = _resolve_range(housing.get('largePadLength', {'nom': 1.8}))  # Default 1.8mm if not specified
        pads.append({'name': '3', 'x': x_right, 'y': 0.0, 'w': tab_l, 'h': tab_w})
        
    elif lead_count == 4:
        # 4-pin DFN: 2 pads on left, 2 pads on right
        # Use e1 for horizontal spacing, e for vertical spacing
        h_spacing = e1 if e1 > 0 else 2.0  # Default 2.0mm horizontal spacing
        v_spacing = e if e > 0 else 0.8   # Default 0.8mm vertical spacing
        
        x_left = -h_spacing / 2.0
        x_right = h_spacing / 2.0
        y_offset = v_spacing / 2.0
        
        # Corrected pin ordering: pin 2 and 1 should be swapped
        pads.append({'name': '2', 'x': x_left, 'y': y_offset, 'w': small_w, 'h': small_h})   # top left (was pin 1)
        pads.append({'name': '1', 'x': x_left, 'y': -y_offset, 'w': small_w, 'h': small_h})  # bottom left (was pin 2)
        pads.append({'name': '3', 'x': x_right, 'y': y_offset, 'w': small_w, 'h': small_h})   # top right
        pads.append({'name': '4', 'x': x_right, 'y': -y_offset, 'w': small_w, 'h': small_h})  # bottom right

    # Emit pads
    copper.preamble(pattern, element)
    pin_num = 1
    for p in pads:
        pad = {
            'type': 'smd',
            'shape': 'rectangle',
            'x': p['x'],
            'y': p['y'],
            'width': p['w'],
            'height': p['h'],
            'layer': ['topCopper', 'topMask', 'topPaste'],
        }
        name = p.get('name') or str(pin_num)
        pattern.pad(name, pad)
        pin_num += 1 if p.get('name') is None else 0
    copper.postscriptum(pattern)

    # Graphics: follow molded-style fab/silkscreen for DFN
    silkscreen.dfn_molded_style(pattern, housing)
    assembly.dfn_molded_style(pattern, housing)
    courtyard.boundary(pattern, housing, cy)

