# -*- coding: utf-8 -*-

from typing import Dict

import os
import pkg_resources

from bag.design import Module


yaml_file = pkg_resources.resource_filename(__name__, os.path.join('netlist_info',
                                                                   'qdr_tapx_summer_cell.yaml'))


# noinspection PyPep8Naming
class bag_serdes_ec__qdr_tapx_summer_cell(Module):
    """Module for library bag_serdes_ec cell qdr_tapx_summer_cell.

    Fill in high level description here.
    """

    def __init__(self, bag_config, parent=None, prj=None, **kwargs):
        Module.__init__(self, bag_config, yaml_file, parent=parent, prj=prj, **kwargs)

    @classmethod
    def get_params_info(cls):
        # type: () -> Dict[str, str]
        return dict(
            sum_params='summer tap parameters.',
            lat_params='latch parameters.',
        )

    def design(self, sum_params, lat_params):
        # design instances
        self.instances['XSUM'].design(**sum_params)
        self.instances['XLAT'].design(**lat_params)

        # remove unused pins
        s_pins = self.instances['XSUM'].master.pin_list
        l_pins = self.instances['XLAT'].master.pin_list
        has_casc = has_set = False
        for pin in s_pins:
            if pin.startswith('casc'):
                has_casc = True
                if pin == 'casc':
                    self.rename_pin('casc<1:0>', 'casc')
                    self.reconnect_instance_terminal('XSUM', 'casc', 'casc')

        if not has_casc:
            self.remove_pin('casc<1:0>')

        if not has_set and 'pulse' not in l_pins:
            for name in ('setp', 'setn', 'pulse'):
                self.remove_pin(name)
