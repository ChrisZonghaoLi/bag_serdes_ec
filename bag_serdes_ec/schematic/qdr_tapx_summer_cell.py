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
        self.has_set = False
        self.has_casc = False
        self.has_but = False

    @classmethod
    def get_params_info(cls):
        # type: () -> Dict[str, str]
        return dict(
            sum_params='summer tap parameters.',
            lat_params='latch parameters.',
        )

    def design(self, sum_params, lat_params):
        s_inst = self.instances['XSUM']
        l_inst = self.instances['XLAT']
        # design instances
        s_inst.design(**sum_params)
        l_inst.design(**lat_params)

        # remove unused pins
        s_master = s_inst.master
        if s_master.has_but:
            self.has_but = True
        else:
            self.has_but = False
            if s_master.has_casc:
                self.rename_pin('casc<1:0>', 'casc')
                self.reconnect_instance_terminal('XSUM', 'casc', 'casc')
                self.has_casc = True
            else:
                self.remove_pin('casc<1:0>')
                self.has_casc = False

        if not l_inst.master.has_en2:
            self.reconnect_instance_terminal('XLAT', 'en<3>', 'en<3>')

        # for now has_set is always False
        for name in ('setp', 'setn', 'pulse'):
            self.remove_pin(name)
