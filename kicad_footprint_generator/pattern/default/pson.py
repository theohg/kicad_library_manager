from .son import build as _son_build


def build(pattern, element):
    housing = element['housing']
    # Ensure pullBack is a dict with 'nom' if provided as scalar
    pb = housing.get('pullBack')
    if pb is not None and not isinstance(pb, dict):
        housing['pullBack'] = {'nom': pb}
    _son_build(pattern, element)

