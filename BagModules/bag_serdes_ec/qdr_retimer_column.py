# -*- coding: utf-8 -*-

from typing import Dict

import os
import pkg_resources

from bag.design import Module

yaml_file = pkg_resources.resource_filename(__name__, os.path.join('netlist_info',
                                                                   'qdr_retimer_column.yaml'))


# noinspection PyPep8Naming
class bag_serdes_ec__qdr_retimer_column(Module):
    """Module for library bag_serdes_ec cell qdr_retimer_column.

    Fill in high level description here.
    """

    def __init__(self, bag_config, parent=None, prj=None, **kwargs):
        Module.__init__(self, bag_config, yaml_file, parent=parent, prj=prj, **kwargs)

    @classmethod
    def get_params_info(cls):
        # type: () -> Dict[str, str]
        return dict(
            ff_params='flip-flop parameters.',
            lat_params='latch parameters.',
            buf_params='inverter chain parameters.',
            delay_params='delay chain parameters.',
            clk_buf_params='clock buffer parameters.',
            clk_inv_params='clock inverter parameters.',
        )

    def design(self, ff_params, lat_params, buf_params, delay_params,
               clk_buf_params, clk_inv_params):
        self.instances['XRTD'].design(ff_params=ff_params, lat_params=lat_params,
                                      buf_params=buf_params, delay_params=delay_params,
                                      delay_ck3=False)
        self.instances['XRTL'].design(ff_params=ff_params, lat_params=lat_params,
                                      buf_params=buf_params, delay_params=delay_params,
                                      delay_ck3=True)
        self.instances['XBUF'].design(**clk_buf_params)
        self.instances['XBUFB'].design(**clk_buf_params)
        self.instances['XCKINV1'].design(**clk_inv_params)
        self.instances['XCKINV3'].design(**clk_inv_params)
