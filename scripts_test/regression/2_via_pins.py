# -*- coding: utf-8 -*-

import yaml

from bag.core import BagProject

from bag.layout.template import TemplateBase


class TestLayout(TemplateBase):
    def __init__(self, temp_db, lib_name, params, used_names, **kwargs):
        TemplateBase.__init__(self, temp_db, lib_name, params, used_names, **kwargs)

    @classmethod
    def get_params_info(cls):
        return {}

    def draw_layout(self):
        # Metal 4 is horizontal, Metal 5 is vertical
        hm_layer = 4
        vm_layer = 5

        warr1 = self.add_wires(hm_layer, 0, 0, 400)
        warr2 = self.add_wires(vm_layer, 2, 0, 400)
        self.connect_to_track_wires(warr1, warr2)

        warr3 = self.add_wires(hm_layer, 10, 0, 400, num=3, pitch=2)
        self.connect_to_track_wires(warr2, warr3)

        self.add_pin('foo', warr2)


if __name__ == '__main__':
    with open('specs_test/serdes_ec/regression/2_via_pins.yaml', 'r') as f:
        block_specs = yaml.load(f)

    local_dict = locals()
    if 'bprj' not in local_dict:
        print('creating BAG project')
        bprj = BagProject()

    else:
        print('loading BAG project')
        bprj = local_dict['bprj']

    bprj.generate_cell(block_specs, TestLayout)
