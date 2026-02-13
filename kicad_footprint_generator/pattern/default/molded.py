from ..common import two_pin as tp


def _get_component_prefix_and_details(comp_type):
    """Get component prefix and description details based on component type"""
    component_map = {
        'capacitor': ('CAPM', 'Capacitor, Molded', 'capacitor'),
        'capacitor_polarized': ('CAPPM', 'Capacitor, Polarized, Molded', 'capacitor polarized'),
        'diode': ('DIOM', 'Diode, Molded', 'diode'),
        'diode_non_polarized': ('DIONM', 'Diode, Non-polarized, Molded', 'diode non-polarized'),
        'fuse': ('FUSM', 'Fuse, Molded', 'fuse'),
        'inductor': ('INDM', 'Inductor, Molded', 'inductor'),
        'inductor_precision': ('INDPM', 'Inductor, Precision, Molded', 'inductor precision'),
        'led': ('LEDM', 'LED, Molded', 'led'),
        'resistor': ('RESM', 'Resistor, Molded', 'resistor')
    }
    return component_map.get(comp_type, ('DIOM', 'Diode, Molded', 'diode'))  # Default to diode


def build(pattern, element):
    housing = element['housing']
    housing['molded'] = True
    # Make molded components behave like chip components (90° CCW rotation, pin 1 on left)
    housing['chip'] = True
    
    if not getattr(pattern, 'name', None):
        # Get component type from housing
        comp_type = housing.get('componentType', 'diode')
        prefix, description_name, tag = _get_component_prefix_and_details(comp_type)
        
        # Extract dimensions for naming
        ls = int(round(housing['leadSpan']['nom'] * 100))
        bw = int(round(housing['bodyWidth']['nom'] * 100))
        bh = int(round(housing.get('height', {}).get('max', 0) * 100))
        ll = housing.get('leadLength', {}).get('nom', housing.get('leadLength', {}).get('max', housing.get('leadLength', {}).get('min', 0)))
        lw = housing.get('leadWidth', {}).get('nom', housing.get('leadWidth', {}).get('max', housing.get('leadWidth', {}).get('min', 0)))
        
        # Molded component naming: PREFIX + LeadSpan X BodyWidth X Height + L LeadLength X LeadWidth
        pattern.name = f"{prefix}{ls:03d}X{bw:03d}X{bh:03d}L{int(round(ll*100)):03d}X{int(round(lw*100)):03d}{pattern.settings['densityLevel']}"
        
        # Generate description and tags
        density_desc = {'L': 'Least', 'N': 'Nominal', 'M': 'Most'}[pattern.settings['densityLevel']]
        
        ls_mm = housing['leadSpan']['nom']
        bw_mm = housing['bodyWidth']['nom']
        bh_mm = housing.get('height', {}).get('max', 0)
        ll_mm = ll
        lw_mm = lw
        
        pattern.description = (
            f"{description_name}, Lead Span {ls_mm:.2f}mm, "
            f"Body {bw_mm:.2f}mm x {bh_mm:.2f}mm, "
            f"Lead {ll_mm:.2f}mm x {lw_mm:.2f}mm, "
            f"{density_desc} Density"
        )
        pattern.tags = tag
    
    tp.build(pattern, element)

