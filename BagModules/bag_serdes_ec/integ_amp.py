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
        self.has_set = False
        self.has_casc = False
        self.has_but = False
        self.has_clkp = False
        self.has_clkn = False
        self.has_en2 = False

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
        gm = self.instances['XGM']
        load = self.instances['XLOAD']
        gm.design(**gm_params)
        load.design(load_params_list=[load_params], nin=1)

        if flip_sign:
            self.reconnect_instance_terminal('XGM', 'outp', 'iin')
            self.reconnect_instance_terminal('XGM', 'outn', 'iip')

        if not gm_params.get('export_probe', False):
            self.remove_pin('tail')
            self.remove_pin('foot')

        master = gm.master
        if master.has_casc:
            self.has_casc = True
            self.rename_pin('casc<1:0>', 'casc')
            self.reconnect_instance_terminal('XGM', 'casc', 'casc')
        elif master.has_but:
            self.has_but = True
        else:
            self.remove_pin('casc<1:0>')

        if master.has_set:
            self.has_set = True
        else:
            self.remove_pin('setp')
            self.remove_pin('setn')
            self.remove_pin('pulse')
        if master.has_tsw:
            self.has_clkn = True

        master = load.master
        if master.has_clk:
            self.has_clkp = self.has_clkn = True
        if master.has_en and not master.en_only:
            self.has_en2 = True
        elif master.en_only:
            self.reconnect_instance_terminal('XLOAD', 'en<3>', 'en<3>')

        if not self.has_clkp:
            self.remove_pin('clkp')
        if not self.has_clkn:
            self.remove_pin('clkn')
        if not self.has_en2:
            self.rename_pin('en<3:2>', 'en<3>')
