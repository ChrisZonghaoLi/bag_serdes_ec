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
            seg_dict='number of segments dictionary for latches.',
            seg_buf='output inverter size.',
        )

    def design(self, lch, w_dict, th_dict, seg_dict, seg_buf):
        wp = w_dict['p1']
        wn = w_dict['n1']
        wpen = w_dict['p0']
        wnen = w_dict['n2']
        thp = th_dict['p1']
        thn = th_dict['n1']
        thpen = th_dict['p0']
        thnen = th_dict['n2']

        params = dict(lch=lch, wp=wp, wn=wn, thp=thp, thn=thn, seg_m=seg_dict,
                      seg_s=seg_dict, pass_zero=True, wpen=wpen,
                      wnen=wnen, thpen=thpen, thnen=thnen)
        self.instances['XFF0'].design(**params)
        seg_dict_out = seg_dict.copy()
        seg_dict_out['pinv'] = seg_dict_out['ninv'] = seg_buf
        params = dict(lch=lch, wp=wp, wn=wn, thp=thp, thn=thn, seg_m=seg_dict,
                      seg_s=seg_dict_out, pass_zero=True, wpen=wpen,
                      wnen=wnen, thpen=thpen, thnen=thnen)
        self.instances['XFF1'].design(**params)
        params['seg_dict'] = seg_dict_out
        self.instances['XLAT'].design(**params)
