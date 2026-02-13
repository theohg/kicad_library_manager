from ..common import two_pin as tp
import math


def _generate_description_and_tags(housing, density_level):
    """Generate description and tags for CAE components"""
    
    # Get dimensions
    bl = housing['bodyLength']['nom'] 
    bw = housing['bodyWidth']['nom']
    h = housing.get('height', {}).get('max', 0)
    ll = housing.get('leadLength', {}).get('nom', 0)
    
    # Map density level to text
    density_map = {'L': 'Least Density', 'N': 'Nominal Density', 'M': 'Most Density'}
    density_text = density_map.get(density_level, 'Nominal Density')
    
    # Generate description in the specified format
    descr = f"Aluminium Electrolytic Capacitor, Length {bl:.2f}mm, Width {bw:.2f}mm, Height {h:.2f}mm, Lead Length {ll:.2f}mm, {density_text}"
    
    # Keywords
    tags = "capacitor electrolytic"
    
    return descr, tags


def build(pattern, element):
    housing = element['housing']
    # Compute leadSpan from leadLength and leadSpace; if only span is provided, back-compute length
    ll = housing.get('leadLength', {})
    ls = housing.get('leadSpace', {})
    span = housing.get('leadSpan')
    if ll and ls:
        # Expect min/nom/max; compute tol as RMS of tolerances
        ll_min, ll_nom, ll_max = ll.get('min'), ll.get('nom'), ll.get('max')
        ls_nom = ls.get('nom')
        
        # Handle case where leadSpace only has nominal value
        if ls_nom is not None and None not in (ll_min, ll_nom, ll_max):
            # Use leadSpace nominal for all min/nom/max if not provided
            ls_min = ls.get('min', ls_nom)
            ls_max = ls.get('max', ls_nom)
            
            tol = math.sqrt((ll_max - ll_min) ** 2 + (ls_max - ls_min) ** 2)
            nom = 2 * ll_nom + ls_nom
            housing['leadSpan'] = {'min': 2 * ll_min + ls_min, 'nom': nom, 'max': 2 * ll_max + ls_max, 'tol': tol}
            print(f"=== CAE LEAD SPAN CALCULATION ===")
            print(f"leadLength: {ll}")
            print(f"leadSpace: {ls}")
            print(f"calculated leadSpan: {housing['leadSpan']}")
    elif span and ls and ('min' in span and 'nom' in span and 'max' in span):
        # Derive leadLength from span and space
        ll_min = (span['min'] - ls.get('max', ls.get('nom', 0))) / 2
        ll_nom = (span['nom'] - ls.get('nom', 0)) / 2
        ll_max = (span['max'] - ls.get('min', ls.get('nom', 0))) / 2
        housing.setdefault('leadLength', {'min': ll_min, 'nom': ll_nom, 'max': ll_max, 'tol': ll_max - ll_min})
    housing['cae'] = True
    # Naming per convention: CAPAE + Base Body Size X Height + L + Lead Length X Width
    if not getattr(pattern, 'name', None):
        bw = int(round(housing['bodyWidth']['nom'] * 100))
        h = int(round(housing['height']['max'] * 100))
        ll = element['housing'].get('leadLength', {}).get('nom', element['housing'].get('leadLength', {}).get('max', element['housing'].get('leadLength', {}).get('min', 0)))
        lw = element['housing'].get('leadWidth', {}).get('nom', element['housing'].get('leadWidth', {}).get('max', element['housing'].get('leadWidth', {}).get('min', 0)))
        pattern.name = f"CAPAE{bw:03d}X{h:03d}L{int(round(ll*100)):03d}X{int(round(lw*100)):03d}{pattern.settings['densityLevel']}"
        
        # Generate description and tags
        descr, tags = _generate_description_and_tags(housing, pattern.settings['densityLevel'])
        pattern.description = descr
        pattern.tags = tags
        
    tp.build(pattern, element)

