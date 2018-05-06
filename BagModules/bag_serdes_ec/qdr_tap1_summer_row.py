# -*- coding: utf-8 -*-

from typing import Dict, Any

import os
import pkg_resources

from bag.design import Module


yaml_file = pkg_resources.resource_filename(__name__, os.path.join('netlist_info',
                                                                   'qdr_tap1_summer_row.yaml'))


# noinspection PyPep8Naming
class bag_serdes_ec__qdr_tap1_summer_row(Module):
    """Module for library bag_serdes_ec cell qdr_tap1_summer_row.

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
            seg_main='number of segments dictionary for main tap.',
            seg_fb='number of segments dictionary for feedback tap.',
            m_dum_info='Main tap dummy information.',
            f_dum_info='Feedback tap dummy information.'
        )

    @classmethod
    def get_default_param_values(cls):
        # type: () -> Dict[str, Any]
        return dict(
            m_dum_info=None,
            f_dum_info=None,
        )

    def design(self, lch, w_dict, th_dict, seg_main, seg_fb, m_dum_info, f_dum_info):
        self.instances['XMAIN'].design(lch=lch, w_dict=w_dict, th_dict=th_dict,
                                       seg_dict=seg_main, dum_info=m_dum_info)
        self.instances['XTAP1'].design(lch=lch, w_dict=w_dict, th_dict=th_dict,
                                       seg_dict=seg_fb, dum_info=f_dum_info)

        if 'pulse' not in self.instances['XMAIN'].master.pin_list:
            for name in ('setp', 'setn', 'pulse'):
                self.remove_pin(name)
