# -*- coding: utf-8 -*-

from typing import Dict

import os
import pkg_resources

from bag.design import Module

yaml_file = pkg_resources.resource_filename(__name__, os.path.join('netlist_info',
                                                                   'enable_retimer.yaml'))


# noinspection PyPep8Naming
class bag_serdes_ec__enable_retimer(Module):
    """Module for library bag_serdes_ec cell enable_retimer.

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
            seg_dict='number of segments dictionary.',
        )

    def design(self, lch, w_dict, th_dict, seg_dict):
        wp = w_dict['pin']
        wn = w_dict['nin']
        wpen = w_dict['pen']
        wnen = w_dict['nen']
        thp = th_dict['pin']
        thn = th_dict['nin']
        thpen = th_dict['pen']
        thnen = th_dict['nen']

        params = dict(lch=lch, wp=wp, wn=wn, thp=thp, thn=thn, seg_m=seg_dict,
                      seg_s=seg_dict, seg_dict=seg_dict, pass_zero=True, wpen=wpen,
                      wnen=wnen, thpen=thpen, thnen=thnen)
        self.instances['XFF0'].design(**params)
        self.instances['XFF1'].design(**params)
        self.instances['XLAT'].design(**params)
