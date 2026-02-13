from ..common import dual as dual_mod, mask, copper, silkscreen, assembly, courtyard, calculator


def build(pattern, element):
    housing = element['housing']
    housing['sop'] = True
    housing['polarized'] = True
    settings = pattern.settings
    
    # Normalize thermal pad dimensions
    thermal_pad_width = 0
    thermal_pad_length = 0
    if 'tabWidth' in housing and housing['tabWidth']['nom'] > 0:
        thermal_pad_width = housing['tabWidth']['nom']
        thermal_pad_length = housing['tabLength']['nom']
    
    # Calculate pad parameters
    pad_params = calculator.dual(pattern.__dict__, housing, 'sop')
    
    # Generate pin layout - dual package with thermal pad support
    pin_count = int(housing['leadCount'])
    pins_per_side = pin_count // 2
    pitch = housing['pitch']
    
    # Create pad template
    pad = {
        'type': 'smd',
        'shape': 'roundrect',
        'width': pad_params['width'],
        'height': pad_params['height'],
        'layer': ['topCopper', 'topMask', 'topPaste'],
        'roundrect_rratio': min(0.25, 0.1 / min(pad_params['width'], pad_params['height']))
    }
    
    # Generate left side pins (1 to pins_per_side)
    pad_distance = pad_params['distance']
    
    y = -(pins_per_side - 1) * pitch / 2
    for i in range(pins_per_side):
        pin_number = i + 1
        pad_left = dict(pad)
        pad_left['x'] = -pad_distance / 2
        pad_left['y'] = y
        pattern.pad(pin_number, pad_left)
        y += pitch  # Move down for next pin
    
    # Generate right side pins (pins_per_side+1 to pin_count)
    y = -(pins_per_side - 1) * pitch / 2
    for i in range(pins_per_side):
        pin_number = pin_count - i  # Count down from highest pin
        pad_right = dict(pad)
        pad_right['x'] = pad_distance / 2
        pad_right['y'] = y
        pattern.pad(pin_number, pad_right)
        y += pitch  # Move down for next pin
    
    # Add thermal pad if specified
    thermal_suffix = ""
    if thermal_pad_width > 0 and thermal_pad_length > 0:
        pad_thermal = {
            'type': 'smd',
            'shape': 'roundrect',
            'x': 0,
            'y': 0,
            'width': thermal_pad_width,
            'height': thermal_pad_length,
            'layer': ['topCopper', 'topMask', 'topPaste'],
            'roundrect_rratio': min(0.25, 0.1 / min(thermal_pad_width, thermal_pad_length))
        }
        pattern.pad(pin_count + 1, pad_thermal)
        # Thermal pad suffix for naming
        tpw = int(round(thermal_pad_width * 100))
        tpl = int(round(thermal_pad_length * 100))
        thermal_suffix = f"T{tpl:03d}X{tpw:03d}"
    
    # Naming convention: SOP+PinQty+PPitch_BodyLength X LeadSpan X BodyHeight + L LeadLength X Width + T ThermalPadLength X Width
    pitch_h = int(round(pitch * 100))
    bl = int(round(housing['bodyLength']['nom'] * 100))
    lead_span = housing['leadSpan']['nom']
    ls = int(round(lead_span * 100))
    bh = int(round(housing['height']['max'] * 100))
    ll = int(round(housing['leadLength']['nom'] * 100))
    lw = int(round(housing['leadWidth']['nom'] * 100))
    
    # Use actual pin count (not including thermal pad)
    actual_pin_count = pin_count
    pattern.name = f"SOP{actual_pin_count}P{pitch_h:03d}_{bl:03d}X{ls:03d}X{bh:03d}L{ll:03d}X{lw:03d}{thermal_suffix}{settings['densityLevel']}"
    
    # Generate description
    density_desc = {"L": "Least", "N": "Nominal", "M": "Most"}[settings['densityLevel']]
    body_l = housing['bodyLength']['nom']
    body_w = housing['bodyWidth']['nom']
    h = housing['height']['max']
    ll_desc = housing['leadLength']['nom']
    lw_desc = housing['leadWidth']['nom']
    
    pattern.description = (f"Small Outline Package (SOP), {actual_pin_count} Pin "
                          f"({pitch:.2f}mm pitch), Body {body_l:.2f}mm x {body_w:.2f}mm x {h:.2f}mm, "
                          f"Lead {ll_desc:.2f}mm x {lw_desc:.2f}mm")
    
    if thermal_pad_width > 0:
        pattern.description += f", Thermal Pad {thermal_pad_length:.2f}mm x {thermal_pad_width:.2f}mm"
    
    pattern.description += f", {density_desc} Density"
    pattern.tags = "sop"
    
    # Add layers
    copper.mask(pattern)
    silkscreen.dual(pattern, housing)
    assembly.sop(pattern, housing)
    courtyard.boundary_flex(pattern, housing, pad_params['courtyard'])
    mask.dual(pattern, housing)

