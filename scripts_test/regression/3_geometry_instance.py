# -*- coding: utf-8 -*-

"""This script tests that layout primitives geometries work properly."""

from typing import TYPE_CHECKING, Dict, Any, Set

import yaml

from bag.core import BagProject
from bag.layout.util import BBox
from bag.layout.template import TemplateBase

if TYPE_CHECKING:
    from bag.layout.template import TemplateDB


class TestLayout1(TemplateBase):
    def __init__(self, temp_db, lib_name, params, used_names, **kwargs):
        # type: (TemplateDB, str, Dict[str, Any], Set[str], Any) -> None
        TemplateBase.__init__(self, temp_db, lib_name, params, used_names, **kwargs)

    @classmethod
    def get_params_info(cls):
        return dict()

    def draw_layout(self):
        res = self.grid.resolution

        # simple rectangle
        self.add_rect('M1', BBox(100, 60, 180, 80))

        # a path
        width = 20
        points = [(0, 0), (2000, 0), (3000, 1000), (3000, 3000)]
        self.add_path('M2', width, points, 'truncate', 'round', 'round')

        # set top layer and bounding box so parent can query those
        self.prim_top_layer = 3
        self.prim_bound_box = BBox(0, 0, 400, 400, res, unit_mode=True)


class TestLayout2(TemplateBase):
    def __init__(self, temp_db, lib_name, params, used_names, **kwargs):
        # type: (TemplateDB, str, Dict[str, Any], Set[str], Any) -> None
        TemplateBase.__init__(self, temp_db, lib_name, params, used_names, **kwargs)

    @classmethod
    def get_params_info(cls):
        return dict()

    def draw_layout(self):
        res = self.grid.resolution

        # instantiate Test1
        master = self.template_db.new_template(params={}, temp_cls=TestLayout1)
        self.add_instance(master, 'X0', loc=(-100, -100), orient='MX', unit_mode=True)

        # add via, using BAG's technology DRC calculator
        self.add_via(BBox(0, 0, 100, 100, res, unit_mode=True),
                     'M1', 'M2', 'x')

        # add a primitive pin
        self.add_pin_primitive('mypin', 'M1', BBox(-100, 0, 0, 20, res, unit_mode=True))

        # add a polygon
        points = [(0, 0), (300, 200), (100, 400)]
        self.add_polygon('M3', points)

        # add a blockage
        points = [(-1000, -1000), (-1000, 1000), (1000, 1000), (1000, -1000)]
        self.add_blockage('', 'placement', points)

        # add a boundary
        points = [(-500, -500), (-500, 500), (500, 500), (500, -500)]
        self.add_boundary('PR', points)

        # add a parallel path bus
        widths = [100, 50, 100]
        spaces = [80, 80]
        points = [(0, -3000), (-3000, -3000), (-4000, -2000), (-4000, 0)]
        self.add_path45_bus('M2', points, widths, spaces, start_style='truncate',
                            join_style='round')

        self.prim_top_layer = 3
        self.prim_bound_box = BBox(-10000, -10000, 10000, 10000, res, unit_mode=True)


if __name__ == '__main__':
    with open('specs_test/serdes_ec/regression/3_geometry_instance.yaml', 'r') as f:
        block_specs = yaml.load(f)

    local_dict = locals()
    if 'bprj' not in local_dict:
        print('creating BAG project')
        bprj = BagProject()

    else:
        print('loading BAG project')
        bprj = local_dict['bprj']

    bprj.generate_cell(block_specs, TestLayout2)
