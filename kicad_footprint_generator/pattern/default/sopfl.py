from ..common import dual as dual_mod


def build(pattern, element):
    housing = element['housing']
    housing['flatlead'] = True
    housing['polarized'] = True
    dual_mod.build(pattern, element)

