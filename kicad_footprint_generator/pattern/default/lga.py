from ..common import grid_array as grid_array_mod


def build(pattern, element):
    housing = element['housing']
    housing['lga'] = True
    grid_array_mod.build(pattern, element)

