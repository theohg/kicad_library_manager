from ..common import two_pin as tp


def _generate_description_and_tags(comp_type, housing, density_level):
    """Generate description and tags for chip components"""
    
    # Component type to description mapping
    type_map = {
        'CAPC': ('Capacitor', 'capacitor'),
        'RESC': ('Resistor', 'resistor'), 
        'LEDC': ('LED', 'led'),
        'DIOC': ('Diode', 'diode'),
        'BEADC': ('Ferrite Bead', 'ferrite_bead'),
        'FUSC': ('Fuse', 'fuse'),
        'THRMC': ('Thermistor', 'thermistor'),
        'VARC': ('Varistor', 'varistor'),
    }
    
    comp_desc, tag = type_map.get(comp_type, ('Component', 'component'))
    
    # Get dimensions
    bl = housing['bodyLength']['nom']
    bw = housing['bodyWidth']['nom'] 
    h = housing.get('height', {}).get('max', 0)
    ll = housing.get('leadLength', {}).get('nom', 0)
    
    # Standard chip size mapping (length x width in mm to imperial size)
    size_map = {
        (0.4, 0.2): '01005',
        (0.6, 0.3): '0201', 
        (1.0, 0.5): '0402',
        (1.6, 0.8): '0603',
        (2.0, 1.25): '0805',
        (3.2, 1.6): '1206',
        (3.2, 2.5): '1210',
        (4.5, 3.2): '1812',
        (5.0, 2.5): '2010',
        (6.4, 3.2): '2512',
    }
    
    # Find closest standard size
    std_size = None
    min_diff = float('inf')
    for (std_l, std_w), size in size_map.items():
        diff = abs(bl - std_l) + abs(bw - std_w)
        if diff < min_diff:
            min_diff = diff
            std_size = size
    
    # Convert to imperial (inches * 100 for standard notation)
    bl_imp = int(round(bl / 25.4 * 100))
    bw_imp = int(round(bw / 25.4 * 100))
    
    # Convert to metric notation (mm * 10 for 4-digit format)
    # Example: 1.6mm x 0.8mm becomes 1608 (16 x 08)
    bl_metric = int(round(bl * 10))
    bw_metric = int(round(bw * 10))
    
    # Density level description
    density_desc = {
        'L': 'Least',
        'N': 'Nominal', 
        'M': 'Most'
    }.get(density_level, 'Nominal')
    
    # Generate description
    descr = f"{comp_desc} {std_size or f'{bl_imp:02d}{bw_imp:02d}'} ({bl_metric:02d}{bw_metric:02d} Metric), "
    descr += f"Length {bl:.2f}mm, Width {bw:.2f}mm, Height {h:.2f}mm, "
    descr += f"Lead Length {ll:.2f}mm, {density_desc} Density"
    
    return descr, tag


def build(pattern, element):
    housing = element['housing']
    housing['chip'] = True
    # Naming per convention: use component type selector
    if not getattr(pattern, 'name', None):
        comp_type = element['housing'].get('componentType', 'CAPC')
        bl = int(round(housing['bodyLength']['nom'] * 100))
        bw = int(round(housing['bodyWidth']['nom'] * 100))
        h = int(round(housing.get('height', {}).get('max', 0) * 100))
        # Use nominal lead length for naming (strictly nom per request)
        ll = element['housing'].get('leadLength', {}).get('nom', 0)
        bls = f"{bl:03d}"; bws = f"{bw:03d}"; hs = f"{h:03d}"; lls = f"{int(round(ll*100)):03d}"
        # Chip naming per request: <CAT>{L}X{W}X{H}L{LeadLen}
        pattern.name = f"{comp_type}{bls}X{bws}X{hs}L{lls}{pattern.settings['densityLevel']}"
        
        # Generate description and tags
        descr, tags = _generate_description_and_tags(comp_type, housing, pattern.settings['densityLevel'])
        pattern.description = descr
        pattern.tags = tags
        
    tp.build(pattern, element)

