# -*- coding: utf-8 -*-

from typing import Dict, Any

import os
import pkg_resources

from bag.design import Module


yaml_file = pkg_resources.resource_filename(__name__, os.path.join('netlist_info',
                                                                   'integ_load.yaml'))


# noinspection PyPep8Naming
class bag_serdes_ec__integ_load(Module):
    """Module for library bag_serdes_ec cell integ_load.

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
        tran_info_list = [('XPENP0', 'pen'), ('XPENP1', 'pen'),
                          ('XPENN0', 'pen'), ('XPENN1', 'pen'),
                          ('XLOADP0', 'load'), ('XLOADP1', 'load'),
                          ('XLOADN0', 'load'), ('XLOADN1', 'load'),
                          ]

        for inst_info in tran_info_list:
            inst_name, inst_type = inst_info
            seg = seg_dict.get(inst_type, 0)
            w = w_dict.get(inst_type, 0)
            th = th_dict.get(inst_type, 'standard')
            if seg <= 0:
                self.delete_instance(inst_name)
            else:
                self.instances[inst_name].design(w=w, l=lch, nf=seg, intent=th)

        seg_load = seg_dict.get('load', 0)
        if seg_load <= 0:
            for name in ('clkp', 'clkn', 'en<3:2>', 'outp', 'outn'):
                self.remove_pin(name)

        self.design_dummy_transistors(dum_info, 'XDUM', 'VDD', 'VSS')
