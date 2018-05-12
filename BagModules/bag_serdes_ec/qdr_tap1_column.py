# -*- coding: utf-8 -*-

from typing import Dict

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
            lat_div_params='latch parameters in the divider row.',
            lat_pul_params='latch parameters in the pulse row.',
            div_params='divider parameters.',
            re_params='enable retimer parameters.',
            pul_params='pulse generation parameters.',
        )

    def design(self, sum_params, lat_params, lat_div_params, lat_pul_params,
               div_params, re_params, pul_params):
        endb_lat_params = dict(
            div_pos_edge=True,
            lat_params=lat_params,
            div_params=None,
            re_params=re_params,
            re_dummy=True,
            pul_params=None,
        )
        endt_lat_params = dict(
            div_pos_edge=True,
            lat_params=lat_pul_params,
            div_params=None,
            re_params=re_params,
            re_dummy=False,
            pul_params=pul_params,
        )
        div2_lat_params = dict(
            div_pos_edge=True,
            lat_params=lat_div_params,
            div_params=div_params,
            pul_params=None,
        )
        div3_lat_params = dict(
            div_pos_edge=False,
            lat_params=lat_div_params,
            div_params=div_params,
            pul_params=None,
        )

        if pul_params is None:
            # remove set pins
            self.remove_pin('setp<1:0>')
            self.remove_pin('setn<1:0>')

        self.instances['X3'].design(sum_params=sum_params, lat_params=endt_lat_params)
        self.instances['X0'].design(sum_params=sum_params, lat_params=div2_lat_params)
        self.instances['X2'].design(sum_params=sum_params, lat_params=div3_lat_params)
        self.instances['X1'].design(sum_params=sum_params, lat_params=endb_lat_params)

        self.has_hp = self.instances['X0'].master.has_hp
