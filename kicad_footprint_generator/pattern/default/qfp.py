from ..common import quad as quad_mod


def build(pattern, element):
    housing = element['housing']
    housing['qfp'] = True
    
    # Generate description and tags for QFP
    if not hasattr(pattern, 'description'):
        pin_count = (housing.get('rowCount', 0) + housing.get('columnCount', 0)) * 2
        pitch = housing.get('pitch', 0.8)
        bl = housing.get('bodyLength', {}).get('nom', 0)
        bw = housing.get('bodyWidth', {}).get('nom', 0) 
        h = housing.get('height', {}).get('max', 0)
        ll = housing.get('leadLength', {}).get('nom', 0)
        lw = housing.get('leadWidth', {}).get('nom', 0)
        
        density_desc = {
            'L': 'Least',
            'N': 'Nominal', 
            'M': 'Most'
        }.get(pattern.settings.get('densityLevel', 'N'), 'Nominal')
        
        pattern.description = (f"Quad Flat Package (QFP), {pin_count} Pin "
                             f"({pitch:.2f}mm pitch), Body {bl:.2f}mm x {bw:.2f}mm x {h:.2f}mm, "
                             f"Lead {ll:.2f}mm x {lw:.2f}mm, {density_desc} Density")
        pattern.tags = "qfp ic"
    
    # Naming for QFP/CQFP handled in common.quad.build
    quad_mod.build(pattern, element)

