# -*- coding: utf-8 -*-

from typing import Dict

import os
import pkg_resources

from bag.design import Module


yaml_file = pkg_resources.resource_filename(__name__, os.path.join('netlist_info',
                                                                   'qdr_tapx_summer.yaml'))


# noinspection PyPep8Naming
class bag_serdes_ec__qdr_tapx_summer(Module):
    """Module for library bag_serdes_ec cell qdr_tapx_summer.

    Fill in high level description here.
    """

    def __init__(self, bag_config, parent=None, prj=None, **kwargs):
        Module.__init__(self, bag_config, yaml_file, parent=parent, prj=prj, **kwargs)

    @classmethod
    def get_params_info(cls):
        # type: () -> Dict[str, str]
        return dict(
            ffe_params_list='List of FFE summer cell parameters.',
            dfe_params_list='List of DFE summer cell parameters.',
            last_params='Last summer cell parameters.',
        )

    def design(self, ffe_params_list, dfe_params_list, last_params):
        num_ffe = len(ffe_params_list)
        num_dfe = len(dfe_params_list)

        # design FFE
        # rename/remove pins
        if num_ffe == 1:
            self.remove_pin('casc')
            a_arr = '<0>'
        else:
            if num_ffe == 2:
                self.rename_pin('casc', 'casc<1>')
            else:
                self.rename_pin('casc', 'casc<%d:1>' % (num_ffe - 1))
            a_arr = '<%d:0>' % (num_ffe - 1)

        for base_name in ('inp_a', 'inn_a', 'outp_a', 'outn_a'):
            self.rename_pin(base_name, base_name + a_arr)
        # compute term list
        term_list, name_list = [], []
        for fidx in range(num_ffe - 1, -1, -1):
            term_dict = dict(inp='inp_a<%d>' % fidx, inn='inn_a<%d>' % fidx,
                             outp_l='outp_a<%d>' % fidx, outn_l='outn_a<%d>' % fidx)
            if fidx != 0:
                term_dict['casc'] = 'casc<%d>' % fidx
            term_list.append(term_dict)
            name_list.append('XFFE%d' % fidx)
        # array instance, and design
        self.array_instance('XFFE', name_list, term_list=term_list)
        for idx, ffe_params in enumerate(ffe_params_list):
            self.instances['XFFE'][num_ffe - 1 - idx].design(**ffe_params)

        # design DFE
        # rename/remove pins/instances
        if num_dfe == 0:
            # handle the case that we only have 2 taps of DFE
            self.delete_instance('XDFE')
            self.remove_pin('biasp_d')
            self.remove_pin('outp_d')
            self.remove_pin('outn_d')
            d_arr = '<2>'
            do_arr = None
        else:
            d_arr = '<%d:2>' % (num_dfe + 2)
            do_arr = '<3>' if num_dfe == 1 else ('<%d:3>' % (num_dfe + 2))
        for base_name in ('inp_d', 'inn_d', 'biasn_s'):
            self.rename_pin(base_name, base_name + d_arr)
        self.rename_pin('outp_d', 'outp_d' + do_arr)
        self.rename_pin('outn_d', 'outn_d' + do_arr)

        if num_dfe > 0:
            # compute term list
            term_list, name_list = [], []
            for idx in range(num_dfe - 1, -1, -1):
                didx = idx + 3
                term_dict = dict(inp='inp_d<%d>' % didx, inn='inn_d<%d>' % didx,
                                 outp_l='outp_d<%d>' % didx, outn_l='outn_d<%d>' % didx,
                                 biasn_s='biasn_s<%d>' % didx)
                term_list.append(term_dict)
                name_list.append('XDFE%d' % didx)
            # array instance, and design
            self.array_instance('XDFE', name_list, term_list=term_list)
            for idx, dfe_params in enumerate(dfe_params_list):
                self.instances['XDFE'][num_dfe - 1 - idx].design(**dfe_params)

        # design last cell
        self.reconnect_instance_terminal('XLAST', 'inp', 'inp_d<2>')
        self.reconnect_instance_terminal('XLAST', 'inn', 'inn_d<2>')
        self.reconnect_instance_terminal('XLAST', 'biasn', 'biasn_s<2>')
        self.instances['XLAST'].design(**last_params)

        # remove pins if not needed
        if 'pulse' not in self.instances['XFFE'][0].master.pin_list:
            self.remove_pin('setp')
            self.remove_pin('setn')
            self.remove_pin('pulse_in')
        last_pins = self.instances['XLAST'].master.pin_list
        has_div = 'div' in last_pins
        has_pulse = 'pulse_out' in last_pins
        if not has_div:
            self.remove_pin('scan_div')
            self.remove_pin('div')
            self.remove_pin('divb')
            if not has_pulse:
                self.remove_pin('en_div')
        if not has_pulse:
            self.remove_pin('pulse_out')
