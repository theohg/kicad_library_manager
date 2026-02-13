from ..common import mask, copper, silkscreen, assembly, courtyard, calculator


def build(pattern, element):
    housing = element['housing']
    housing['soj'] = True
    housing['polarized'] = True
    settings = pattern.settings
    
    # SOJ doesn't support thermal pads (like SOP but without thermal pad logic)
    
    if not getattr(pattern, 'name', None):
        # SOJ naming: SOJ + PinQty + P + Pitch_BodyLength X LeadSpan X Height + L + LeadWidth
        pin_count = int(housing['leadCount'])
        pitch_h = int(round(housing['pitch'] * 100))
        bl = int(round(housing['bodyLength']['nom'] * 100))
        ls = int(round(housing['leadSpan']['nom'] * 100))
        bh = int(round(housing['height']['max'] * 100))
        
        # Get lead width (use nominal, calculate from min/max if needed)
        lw = housing.get('leadWidth', {}).get('nom')
        if lw is None:
            lw_min = housing.get('leadWidth', {}).get('min', 0)
            lw_max = housing.get('leadWidth', {}).get('max', 0)
            lw = (lw_min + lw_max) / 2 if lw_max > 0 else 0
        lw_h = int(round(lw * 100))
        
        pattern.name = f"SOJ{pin_count}P{pitch_h:03d}_{bl:03d}X{ls:03d}X{bh:03d}L{lw_h:03d}{settings['densityLevel']}"
        
        # Generate description
        density_desc = {"L": "Least", "N": "Nominal", "M": "Most"}[settings['densityLevel']]
        pitch = housing['pitch']
        body_l = housing['bodyLength']['nom']
        body_w = housing['bodyWidth']['nom']
        h = housing['height']['max']
        lead_span = housing['leadSpan']['nom']
        
        pattern.description = (f"Small Outline J-Lead (SOJ), {pin_count} Pin "
                              f"({pitch:.2f}mm pitch), Body {body_l:.2f}mm x {body_w:.2f}mm x {h:.2f}mm, "
                              f"Lead Span {lead_span:.2f}mm, Lead Width {lw:.2f}mm, {density_desc} Density")
        pattern.tags = "soj"
    
    # Calculate pad parameters using custom SOJ calculator
    pad_params = calculator.soj(pattern.__dict__, housing)
    
    # Generate pin layout - dual package (similar to SOP but without thermal pad)
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
    
    # Apply SOP-like silkscreen, assembly, etc.
    copper.mask(pattern)
    silkscreen.dual(pattern, housing)  # Use same silkscreen as SOP (SOJ gets SOP treatment)
    assembly.sop(pattern, housing)  # Use same assembly as SOP
    courtyard.dual(pattern, housing, pad_params['courtyard'])
    mask.dual(pattern, housing)

