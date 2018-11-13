# -*- coding: utf-8 -*-

from typing import Dict

import os
import pkg_resources

from bag.design import Module

yaml_file = pkg_resources.resource_filename(__name__, os.path.join('netlist_info',
                                                                   'qdr_divider_column.yaml'))


# noinspection PyPep8Naming
class bag_serdes_ec__qdr_divider_column(Module):
    """Module for library bag_serdes_ec cell qdr_divider_column.

    Fill in high level description here.
    """

    def __init__(self, bag_config, parent=None, prj=None, **kwargs):
        Module.__init__(self, bag_config, yaml_file, parent=parent, prj=prj, **kwargs)

    @classmethod
    def get_params_info(cls):
        # type: () -> Dict[str, str]
        return dict(
            lch='channel length, in meters.',
            w_dict='NMOS/PMOS width dictionary.',
            th_dict='NMOS/PMOS threshold flavor dictionary.',
            seg_div='number of segments dictionary for divider.',
            seg_re='number of segments dictionary for retimer latches.',
            seg_buf='retimer output buffer size.',
            sr_params='SR latch parameteres.'
        )

    def design(self, lch, w_dict, th_dict, seg_div, seg_re, seg_buf, sr_params):
        for name in ('XDIV2', 'XDIV3'):
            self.instances[name].design(lch=lch, w_dict=w_dict, th_dict=th_dict,
                                        seg_dict=seg_div, sr_params=sr_params)
        for name in ('XRE', 'XDUM'):
            self.instances[name].design(lch=lch, w_dict=w_dict, th_dict=th_dict,
                                        seg_dict=seg_re, seg_buf=seg_buf)
