# -*- coding: utf-8 -*-

from typing import Dict

import os
import pkg_resources

from bag.design import Module


yaml_file = pkg_resources.resource_filename(__name__, os.path.join('netlist_info',
                                                                   'qdr_tap1_main_row.yaml'))


# noinspection PyPep8Naming
class bag_serdes_ec__qdr_tap1_main_row(Module):
    """Module for library bag_serdes_ec cell qdr_tap1_main_row.

    Fill in high level description here.
    """

    def __init__(self, bag_config, parent=None, prj=None, **kwargs):
        Module.__init__(self, bag_config, yaml_file, parent=parent, prj=prj, **kwargs)

    @classmethod
    def get_params_info(cls):
        # type: () -> Dict[str, str]
        return dict(
            div_pos_edge='True if divider is running on positive edge of clock.',
            main_params='Main integrating amplifier parameters.',
            div_params='clock divider parameters.  None to disable.'
        )

    def design(self, div_pos_edge, main_params, div_params):
        if div_params is None:
            self.delete_instance('XDIV')
            for name in ['div', 'divb', 'scan_div', 'en_div']:
                self.remove_pin(name)
        else:
            self.instances['XDIV'].design(**div_params)
            clk_name = 'clkp' if div_pos_edge else 'clkn'
            self.reconnect_instance_terminal('XDIV', 'clk', clk_name)

        self.instances['XMAIN'].design(**main_params)
