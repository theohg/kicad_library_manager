from ..common import assembly, calculator, copper, courtyard, silkscreen


def build(pattern, element):
    housing = element['housing']
    housing['polarized'] = True
    housing['son'] = True  # Flag for SON-specific silkscreen
    settings = pattern.settings
    lead_count = housing['leadCount']
    has_tab = ('tabWidth' in housing) and ('tabLength' in housing)
    if has_tab:
        lead_count += 1

    if not getattr(pattern, 'name', None):
        # SON naming: SON+PinQty.+P Pitch_BodyLength X Width X Height+L LeadLength X Width+T ThermalPadLength X Width
        pitch_h = int(round(housing['pitch'] * 100))
        bl = int(round(housing['bodyLength']['nom'] * 100))
        bw = int(round(housing['bodyWidth']['nom'] * 100))
        bh = int(round(housing['height']['max'] * 100))
        
        # Get lead dimensions (use nominal values, compute from min/max if not available)
        def get_nominal(param_dict):
            if isinstance(param_dict, dict):
                if 'nom' in param_dict:
                    return param_dict['nom']
                elif 'min' in param_dict and 'max' in param_dict:
                    # Compute nominal as average of min/max
                    return (param_dict['min'] + param_dict['max']) / 2
                else:
                    return param_dict.get('max', param_dict.get('min', 0))
            return param_dict or 0
        
        ll = get_nominal(housing.get('leadLength', {}))
        lw = get_nominal(housing.get('leadWidth', {}))
        
        def _nom(v):
            if isinstance(v, dict):
                return v.get('nom', v.get('max', v.get('min', 0)))
            return v
        
        # Build name components with proper zero-padding to 3 digits
        # Use actual leadCount from housing, not the modified lead_count variable
        actual_pin_count = housing['leadCount']
        name_parts = [
            f"SON{actual_pin_count}",
            f"P{pitch_h:03d}",  # 3-digit pitch
            f"_{bl:03d}X{bw:03d}X{bh:03d}",  # Body dimensions
            f"L{int(round(ll*100)):03d}X{int(round(lw*100)):03d}"  # Lead dimensions
        ]
        
        # Add thermal pad if present
        tw = housing.get('tabWidth')
        tl = housing.get('tabLength')
        if (_nom(tw) or 0) > 0 and (_nom(tl) or 0) > 0:
            name_parts.append(f"T{int(round(_nom(tl)*100)):03d}X{int(round(_nom(tw)*100)):03d}")
        
        pattern.name = "".join(name_parts) + settings['densityLevel']
        
        # Generate description and tags
        pitch = housing['pitch']
        pin_count = housing['leadCount']
        bl = housing['bodyLength']['nom']
        bw = housing['bodyWidth']['nom']
        h = housing['height']['max']
        density_desc = {'L': 'Least', 'N': 'Nominal', 'M': 'Most'}[settings['densityLevel']]
        
        thermal_desc = ""
        if (_nom(tw) or 0) > 0 and (_nom(tl) or 0) > 0:
            thermal_desc = f", Thermal Pad {_nom(tl):.2f}mm x {_nom(tw):.2f}mm"
        
        pattern.description = (f"Small Outline No-Lead (SON), {pin_count} Pin "
                             f"({pitch:.2f}mm pitch), Body {bl:.2f}mm x {bw:.2f}mm x {h:.2f}mm, "
                             f"Lead {ll:.2f}mm x {lw:.2f}mm{thermal_desc}, {density_desc} Density")
        pattern.tags = "son ic"

    pad_params = calculator.son(pattern.__dict__, housing)
    pad_params.update({'pitch': housing['pitch'], 'count': housing['leadCount'], 'order': 'round'})
    pad_params['pad'] = {
        'type': 'smd',
        'shape': 'rectangle',
        'width': pad_params['width'],
        'height': pad_params['height'],
        'layer': ['topCopper', 'topMask', 'topPaste'],
    }

    copper.dual(pattern, element, pad_params)

    if 'width1' in pad_params:
        # adjust first pad width and x offset
        first_key = sorted(pattern.pads.keys(), key=lambda k: int(k) if k.isdigit() else k)[0]
        first_pad = pattern.pads[first_key]
        width1 = pad_params['width1']
        dx = (width1 - first_pad.width) / 2
        first_pad.x += dx
        first_pad.width = width1

    silkscreen.dual(pattern, housing)
    assembly.son(pattern, housing)
    courtyard.dual(pattern, housing, pad_params['courtyard'])
    copper.tab(pattern, element)

