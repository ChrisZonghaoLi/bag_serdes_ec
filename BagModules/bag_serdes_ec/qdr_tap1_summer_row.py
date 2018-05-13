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
        self.has_hp = False
        self.has_set = False

    @classmethod
    def get_params_info(cls):
        # type: () -> Dict[str, str]
        return dict(
            lch='channel length, in meters.',
            w_dict='NMOS/PMOS width dictionary.',
            th_dict='NMOS/PMOS threshold flavor dictionary.',
            seg_main='number of segments dictionary for main tap.',
            seg_fb='number of segments dictionary for feedback tap.',
            hp_params='high-pass parameters.  If None, delete it.',
            m_dum_info='Main tap dummy information.',
            f_dum_info='Feedback tap dummy information.'
        )

    @classmethod
    def get_default_param_values(cls):
        # type: () -> Dict[str, Any]
        return dict(
            hp_params=None,
            m_dum_info=None,
            f_dum_info=None,
        )

    def design(self, lch, w_dict, th_dict, seg_main, seg_fb, hp_params, m_dum_info, f_dum_info):
        self.has_hp = (hp_params is not None)

        nw = {k: v for k, v in w_dict.items() if k != 'load' and k != 'pen'}
        nth = {k: v for k, v in th_dict.items() if k != 'load' and k != 'pen'}
        nseg_m = {k: v for k, v in seg_main.items() if k != 'load' and k != 'pen'}
        nseg_f = {k: v for k, v in seg_fb.items() if k != 'load' and k != 'pen'}
        pw = {'load': w_dict.get('load', 0), 'pen': w_dict.get('pen', 0)}
        pth = {'load': th_dict.get('load', 'standard'), 'pen': th_dict.get('pen', 'standard')}
        pseg_m = {'load': seg_main.get('load', 0), 'pen': seg_main.get('pen', 0)}
        pseg_f = {'load': seg_fb.get('load', 0), 'pen': seg_fb.get('pen', 0)}
        ndum_m, pdum_m = self._split_dummies(m_dum_info)
        ndum_f, pdum_f = self._split_dummies(f_dum_info)

        load_params_list = [dict(lch=lch, w_dict=pw, th_dict=pth, seg_dict=pseg_m, dum_info=pdum_m),
                            dict(lch=lch, w_dict=pw, th_dict=pth, seg_dict=pseg_f, dum_info=pdum_f),
                            ]

        self.instances['XMAIN'].design(lch=lch, w_dict=nw, th_dict=nth, seg_dict=nseg_m,
                                       hp_params=None, dum_info=ndum_m)
        self.instances['XFB'].design(lch=lch, w_dict=nw, th_dict=nth, seg_dict=nseg_f,
                                     hp_params=hp_params, dum_info=ndum_f)
        self.instances['XLOAD'].design(load_params_list=load_params_list, nin=2)
        self.reconnect_instance_terminal('XLOAD', 'iip<1:0>', 'iip<1>,iip<0>')
        self.reconnect_instance_terminal('XLOAD', 'iin<1:0>', 'iin<1>,iin<0>')

        master = self.instances['XMAIN'].master
        if master.has_set:
            self.has_set = True
        else:
            for name in ('setp', 'setn', 'pulse'):
                self.remove_pin(name)

    @classmethod
    def _split_dummies(cls, dum_info):
        if dum_info is None:
            ndum_info = pdum_info = None
        else:
            ndum_info = []
            pdum_info = []
            for info in dum_info:
                if info[0][0] == 'pch':
                    pdum_info.append(info)
                else:
                    ndum_info.append(info)

        return ndum_info, pdum_info
