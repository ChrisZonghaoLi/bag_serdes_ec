# -*- coding: utf-8 -*-

from typing import Dict

import os
import pkg_resources

from bag.design import Module


yaml_file = pkg_resources.resource_filename(__name__, os.path.join('netlist_info',
                                                                   'qdr_tap1_latch_row.yaml'))


# noinspection PyPep8Naming
class bag_serdes_ec__qdr_tap1_latch_row(Module):
    """Module for library bag_serdes_ec cell qdr_tap1_latch_row.

    Fill in high level description here.
    """

    def __init__(self, bag_config, parent=None, prj=None, **kwargs):
        Module.__init__(self, bag_config, yaml_file, parent=parent, prj=prj, **kwargs)
        self.has_div = False
        self.has_pul = False
        self.has_re = False
        self.has_set = False
        self.re_dummy = False

    @classmethod
    def get_params_info(cls):
        # type: () -> Dict[str, str]
        return dict(
            div_pos_edge='True if the divider block triggers on positive edge.',
            lat_params='latch parameters.',
            div_params='divider parameters.',
            pul_params='pulse generation parameters.',
            re_params='enable retimer parameters.',
            re_dummy='True if the enable retimer is a dummy cell.',
        )

    def design(self, div_pos_edge, lat_params, div_params, pul_params, re_params, re_dummy):
        # design latch
        self.instances['XLAT'].design(**lat_params)
        lat_master = self.instances['XLAT'].master
        if lat_master.has_set:
            self.has_set = True
        else:
            for name in ('setp', 'setn', 'pulse_in'):
                self.remove_pin(name)

        # design divider
        if div_params is None:
            self.delete_instance('XDIV')
            if re_params is None or re_dummy:
                self.remove_pin('en_div')
            for name in ('scan_div', 'div', 'divb'):
                self.remove_pin(name)
        else:
            self.has_div = True
            self.instances['XDIV'].design(**div_params)
            if not div_pos_edge:
                self.reconnect_instance_terminal('XDIV', 'clk', 'clkn')

        # design pulse generation
        if pul_params is None:
            self.delete_instance('XPULSE')
            for name in ('en0', 'en3', 'pulse_out'):
                self.remove_pin(name)
        else:
            self.has_pul = True
            self.instances['XPULSE'].design(**pul_params)

        # design enable retimer
        if re_params is None:
            self.delete_instance('XRE')
            self.remove_pin('en_div3')
            self.remove_pin('en_div2')
        else:
            self.has_re = True
            self.instances['XRE'].design(**re_params)
            if re_dummy:
                self.re_dummy = True
                self.remove_pin('en_div3')
                self.remove_pin('en_div2')
                self.reconnect_instance_terminal('XRE', 'in', 'VSS')
                self.reconnect_instance_terminal('XRE', 'clkp', 'VSS')
                self.reconnect_instance_terminal('XRE', 'clkn', 'VDD')
