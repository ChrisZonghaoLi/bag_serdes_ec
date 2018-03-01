# -*- coding: utf-8 -*-

from typing import Dict, Union, Any

import os
import pkg_resources

from bag.design import Module


yaml_file = pkg_resources.resource_filename(__name__, os.path.join('netlist_info',
                                                                   'integ_amp.yaml'))


# noinspection PyPep8Naming
class bag_serdes_ec__integ_amp(Module):
    """Module for library bag_serdes_ec cell integ_amp.

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
            dum_info='Dummy information data structure.',
        )

    @classmethod
    def get_default_param_values(cls):
        # type: () -> Dict[str, Any]
        return dict(
            dum_info=None,
        )

    def design(self, lch, w_dict, th_dict, seg_dict, dum_info):
        # type: (float, Dict[str, Union[float, int]], Dict[str, str], Dict[str, int]) -> None
        tran_info_list = [('XTAILP', 'tail'), ('XTAILN', 'tail'),
                          ('XNENP', 'nen'), ('XNENN', 'nen'),
                          ('XINP', 'in'), ('XINN', 'in'),
                          ('XPENP0', 'pen'), ('XPENP1', 'pen'),
                          ('XPENN0', 'pen'), ('XPENN1', 'pen'),
                          ('XLOADP0', 'load'), ('XLOADP1', 'load'),
                          ('XLOADN0', 'load'), ('XLOADN1', 'load'),
                          ]

        for inst_name, inst_type in tran_info_list:
            w = w_dict[inst_type]
            th = th_dict[inst_type]
            seg = seg_dict[inst_type]
            self.instances[inst_name].design(w=w, l=lch, nf=seg, intent=th)

        self.design_dummy_transistors(dum_info, 'XDUM', 'VDD', 'VSS')
