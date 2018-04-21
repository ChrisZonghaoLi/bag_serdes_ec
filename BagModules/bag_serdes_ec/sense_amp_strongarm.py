# -*- coding: utf-8 -*-

from typing import Dict

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
        )

    def design(self, lch, w_dict, th_dict, seg_dict):
        pass
