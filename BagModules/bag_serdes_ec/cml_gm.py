# -*- coding: utf-8 -*-

from typing import Dict, Any

import os
import pkg_resources

from bag.design import Module


yaml_file = pkg_resources.resource_filename(__name__, os.path.join('netlist_info', 'cml_gm.yaml'))


# noinspection PyPep8Naming
class bag_serdes_ec__cml_gm(Module):
    """Module for library bag_serdes_ec cell cml_gm.

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
        tran_info_list = [('XTAIL', 'tail', 'tail'), ('XREF', 'tail', 'ref'),
                          ('XINP', 'in', 'in'), ('XINN', 'in', 'in'),
                          ]

        for inst_info in tran_info_list:
            inst_name, inst_type, seg_type = inst_info
            w = w_dict[inst_type]
            th = th_dict[inst_type]
            seg = seg_dict[seg_type]
            self.instances[inst_name].design(w=w, l=lch, nf=seg, intent=th)

        self.design_dummy_transistors(dum_info, 'XDUM', 'VDD', 'VSS')
