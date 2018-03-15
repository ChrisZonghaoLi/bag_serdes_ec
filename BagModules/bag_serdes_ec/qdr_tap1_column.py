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

    @classmethod
    def get_params_info(cls):
        # type: () -> Dict[str, str]
        return dict(
            main_params='main tap parameters.',
            div_params='divider parameters.',
            fb_params='feedback tap parameters.',
        )

    def design(self, main_params, div_params, fb_params):
        end_row_params = dict(
            div_pos_edge=True,
            main_params=main_params,
            div_params=None,
        )
        divp_row_params = dict(
            div_pos_edge=True,
            main_params=main_params,
            div_params=div_params,
        )
        divn_row_params = dict(
            div_pos_edge=False,
            main_params=main_params,
            div_params=div_params,
        )

        self.instances['X0'].design(main_params=end_row_params, fb_params=fb_params)
        self.instances['X1'].design(main_params=divn_row_params, fb_params=fb_params)
        self.instances['X2'].design(main_params=end_row_params, fb_params=fb_params)
        self.instances['X3'].design(main_params=divp_row_params, fb_params=fb_params)
