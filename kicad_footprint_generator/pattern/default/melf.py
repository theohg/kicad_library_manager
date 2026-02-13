from ..common import two_pin as tp


def build(pattern, element):
    housing = element['housing']
    housing['melf'] = True
    if not getattr(pattern, 'name', None):
        bl = int(round(housing['bodyLength']['nom'] * 100))
        bd = int(round(housing.get('bodyDiameter', {}).get('nom', housing.get('bodyDiameter', 0)) * 100))
        ll = housing.get('leadLength', {}).get('nom', housing.get('leadLength', {}).get('max', housing.get('leadLength', {}).get('min', 0)))
        pattern.name = f"DIOMELF{bl:03d}{bd:03d}{int(round(ll*100)):03d}{pattern.settings['densityLevel']}"
    tp.build(pattern, element)

