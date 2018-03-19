# -*- coding: utf-8 -*-

from typing import Dict

import os
import pkg_resources

from bag.design import Module


yaml_file = pkg_resources.resource_filename(__name__, os.path.join('netlist_info',
                                                                   'qdr_tap1_summer.yaml'))


# noinspection PyPep8Naming
class bag_serdes_ec__qdr_tap1_summer(Module):
    """Module for library bag_serdes_ec cell qdr_tap1_summer.

    Fill in high level description here.
    """

    def __init__(self, bag_config, parent=None, prj=None, **kwargs):
        Module.__init__(self, bag_config, yaml_file, parent=parent, prj=prj, **kwargs)

    @classmethod
    def get_params_info(cls):
        # type: () -> Dict[str, str]
        return dict(
            sum_params='summer row parameters.',
            lat_params='latch row parameters.',
        )

    def design(self, sum_params, lat_params):
        self.instances['XSUM'].design(**sum_params)
        self.instances['XLAT'].design(**lat_params)

        sum_pins = self.instances['XSUM'].master.pin_list
        lat_pins = self.instances['XLAT'].master.pin_list

        # delete divider pins if they are not there.
        if 'div' not in lat_pins:
            for name in ['div', 'divb', 'en_div', 'scan_div']:
                self.remove_pin(name)
        # delete pulse pins if they are not there
        if 'pulse_out' not in lat_pins:
            self.remove_pin('pulse_out')
        # delete initialization pins if they are not needed
        if 'pulse' not in sum_pins and 'pulse_in' not in lat_pins:
            for name in ('setp', 'setn', 'pulse_in'):
                self.remove_pin(name)
