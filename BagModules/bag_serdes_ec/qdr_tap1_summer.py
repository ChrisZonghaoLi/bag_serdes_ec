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
        self.has_hp = False
        self.has_div = False
        self.has_pul = False
        self.has_set = False
        self.has_re = False
        self.re_dummy = False

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

        master_sum = self.instances['XSUM'].master
        master_lat = self.instances['XLAT'].master

        self.has_hp = master_sum.has_hp
        if master_lat.has_div:
            self.has_div = True
        else:
            for name in ['div', 'divb', 'scan_div']:
                self.remove_pin(name)
            if master_lat.has_re:
                self.has_re = True
                if master_lat.re_dummy:
                    self.re_dummy = True
                    self.remove_pin('en_div')
                    self.remove_pin('en_div3')
                    self.remove_pin('en_div2')
            else:
                self.remove_pin('en_div3')
                self.remove_pin('en_div2')

        if master_lat.has_pul:
            self.has_pul = True
        else:
            self.remove_pin('pulse_out')

        if master_sum.has_set or master_lat.has_set:
            self.has_set = True
        else:
            for name in ('setp', 'setn', 'pulse_in'):
                self.remove_pin(name)
