# -*- coding: utf-8 -*-

from typing import Dict, Any

import os
import pkg_resources

from bag.design import Module

yaml_file = pkg_resources.resource_filename(__name__, os.path.join('netlist_info',
                                                                   'qdr_tap1_column.yaml'))


# noinspection PyPep8Naming
class bag_serdes_ec__qdr_tap1_column(Module):
    """Module for library bag_serdes_ec cell qdr_tap1_column.

    Fill in high level description here.
    """

    def __init__(self, bag_config, parent=None, prj=None, **kwargs):
        Module.__init__(self, bag_config, yaml_file, parent=parent, prj=prj, **kwargs)
        self.has_hp = False

    @classmethod
    def get_params_info(cls):
        # type: () -> Dict[str, str]
        return dict(
            sum_params='summer row parameters.',
            lat_params='latch parameters.',
            div_params='divider column parameters.',
            export_probe='True to export probe ports.',
        )

    @classmethod
    def get_default_param_values(cls):
        # type: () -> Dict[str, Any]
        return dict(
            export_probe=False,
        )

    def design(self, sum_params, lat_params, div_params, export_probe):
        self.instances['X0'].design(sum_params=sum_params, lat_params=lat_params)
        self.instances['X1'].design(sum_params=sum_params, lat_params=lat_params)
        self.instances['X2'].design(sum_params=sum_params, lat_params=lat_params)
        self.instances['X3'].design(sum_params=sum_params, lat_params=lat_params)
        self.instances['XDIV'].design(**div_params)

        self.has_hp = self.instances['X0'].master.has_hp
        if not export_probe:
            self.remove_pin('en<3:0>')
