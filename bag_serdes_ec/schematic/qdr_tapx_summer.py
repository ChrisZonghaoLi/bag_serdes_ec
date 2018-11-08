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
        self.en_only = False

    @classmethod
    def get_params_info(cls):
        # type: () -> Dict[str, str]
        return dict(
            ffe_params_list='List of FFE summer cell parameters.',
            dfe_params_list='List of DFE summer cell parameters.',
            dfe2_params='DFE tap2 gm/load parameters.',
        )

    def design(self, ffe_params_list, dfe_params_list, dfe2_params):
        num_ffe = len(ffe_params_list)
        if dfe_params_list is None:
            num_dfe = -1
        else:
            num_dfe = len(dfe_params_list)

        # design FFE
        # rename/remove pins
        if num_ffe == 1:
            self.remove_pin('casc')
            a_arr = '<0>'
        else:
            if num_ffe > 2:
                self.rename_pin('casc', 'casc<%d:1>' % (num_ffe - 1))
            a_arr = '<%d:0>' % (num_ffe - 1)

        for base_name in ('inp_a', 'inn_a', 'outp_a', 'outn_a'):
            self.rename_pin(base_name, base_name + a_arr)
        # compute term list
        load_idx = 0
        term_list = []
        name_list = []
        sum_params_list = []
        load_params_list = []
        for fidx in range(num_ffe - 1, -1, -1):
            ffe_params = ffe_params_list[fidx]
            ffe_suf = '<%d>' % fidx
            load_suf = '<%d>' % load_idx
            load_idx += 1
            if ffe_params.get('flip_sign', False):
                outp_s = 'iin' + load_suf
                outn_s = 'iip' + load_suf
            else:
                outp_s = 'iip' + load_suf
                outn_s = 'iin' + load_suf
            term_dict = dict(inp='inp_a' + ffe_suf, inn='inn_a' + ffe_suf,
                             outp_l='outp_a' + ffe_suf, outn_l='outn_a' + ffe_suf,
                             outp_s=outp_s, outn_s=outn_s)
            if fidx != 0:
                if num_ffe == 2:
                    term_dict['casc'] = 'casc'
                else:
                    term_dict['casc'] = 'casc' + ffe_suf
            term_list.append(term_dict)
            name_list.append('XFFE%d' % fidx)
            sum_params_list.append(ffe_params['sum_params'])
            load_params_list.append(ffe_params['load_params'])

        # array instance, and design
        self.array_instance('XFFE', name_list, term_list=term_list)
        for idx, sum_params in enumerate(sum_params_list):
            self.instances['XFFE'][idx].design(**sum_params)

        # design DFE
        if num_dfe < 0:
            # no DFE at all
            self.delete_instance('XDFE')
            self.delete_instance('XDFE2')
            for name in ['inp_d', 'inn_d', 'biasp_d', 'sgnp', 'sgnn', 'outp_d',
                         'outn_d', 'biasn_s']:
                self.remove_pin(name)
        else:
            # rename/remove pins/instances
            if num_dfe <= 0:
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
            for base_name in ('inp_d', 'inn_d', 'biasn_s', 'sgnp', 'sgnn'):
                self.rename_pin(base_name, base_name + d_arr)
            self.rename_pin('outp_d', 'outp_d' + do_arr)
            self.rename_pin('outn_d', 'outn_d' + do_arr)

            if num_dfe > 0:
                # compute term list
                term_list = []
                name_list = []
                sum_params_list = []
                for idx in range(num_dfe - 1, -1, -1):
                    dfe_params = dfe_params_list[idx]
                    didx = idx + 3
                    dfe_suf = '<%d>' % didx
                    load_suf = '<%d>' % load_idx
                    load_idx += 1
                    if dfe_params.get('flip_sign', False):
                        outp_s = 'iin' + load_suf
                        outn_s = 'iip' + load_suf
                    else:
                        outp_s = 'iip' + load_suf
                        outn_s = 'iin' + load_suf
                    term_dict = {'inp': 'inp_d' + dfe_suf, 'inn': 'inn_d' + dfe_suf,
                                 'outp_l': 'outp_d' + dfe_suf, 'outn_l': 'outn_d' + dfe_suf,
                                 'casc<1:0>': 'sgnn' + dfe_suf + ',sgnp' + dfe_suf,
                                 'biasn_s': 'biasn_s' + dfe_suf, 'outp_s': outp_s, 'outn_s': outn_s}
                    term_list.append(term_dict)
                    name_list.append('XDFE%d' % didx)
                    sum_params_list.append(dfe_params['sum_params'])
                    load_params_list.append(dfe_params['load_params'])
                # array instance, and design
                self.array_instance('XDFE', name_list, term_list=term_list)
                for idx, sum_params in enumerate(sum_params_list):
                    self.instances['XDFE'][idx].design(**sum_params)

            # design DFE tap2
            self.reconnect_instance_terminal('XDFE2', 'inp', 'inp_d<2>')
            self.reconnect_instance_terminal('XDFE2', 'inn', 'inn_d<2>')
            self.reconnect_instance_terminal('XDFE2', 'biasp', 'biasn_s<2>')
            self.reconnect_instance_terminal('XDFE2', 'casc<1:0>', 'sgnn<2>,sgnp<2>')
            load_suf = '<%d>' % load_idx
            load_idx += 1
            if dfe2_params.get('flip_sign', False):
                outp_s = 'iin' + load_suf
                outn_s = 'iip' + load_suf
            else:
                outp_s = 'iip' + load_suf
                outn_s = 'iin' + load_suf
            self.reconnect_instance_terminal('XDFE2', 'outp', outp_s)
            self.reconnect_instance_terminal('XDFE2', 'outn', outn_s)
            self.instances['XDFE2'].design(**dfe2_params['gm_params'])
            load_params_list.append(dfe2_params['load_params'])

        # design load
        nin = len(load_params_list)
        inst_load = self.instances['XLOAD']
        inst_load.design(load_params_list=load_params_list, nin=nin)
        suf = '<%d:0>' % (nin - 1)
        self.reconnect_instance_terminal('XLOAD', 'iip' + suf, 'iip' + suf)
        self.reconnect_instance_terminal('XLOAD', 'iin' + suf, 'iin' + suf)
        if inst_load.master.en_only:
            self.en_only = True
            self.reconnect_instance_terminal('XLOAD', 'en<3>', 'en<2>')
            self.rename_pin('en<3:1>', 'en<3:2>')

        # for now has_set is always False
        for name in ('setp', 'setn', 'pulse_in'):
            self.remove_pin(name)
