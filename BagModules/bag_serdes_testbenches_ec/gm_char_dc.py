# -*- coding: utf-8 -*-

from typing import Dict

import os
import pkg_resources

from bag.design import Module


yaml_file = pkg_resources.resource_filename(__name__, os.path.join('netlist_info',
                                                                   'gm_char_dc.yaml'))


# noinspection PyPep8Naming
class bag_serdes_testbenches_ec__gm_char_dc(Module):
    """Module for library bag_serdes_testbenches_ec cell gm_char_dc.

    Fill in high level description here.
    """

    def __init__(self, bag_config, parent=None, prj=None, **kwargs):
        Module.__init__(self, bag_config, yaml_file, parent=parent, prj=prj, **kwargs)

    @classmethod
    def get_params_info(cls):
        # type: () -> Dict[str, str]
        return dict(
            lib_name='DUT library name.',
            cell_name='DUT cell name.',
        )

    def design(self, lib_name, cell_name):
        self.replace_instance_master('XDUT', lib_name, cell_name, static=True)
