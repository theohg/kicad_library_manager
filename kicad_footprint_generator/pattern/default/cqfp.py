from ..common import quad as quad_mod


def build(pattern, element):
    housing = element['housing']
    housing['cqfp'] = True
    quad_mod.build(pattern, element)

