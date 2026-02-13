from ..common import assembly, calculator, copper, courtyard
from .chip_array import build as chip_array_build


def build(pattern, element):
    settings = pattern.settings
    housing = element['housing']
    housing['polarized'] = True

    abbr = 'OSC'
    if housing.get('corner-concave'):
        abbr += 'CC'
    elif housing.get('dfn'):
        abbr += 'DFN'
    elif housing.get('side-concave'):
        abbr += 'SC'
    elif housing.get('side-flat'):
        abbr += 'SF'

    if not getattr(pattern, 'name', None):
        if not housing.get('corner-concave'):
            # Non-corner-concave naming (corner-concave will be handled after calculation)
            pitch_h = int(round(housing['pitch'] * 100))
            bl = int(round(housing['bodyLength']['nom'] * 100))
            bw = int(round(housing['bodyWidth']['nom'] * 100))
            bh = int(round(housing['height']['max'] * 100))
            ll = housing.get('leadLength', {}).get('nom', housing.get('leadLength', {}).get('max', housing.get('leadLength', {}).get('min', 0)))
            lw = housing.get('leadWidth', {}).get('nom', housing.get('leadWidth', {}).get('max', housing.get('leadWidth', {}).get('min', 0)))
            if housing.get('side-concave'):
                # OSCSC + Pin Qty + P Pitch _ Body L X W X H + Lead L X W
                pattern.name = f"OSCSC{int(round(housing['leadCount']))}P{pitch_h}_{bl}X{bw}X{bh}{int(round(ll*100))}X{int(round(lw*100))}{settings['densityLevel']}"
            elif housing.get('side-flat'):
                pattern.name = f"OSCSF{int(round(housing['leadCount']))}P{pitch_h}_{bl}X{bw}X{bh}{int(round(ll*100))}X{int(round(lw*100))}{settings['densityLevel']}"
            else:
                # L-lead or C-bend could be added as OSCSL/OSCCL later if needed
                pattern.name = f"OSC{int(round(housing['leadCount']))}P{pitch_h}_{bl}X{bw}X{bh}{int(round(ll*100))}X{int(round(lw*100))}{settings['densityLevel']}"

    if housing.get('corner-concave'):
        print(f"DEBUG oscillator: input housing = {housing}")
        pad_params = calculator.corner_concave(pattern.__dict__, housing)
        print(f"DEBUG oscillator: calculator.corner_concave returned = {pad_params}")
        pad_params['distance'] = pad_params['distance1']
        housing['pitch'] = pad_params['distance2']
        housing['leadCount'] = 4
        print(f"DEBUG oscillator: final pad_params distance = {pad_params['distance']}")
        print(f"DEBUG oscillator: final housing pitch = {housing['pitch']}")
        
        # Generate name using calculated lead dimensions (now available in housing)
        if not getattr(pattern, 'name', None):
            bl = int(round(housing['bodyLength']['nom'] * 100))
            bw = int(round(housing['bodyWidth']['nom'] * 100))
            bh = int(round(housing['height']['max'] * 100))
            # Use the calculated lead dimensions from the corner_concave calculation
            ll = housing['leadLength']['nom']  # Lead length (along body length)
            lw = housing['leadWidth']['nom']   # Lead width (along body width)
            ll_h = int(round(ll * 100))
            lw_h = int(round(lw * 100))
            # Corner concave oscillator naming: OSCC + body dimensions + lead dimensions
            pattern.name = f"OSCC{bl}X{bw}X{bh}L{ll_h}X{lw_h}{settings['densityLevel']}"
            
            # Generate description and tags
            density_names = {'L': 'Least', 'N': 'Nominal', 'M': 'Most'}
            density_name = density_names.get(settings['densityLevel'], 'Unknown')
            
            bl_mm = housing['bodyLength']['nom']
            bw_mm = housing['bodyWidth']['nom']
            bh_mm = housing['height']['max']
            ll_mm = ll
            lw_mm = lw
            
            pattern.description = (
                f"Crystal Oscillator {bl_mm:.1f}mmx{bw_mm:.1f}mm "
                f", Body {bl_mm:.2f}mmx{bw_mm:.2f}mm, "
                f"Height {bh_mm:.2f}mm, Lead {ll_mm:.2f}mmx{lw_mm:.2f}mm, "
                f"{density_name} Density"
            )
            pattern.tags = "oscillator"
            
        pad_params['pad'] = {
            'type': 'smd',
            'shape': 'rectangle',
            'width': pad_params['width'],
            'height': pad_params['height'],
            'layer': ['topCopper', 'topMask', 'topPaste'],
        }
        # Custom numbering for corner concave oscillator: [4, 1, 3, 2]
        # This places pad 4 at bottom-left, 1 at top-left, 3 at top-right, 2 at bottom-right
        pad_params['order'] = 'custom'
        pad_params['custom_numbers'] = [4, 1, 3, 2]
        copper.dual(pattern, element, pad_params)
        from ..common import silkscreen
        silkscreen.corner_concave(pattern, housing)
        assembly.corner_concave(pattern, housing)
        courtyard.boundary(pattern, housing, pad_params['courtyard'])
    elif housing.get('dfn'):
        # Not implemented in CoffeeScript either (TODO)
        raise NotImplementedError('oscillator dfn not implemented')
    else:
        if housing.get('side-concave'):
            housing['concave'] = True
        if housing.get('side-flat'):
            housing['flat'] = True
        chip_array_build(pattern, element)

