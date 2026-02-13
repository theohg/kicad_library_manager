from ..common import dual as dual_mod


def build(pattern, element):
    housing = element['housing']
    housing.setdefault('pitch', 1.27)
    housing['soic'] = True
    housing['polarized'] = True
    
    # Generate description and tags for SOIC
    if not hasattr(pattern, 'description'):
        pin_count = housing.get('leadCount', 0)
        pitch = housing.get('pitch', 1.27)
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
        
        pattern.description = (f"Small Outline Integrated Circuit (SOIC), {pin_count} Pin "
                             f"({pitch:.2f}mm pitch), Body {bl:.2f}mm x {bw:.2f}mm x {h:.2f}mm, "
                             f"Lead {ll:.2f}mm x {lw:.2f}mm, {density_desc} Density")
        pattern.tags = "soic ic"
    
    # Naming handled in common.dual.build
    dual_mod.build(pattern, element)

