# -*- coding: utf-8 -*-

from typing import Dict, Any

import os
import pkg_resources

from bag.design import Module


yaml_file = pkg_resources.resource_filename(__name__, os.path.join('netlist_info',
                                                                   'integ_amp.yaml'))


# noinspection PyPep8Naming
class bag_serdes_ec__integ_amp(Module):
    """Module for library bag_serdes_ec cell integ_amp.

    Fill in high level description here.
    """

    def __init__(self, bag_config, parent=None, prj=None, **kwargs):
        Module.__init__(self, bag_config, yaml_file, parent=parent, prj=prj, **kwargs)

    @classmethod
    def get_params_info(cls):
        # type: () -> Dict[str, str]
        return dict(
            gm_params='Gm parameters dictionary.',
            load_params='Load parameters dictionary.',
            flip_sign='True to flip sign.',
        )

    @classmethod
    def get_default_param_values(cls):
        # type: () -> Dict[str, Any]
        return dict(
            flip_sign=False,
        )

    def design(self, gm_params, load_params, flip_sign):
        self.instances['XGM'].design(**gm_params)
        self.instances['XLOAD'].design(load_params_list=[load_params], nin=1)

        if flip_sign:
            self.reconnect_instance_terminal('XGM', 'outp', 'iin')
            self.reconnect_instance_terminal('XGM', 'outn', 'iip')

        if not gm_params.get('export_probe', False):
            self.remove_pin('tail')
            self.remove_pin('foot')

        pin_list = self.instances['XGM'].master.pin_list
        has_set = has_casc = False
        for pin in pin_list:
            if pin == 'setp':
                has_set = True
            if pin.startswith('casc'):
                has_casc = True
                if pin == 'casc':
                    self.rename_pin('casc<1:0>', 'casc')
        if not has_casc:
            self.remove_pin('casc<1:0>')
        if not has_set:
            self.remove_pin('setp')
            self.remove_pin('setn')
            self.remove_pin('pulse')
