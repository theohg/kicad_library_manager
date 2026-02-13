from ..common import two_pin as tp


def build(pattern, element):
    housing = element['housing']
    housing['sod'] = True
    if not getattr(pattern, 'name', None):
        ls = int(round(housing['leadSpan']['nom'] * 100))
        bw = int(round(housing['bodyWidth']['nom'] * 100))
        bh = int(round(housing.get('height', {}).get('max', 0) * 100))
        ll = housing.get('leadLength', {}).get('nom', housing.get('leadLength', {}).get('max', housing.get('leadLength', {}).get('min', 0)))
        lw = housing.get('leadWidth', {}).get('nom', housing.get('leadWidth', {}).get('max', housing.get('leadWidth', {}).get('min', 0)))
        pattern.name = f"SOD{ls:03d}X{bw:03d}X{bh:03d}{int(round(ll*100)):03d}X{int(round(lw*100)):03d}{pattern.settings['densityLevel']}"
    tp.build(pattern, element)

