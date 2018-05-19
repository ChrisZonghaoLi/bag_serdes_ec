# -*- coding: utf-8 -*-

from typing import Dict

import os
import pkg_resources

from bag.design import Module


yaml_file = pkg_resources.resource_filename(__name__, os.path.join('netlist_info',
                                                                   'tx_datapath.yaml'))


# noinspection PyPep8Naming
class bag_serdes_ec__tx_datapath(Module):
    """Module for library bag_serdes_ec cell tx_datapath.

    Fill in high level description here.
    """

    def __init__(self, bag_config, parent=None, prj=None, **kwargs):
        Module.__init__(self, bag_config, yaml_file, parent=parent, prj=prj, **kwargs)

    @classmethod
    def get_params_info(cls):
        # type: () -> Dict[str, str]
        return dict(
            ser_params='serializer parameters.',
            amp_params='CML driver parameters.',
            esd_params='ESD diode parameters.',
        )

    def design(self, ser_params, amp_params, esd_params):
        lib_name = esd_params['lib_name']
        cell_name = esd_params['cell_name']
        self.replace_instance_master('XESDP', lib_name, cell_name, static=True)
        self.replace_instance_master('XESDN', lib_name, cell_name, static=True)

        self.instances['XAMP'].design(**amp_params)
        self.instances['XSER'].design(**ser_params)
