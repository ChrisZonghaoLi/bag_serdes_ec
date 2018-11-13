# -*- coding: utf-8 -*-

from typing import Dict, Any

import os
import pkg_resources

from bag.design import Module


yaml_file = pkg_resources.resource_filename(__name__, os.path.join('netlist_info',
                                                                   'integ_load.yaml'))


# noinspection PyPep8Naming
class bag_serdes_ec__integ_load(Module):
    """Module for library bag_serdes_ec cell integ_load.

    Fill in high level description here.
    """

    load_names = ('XLOADP0', 'XLOADP1', 'XLOADN0', 'XLOADN1')
    en_names = ('XPENP0', 'XPENP1', 'XPENN0', 'XPENN1')

    def __init__(self, bag_config, parent=None, prj=None, **kwargs):
        Module.__init__(self, bag_config, yaml_file, parent=parent, prj=prj, **kwargs)
        self.has_clk = False
        self.has_en = False
        self.en_only = False

    @classmethod
    def get_params_info(cls):
        # type: () -> Dict[str, str]
        return dict(
            lch='channel length, in meters.',
            w_dict='NMOS/PMOS width dictionary.',
            th_dict='NMOS/PMOS threshold flavor dictionary.',
            seg_dict='number of segments dictionary.',
            dum_info='Dummy information data structure.',
        )

    @classmethod
    def get_default_param_values(cls):
        # type: () -> Dict[str, Any]
        return dict(
            dum_info=None,
        )

    @classmethod
    def is_empty(cls, seg_dict, dum_info):
        return (not dum_info) and seg_dict.get('load', 0) <= 0 and seg_dict.get('pen', 0) <= 0

    def design(self, lch, w_dict, th_dict, seg_dict, dum_info):
        seg_load = seg_dict.get('load', 0)
        w_load = w_dict.get('load', 0)
        th_load = th_dict.get('load', 'standard')
        seg_en = seg_dict.get('pen', 0)
        w_en = w_dict.get('pen', 0)
        th_en = th_dict.get('pen', 'standard')
        en_only = seg_dict.get('en_only', False)
        en_swap = seg_dict.get('en_swap', False)

        if seg_load <= 0:
            self.has_clk = False
            for name in self.load_names:
                self.delete_instance(name)
            for name in ('clkp', 'clkn'):
                self.remove_pin(name)
            if seg_en <= 0:
                self.has_en = False
                for name in ('en<3:2>', 'outp', 'outn'):
                    self.remove_pin(name)
                for name in self.en_names:
                    self.delete_instance(name)
            else:
                self.has_en = True
                self.delete_instance('XPENP1')
                self.delete_instance('XPENN1')
                self.instances['XPENP0'].design(w=w_en, l=lch, nf=seg_en, intent=th_en)
                self.instances['XPENN0'].design(w=w_en, l=lch, nf=seg_en, intent=th_en)
                self.reconnect_instance_terminal('XPENP0', 'S', 'VDD')
                self.reconnect_instance_terminal('XPENN0', 'S', 'VDD')
        else:
            if en_only:
                self.rename_pin('en<3:2>', 'en<3>')
                self.en_only = True
            self.has_clk = self.has_en = True
            for name in self.load_names:
                self.instances[name].design(w=w_load, l=lch, nf=seg_load, intent=th_load)
            for name in self.en_names:
                self.instances[name].design(w=w_en, l=lch, nf=seg_en, intent=th_en)
                if en_only:
                    self.reconnect_instance_terminal(name, 'S', 'VDD')
                    self.reconnect_instance_terminal(name, 'G', 'en<3>')
            if en_swap:
                self.reconnect_instance_terminal('XLOADP0', 'G', 'en<3>')
                self.reconnect_instance_terminal('XPENP0', 'G', 'clkn')
                self.reconnect_instance_terminal('XLOADP1', 'G', 'en<2>')
                self.reconnect_instance_terminal('XPENP1', 'G', 'clkp')
                self.reconnect_instance_terminal('XLOADN0', 'G', 'en<3>')
                self.reconnect_instance_terminal('XPENN0', 'G', 'clkn')
                self.reconnect_instance_terminal('XLOADN1', 'G', 'en<2>')
                self.reconnect_instance_terminal('XPENN1', 'G', 'clkp')

        self.design_dummy_transistors(dum_info, 'XDUM', 'VDD', 'VSS')
