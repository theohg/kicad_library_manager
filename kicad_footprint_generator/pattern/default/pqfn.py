from .qfn import build as _qfn_build


def build(pattern, element):
    housing = element['housing']
    # Ensure QFN path is used with pullback for PQFN
    housing['qfn'] = True
    housing['pqfn'] = True  # Flag to indicate this is PQFN (pullback QFN)
    pb = housing.get('pullBack')
    if pb is not None and not isinstance(pb, dict):
        housing['pullBack'] = {'nom': pb}
    _qfn_build(pattern, element)

