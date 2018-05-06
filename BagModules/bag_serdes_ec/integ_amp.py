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
            lch='channel length, in meters.',
            w_dict='NMOS/PMOS width dictionary.',
            th_dict='NMOS/PMOS threshold flavor dictionary.',
            seg_dict='number of segments dictionary.',
            flip_sign='True to flip output sign.',
            hp_params='high-pass parameters.  If None, delete it.',
            dum_info='Dummy information data structure.',
            export_probe='True to export probe ports.',
        )

    @classmethod
    def get_default_param_values(cls):
        # type: () -> Dict[str, Any]
        return dict(
            flip_sign=False,
            hp_params=None,
            dum_info=None,
            export_probe=False,
        )

    def design(self, lch, w_dict, th_dict, seg_dict, flip_sign, hp_params, dum_info, export_probe):
        if dum_info is None:
            ndum_info = pdum_info = None
        else:
            ndum_info = []
            pdum_info = []
            for info in dum_info:
                if info[0][0] == 'pch':
                    pdum_info.append(info)
                else:
                    ndum_info.append(info)

        nw_dict = {k: v for k, v in w_dict.items() if k != 'load' and k != 'pen'}
        nth_dict = {k: v for k, v in th_dict.items() if k != 'load' and k != 'pen'}
        nseg_dict = {k: v for k, v in seg_dict.items() if k != 'load' and k != 'pen'}
        self.instances['XGM'].design(lch=lch, w_dict=nw_dict, th_dict=nth_dict, seg_dict=nseg_dict,
                                     hp_params=hp_params, dum_info=ndum_info,
                                     export_probe=export_probe)
        pw_dict = {'load': w_dict.get('load', 0), 'pen': w_dict.get('pen', 0)}
        pth_dict = {'load': th_dict.get('load', 'standard'), 'pen': th_dict.get('pen', 'standard')}
        pseg_dict = {'load': seg_dict.get('load', 0), 'pen': seg_dict.get('pen', 0)}
        load_params = dict(
            lch=lch,
            w_dict=pw_dict,
            th_dict=pth_dict,
            seg_dict=pseg_dict,
            dum_info=pdum_info
        )
        self.instances['XLOAD'].design(load_params_list=[load_params], nin=1)

        if flip_sign:
            self.reconnect_instance_terminal('XGM', 'outp', 'iin')
            self.reconnect_instance_terminal('XGM', 'outn', 'iip')

        if not export_probe:
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
