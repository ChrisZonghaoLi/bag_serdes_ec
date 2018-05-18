# -*- coding: utf-8 -*-

from typing import Dict

import os
import pkg_resources

from bag.design import Module


yaml_file = pkg_resources.resource_filename(__name__, os.path.join('netlist_info', 'term_rx.yaml'))


# noinspection PyPep8Naming
class bag_serdes_ec__term_rx(Module):
    """Module for library bag_serdes_ec cell term_rx.

    Fill in high level description here.
    """

    def __init__(self, bag_config, parent=None, prj=None, **kwargs):
        Module.__init__(self, bag_config, yaml_file, parent=parent, prj=prj, **kwargs)

    @classmethod
    def get_params_info(cls):
        # type: () -> Dict[str, str]
        return dict(
            esd_params='ESD parameters.',
            res_params='resistor parameters.',
            cap_params='MOM cap parameters.',
        )

    def design(self, esd_params, res_params, cap_params):
        self.instances['XRP'].design(**res_params)
        self.instances['XRN'].design(**res_params)
        self.instances['XCP'].design(**cap_params)
        self.instances['XCN'].design(**cap_params)

        lib_name = esd_params['lib_name']
        cell_name = esd_params['cell_name']
        self.replace_instance_master('XESDP', lib_name, cell_name, static=True)
        self.replace_instance_master('XESDN', lib_name, cell_name, static=True)
        self.reconnect_instance_terminal('XESDP', 'in', 'inp')
        self.reconnect_instance_terminal('XESDP', 'VDD', 'VDD')
        self.reconnect_instance_terminal('XESDP', 'VSS', 'VSS')
        self.reconnect_instance_terminal('XESDN', 'in', 'inn')
        self.reconnect_instance_terminal('XESDN', 'VDD', 'VDD')
        self.reconnect_instance_terminal('XESDN', 'VSS', 'VSS')
