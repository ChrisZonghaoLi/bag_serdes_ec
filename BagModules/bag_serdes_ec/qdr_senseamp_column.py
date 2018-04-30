# -*- coding: utf-8 -*-

from typing import Dict, Any

import os
import pkg_resources

from bag.design import Module


yaml_file = pkg_resources.resource_filename(__name__, os.path.join('netlist_info',
                                                                   'qdr_senseamp_column.yaml'))


# noinspection PyPep8Naming
class bag_serdes_ec__qdr_senseamp_column(Module):
    """Module for library bag_serdes_ec cell qdr_senseamp_column.

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
            export_probe='True to export probe pins.',
        )

    @classmethod
    def get_default_param_values(cls):
        # type: () -> Dict[str, Any]
        return dict(
            dum_info=None,
            export_probe=False,
        )

    def design(self, lch, w_dict, th_dict, seg_dict, dum_info, export_probe):
        for name in ('XDLEV<3:0>', 'XDATA<3:0>'):
            self.instances[name].design(lch=lch, w_dict=w_dict, th_dict=th_dict,
                                        seg_dict=seg_dict, dum_info=dum_info,
                                        export_probe=export_probe)
