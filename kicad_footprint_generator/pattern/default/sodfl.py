from ..common import two_pin as tp


def build(pattern, element):
    housing = element['housing']
    housing['sodfl'] = True
    # Make SODFL behave like chip components (90° CCW rotation, pin 1 on left)
    housing['chip'] = True
    # SODFL is polarized (for pin 1 dot indicator)
    housing['polarized'] = True
    
    # Implement new naming scheme and description
    if not getattr(pattern, 'name', None):
        # Extract dimensions for naming
        ls = int(round(housing['leadSpan']['nom'] * 100))
        bw = int(round(housing['bodyWidth']['nom'] * 100))
        bh = int(round(housing.get('height', {}).get('max', 0) * 100))
        ll = housing.get('leadLength', {}).get('nom', (housing.get('leadLength', {}).get('min', 0) + housing.get('leadLength', {}).get('max', 0)) / 2)
        lw = housing.get('leadWidth', {}).get('nom', (housing.get('leadWidth', {}).get('min', 0) + housing.get('leadWidth', {}).get('max', 0)) / 2)
        
        # SODFL naming: SODFL + LeadSpan X BodyWidth X Height + L LeadLength X Width
        pattern.name = f"SODFL{ls:03d}X{bw:03d}X{bh:03d}L{int(round(ll*100)):03d}X{int(round(lw*100)):03d}{pattern.settings['densityLevel']}"
        
        # Generate description and tags
        density_desc = {'L': 'Least', 'N': 'Nominal', 'M': 'Most'}[pattern.settings['densityLevel']]
        
        ls_mm = housing['leadSpan']['nom']
        bw_mm = housing['bodyWidth']['nom']
        bh_mm = housing.get('height', {}).get('max', 0)
        ll_mm = ll
        lw_mm = lw
        
        pattern.description = (
            f"Small Outline Diode, Flat Lead (SODFL), "
            f"Lead Span {ls_mm:.2f}mm, "
            f"Body {bw_mm:.2f}mm x {bh_mm:.2f}mm, "
            f"Lead {ll_mm:.2f}mm x {lw_mm:.2f}mm, "
            f"{density_desc} Density"
        )
        pattern.tags = "diode"
    
    tp.build(pattern, element)

