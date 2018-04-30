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

        has_set = False
        has_ffe = False
        tapx_pins = self.instances['XTAPX'].master.pin_list
        for name in tapx_pins:
            if name.startswith('casc'):
                has_ffe = True
                new_name = 'bias_ffe' + name[4:]
                self.rename_pin('bias_ffe<7:4>', new_name)
                self.reconnect_instance_terminal('XTAPX', name, new_name)
            elif name.startswith('bias_s'):
                suffix = name[6:]
                max_idx = int(suffix[1:].split(':')[0])
                sgnp_name = 'sgnp_dfe' + suffix
                sgnn_name = 'sgnn_dfe' + suffix
                self.rename_pin('sgnp_dfe<11:8>', sgnp_name)
                self.rename_pin('sgnn_dfe<11:8>', sgnn_name)
                self.rename_pin('clk_dfe<11:4>', 'clk_dfe<%d:4>' % max_idx)
                self.reconnect_instance_terminal('XTAPX', 'sgnp' + suffix, sgnp_name)
                self.reconnect_instance_terminal('XTAPX', 'sgnn' + suffix, sgnn_name)
                self.reconnect_instance_terminal('XTAPX', name, 'clk_dfe<%d:8>' % max_idx)
            elif name.startswith('setp'):
                has_set = True
                # TODO: figure out the rest

        if not has_ffe:
            self.remove_pin('bias_ffe<7:4>')
        if not has_set:
            self.remove_pin('setp')
            self.remove_pin('setn')
