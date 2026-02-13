from ..common import grid_array as grid_array_mod


def build(pattern, element):
    housing = element['housing']
    housing['bga'] = True
    
    # Generate description and tags for BGA
    if not hasattr(pattern, 'description'):
        pin_count = housing.get('pinCount', len(element.get('pins', {})))
        pitch = housing.get('pitch', 1.0)
        bl = housing.get('bodyLength', {}).get('nom', 0)
        bw = housing.get('bodyWidth', {}).get('nom', 0) 
        h = housing.get('height', {}).get('max', 0)
        ball_dia = housing.get('ballDiameter', {}).get('nom', 0)
        
        density_desc = {
            'L': 'Least',
            'N': 'Nominal', 
            'M': 'Most'
        }.get(pattern.settings.get('densityLevel', 'N'), 'Nominal')
        
        pattern.description = (f"Ball Grid Array (BGA), {pin_count} Pin "
                             f"({pitch:.2f}mm pitch), Body {bl:.2f}mm x {bw:.2f}mm x {h:.2f}mm, "
                             f"Ball Diameter {ball_dia:.2f}mm, IPC-7351 {density_desc} Density")
        pattern.tags = "bga ic"
    
    grid_array_mod.build(pattern, element)

