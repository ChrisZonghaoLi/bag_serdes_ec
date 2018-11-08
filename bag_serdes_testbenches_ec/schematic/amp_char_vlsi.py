# -*- coding: utf-8 -*-

from typing import Dict

import os
import pkg_resources

from bag.design import Module


yaml_file = pkg_resources.resource_filename(__name__, os.path.join('netlist_info',
                                                                   'amp_char_vlsi.yaml'))


# noinspection PyPep8Naming
class bag_serdes_testbenches_ec__amp_char_vlsi(Module):
    """Module for library bag_serdes_testbenches_ec cell amp_char_vlsi.

    Fill in high level description here.
    """

    def __init__(self, bag_config, parent=None, prj=None, **kwargs):
        Module.__init__(self, bag_config, yaml_file, parent=parent, prj=prj, **kwargs)

    @classmethod
    def get_params_info(cls):
        # type: () -> Dict[str, str]
        return dict(
            dut_lib='DUT library name.',
            dut_cell='DUT cell name.',
        )

    def design(self, dut_lib, dut_cell):
        self.replace_instance_master('XDUT', dut_lib, dut_cell, static=True)
