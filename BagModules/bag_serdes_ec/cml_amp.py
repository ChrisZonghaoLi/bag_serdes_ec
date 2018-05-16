# -*- coding: utf-8 -*-

from typing import Dict

import os
import pkg_resources

from bag.design import Module


yaml_file = pkg_resources.resource_filename(__name__, os.path.join('netlist_info', 'cml_amp.yaml'))


# noinspection PyPep8Naming
class bag_serdes_ec__cml_amp(Module):
    """Module for library bag_serdes_ec cell cml_amp.

    Fill in high level description here.
    """

    def __init__(self, bag_config, parent=None, prj=None, **kwargs):
        Module.__init__(self, bag_config, yaml_file, parent=parent, prj=prj, **kwargs)

    @classmethod
    def get_params_info(cls):
        # type: () -> Dict[str, str]
        return dict(
            res_params='resistor parameters.',
            gm_params='gm parameters.',
        )

    def design(self, res_params, gm_params):
        self.instances['XRP'].design(**res_params)
        self.instances['XRN'].design(**res_params)
        self.instances['XGM'].design(**gm_params)
