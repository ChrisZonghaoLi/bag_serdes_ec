# -*- coding: utf-8 -*-

from typing import Dict

import os
import pkg_resources

from bag.design import Module


yaml_file = pkg_resources.resource_filename(__name__, os.path.join('netlist_info',
                                                                   'qdr_tapx_summer_last.yaml'))


# noinspection PyPep8Naming
class bag_serdes_ec__qdr_tapx_summer_last(Module):
    """Module for library bag_serdes_ec cell qdr_tapx_summer_last.

    Fill in high level description here.
    """

    def __init__(self, bag_config, parent=None, prj=None, **kwargs):
        Module.__init__(self, bag_config, yaml_file, parent=parent, prj=prj, **kwargs)

    @classmethod
    def get_params_info(cls):
        # type: () -> Dict[str, str]
        return dict(
            div_pos_edge='True if the divider block triggers on positive edge of latch.',
            sum_params='summer tap parameters.',
            div_params='divider parameters.  None to disable',
            pul_params='pulse generation parameters.  None to disable',
        )

    def design(self, div_pos_edge, sum_params, div_params, pul_params):
        # design summer
        self.instances['XSUM'].design(**sum_params)
        if 'pulse' not in self.instances['XSUM'].master.pin_list:
            # delete set pins
            for name in ('setp', 'setn', 'pulse_in'):
                self.remove_pin(name)

        # design divider
        if div_params is None:
            self.delete_instance('XDIV')
            for name in ('en_div', 'scan_div', 'div', 'divb'):
                self.remove_pin(name)
        else:
            self.instances['XDIV'].design(**div_params)
            if not div_pos_edge:
                self.reconnect_instance_terminal('XDIV', 'clk', 'clkn')

        # design pulse generation
        if pul_params is None:
            self.delete_instance('XPULSE')
            for name in ('en0', 'en3', 'pulse_out'):
                self.remove_pin(name)
        else:
            self.instances['XPULSE'].design(**pul_params)
