# -*- coding: utf-8 -*-

from typing import Dict

import os
import pkg_resources

from bag.design import Module


yaml_file = pkg_resources.resource_filename(__name__, os.path.join('netlist_info',
                                                                   'qdr_datapath.yaml'))


# noinspection PyPep8Naming
class bag_serdes_ec__qdr_datapath(Module):
    """Module for library bag_serdes_ec cell qdr_datapath.

    Fill in high level description here.
    """

    def __init__(self, bag_config, parent=None, prj=None, **kwargs):
        Module.__init__(self, bag_config, yaml_file, parent=parent, prj=prj, **kwargs)

    @classmethod
    def get_params_info(cls):
        # type: () -> Dict[str, str]
        return dict(
            tapx_params='TapX summer parmeters.',
            off_params='Offset cancel parameters.',
            tap1_params='Tap1 summer parameters.',
            loff_params='dlev offset parameters.',
            samp_params='sampler parameters.',
        )

    def design(self, tapx_params, off_params, tap1_params, loff_params, samp_params):
        self.instances['XTAPX'].design(**tapx_params)
        self.instances['XOFF'].design(**off_params)
        self.instances['XTAP1'].design(**tap1_params)
        self.instances['XOFFL'].design(**loff_params)
        self.instances['XSAMP'].design(**samp_params)
