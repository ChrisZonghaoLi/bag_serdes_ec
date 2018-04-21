# -*- coding: utf-8 -*-

from typing import Dict, Any

import os
import pkg_resources

from bag.design import Module


yaml_file = pkg_resources.resource_filename(__name__, os.path.join('netlist_info',
                                                                   'sense_amp_strongarm.yaml'))


# noinspection PyPep8Naming
class bag_serdes_ec__sense_amp_strongarm(Module):
    """Module for library bag_serdes_ec cell sense_amp_strongarm.

    Fill in high level description here.
    """

    def __init__(self, bag_config, parent=None, prj=None, **kwargs):
        Module.__init__(self, bag_config, yaml_file, parent=parent, prj=prj, **kwargs)

    @classmethod
    def get_params_info(cls):
        # type: () -> Dict[str, str]
        return dict(
            lch='Channel length, in meters.',
            w_dict='width dictionary.',
            th_dict='threshold dictionary.',
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
        tran_info_list = [('XTAILL', 'tail'), ('XTAILR', 'tail'),
                          ('XINL', 'in'), ('XINR', 'in'),
                          ('XNINVL', 'ninv'), ('XNINVR', 'ninv'),
                          ('XPINVL', 'pinv'), ('XPINVR', 'pinv'),
                          ('XRML', 'pinv'), ('XRMR', 'pinv'),
                          ('XRIL', 'pinv'), ('XRIR', 'pinv'),
                          ]

        for inst_name, inst_type in tran_info_list:
            w = w_dict[inst_type]
            th = th_dict[inst_type]
            seg = seg_dict[inst_type]
            self.instances[inst_name].design(w=w, l=lch, nf=seg, intent=th)

        self.design_dummy_transistors(dum_info, 'XDUM', 'VDD', 'VSS')
