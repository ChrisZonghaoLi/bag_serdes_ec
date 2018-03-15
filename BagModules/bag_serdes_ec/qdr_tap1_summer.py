# -*- coding: utf-8 -*-

from typing import Dict

import os
import pkg_resources

from bag.design import Module


yaml_file = pkg_resources.resource_filename(__name__, os.path.join('netlist_info',
                                                                   'qdr_tap1_summer.yaml'))


# noinspection PyPep8Naming
class bag_serdes_ec__qdr_tap1_summer(Module):
    """Module for library bag_serdes_ec cell qdr_tap1_summer.

    Fill in high level description here.
    """

    def __init__(self, bag_config, parent=None, prj=None, **kwargs):
        Module.__init__(self, bag_config, yaml_file, parent=parent, prj=prj, **kwargs)

    @classmethod
    def get_params_info(cls):
        # type: () -> Dict[str, str]
        return dict(
            main_params='Main tap parameters.',
            fb_params='Feedback tap parameters.',
        )

    def design(self, main_params, fb_params):
        self.instances['XMAIN'].design(**main_params)
        self.instances['XFB'].design(**fb_params)

        # delete divider pins if they are not there.
        if 'div' not in self.instances['XMAIN'].master.pin_list:
            for name in ['div', 'divb', 'en_div', 'scan_div']:
                self.remove_pin(name)
