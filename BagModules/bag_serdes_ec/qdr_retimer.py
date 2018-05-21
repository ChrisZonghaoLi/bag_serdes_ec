# -*- coding: utf-8 -*-

from typing import Dict

import os
import pkg_resources

from bag.design import Module


yaml_file = pkg_resources.resource_filename(__name__, os.path.join('netlist_info',
                                                                   'qdr_retimer.yaml'))


# noinspection PyPep8Naming
class bag_serdes_ec__qdr_retimer(Module):
    """Module for library bag_serdes_ec cell qdr_retimer.

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
            delay_ck3='True to delay phase 3',
        )

    def design(self, ff_params, lat_params, buf_params, delay_params, delay_ck3):
        self.instances['XBUF3'].design(**buf_params)
        if delay_ck3:
            self.reconnect_instance_terminal('XBUF3', 'in', 'mid0<3>')
            self.instances['XFF3'].design(**ff_params)
        else:
            self.delete_instance('XFF3')

        self.instances['XFF2'].design(**ff_params)
        self.instances['XLAT1'].design(**lat_params)
        self.instances['XLAT0'].design(**lat_params)
        self.instances['XBUF1'].design(**buf_params)
        self.instances['XRT<3:0>'].design(**ff_params)
        self.instances['XDELAY<3:0>'].design(**delay_params)
