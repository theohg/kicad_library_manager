from ..common import quad as quad_mod


def build(pattern, element):
    housing = element['housing']
    housing['qfn'] = True
    # Naming for QFN/PQFN handled in common.quad.build
    quad_mod.build(pattern, element)

