# -*- coding: utf-8 -*-

from typing import Dict

import os
import pkg_resources

from bag.design import Module


yaml_file = pkg_resources.resource_filename(__name__, os.path.join('netlist_info', 'ser_32.yaml'))


# noinspection PyPep8Naming
class bag_serdes_ec__ser_32(Module):
    """Module for library bag_serdes_ec cell ser_32.

    Fill in high level description here.
    """

    def __init__(self, bag_config, parent=None, prj=None, **kwargs):
        Module.__init__(self, bag_config, yaml_file, parent=parent, prj=prj, **kwargs)

    @classmethod
    def get_params_info(cls):
        # type: () -> Dict[str, str]
        return dict(
            ser_params='serializer parameters.',
            mux_params='mux parameters.',
            div_params='divider parameters.',
            buf_params='buffer parameters.',
        )

    def design(self, ser_params, mux_params, div_params, buf_params):
        lib_name = ser_params['lib_name']
        cell_name = ser_params['cell_name']
        self.replace_instance_master('XSERB', lib_name, cell_name, static=True)
        self.replace_instance_master('XSERT', lib_name, cell_name, static=True)
        lib_name = mux_params['lib_name']
        cell_name = mux_params['cell_name']
        self.replace_instance_master('XMUX', lib_name, cell_name, static=True)

        self.instances['XDIV'].design(**div_params)
        self.instances['XBUFP'].design(**buf_params)
        self.instances['XBUFN'].design(**buf_params)
