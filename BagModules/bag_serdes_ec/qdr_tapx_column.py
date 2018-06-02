# -*- coding: utf-8 -*-

from typing import Dict, Any

import os
import pkg_resources

from bag.design import Module

yaml_file = pkg_resources.resource_filename(__name__, os.path.join('netlist_info',
                                                                   'qdr_tapx_column.yaml'))


# noinspection PyPep8Naming
class bag_serdes_ec__qdr_tapx_column(Module):
    """Module for library bag_serdes_ec cell qdr_tapx_column.

    Fill in high level description here.
    """

    probe_names = ['en<3:0>', 'outp_a<3:0>', 'outn_a<3:0>', 'outp_d<3:0>', 'outn_d<3:0>']

    def __init__(self, bag_config, parent=None, prj=None, **kwargs):
        Module.__init__(self, bag_config, yaml_file, parent=parent, prj=prj, **kwargs)
        self.num_ffe = None
        self.num_dfe = None
        self.probe_suf_ffe = None
        self.probe_dfe_max_idx = None

    @classmethod
    def get_params_info(cls):
        # type: () -> Dict[str, str]
        return dict(
            div_params='divider column parameters.',
            ffe_params_list='List of FFE summer cell parameters.',
            dfe_params_list='List of DFE summer cell parameters.',
            dfe2_params='DFE tap2 gm/load parameters.',
            export_probe='True to export probe ports.',
        )

    @classmethod
    def get_default_param_values(cls):
        # type: () -> Dict[str, Any]
        return dict(
            export_probe=False,
        )

    def design(self, div_params, ffe_params_list, dfe_params_list, dfe2_params, export_probe):
        num_ffe = len(ffe_params_list)
        if dfe_params_list is None:
            num_dfe = -1
            self.num_dfe = 0
        else:
            self.num_dfe = num_dfe = len(dfe_params_list) + 2
        self.num_ffe = num_ffe - 1

        if num_dfe == 2 or num_dfe == 3:
            # TODO: add support for 2 or 3 taps.
            raise NotImplementedError('Did not implement 2/3 taps schematic generator yet.')

        # design divider
        self.instances['XDIVL'].design(**div_params)
        if num_dfe < 0:
            self.delete_instance('XDIVR')
        else:
            self.instances['XDIVR'].design(**div_params)

        max_ffe = 4 * (num_ffe - 1)
        max_dfe = 0 if num_dfe < 0 else 4 * num_dfe
        # handle probe ports
        if export_probe:
            self.probe_suf_ffe = asuf = '<%d:0>' % (max_ffe + 3)
            self.rename_pin('outp_a<3:0>', 'outp_a' + asuf)
            self.rename_pin('outn_a<3:0>', 'outn_a' + asuf)
            if num_dfe < 3:
                self.remove_pin('outp_d<3:0>')
                self.remove_pin('outn_d<3:0>')
            else:
                self.probe_dfe_max_idx = max_dfe + 3
                dsuf = '<%d:12>' % (max_dfe + 3)
                self.rename_pin('outp_d<3:0>', 'outp_d' + dsuf)
                self.rename_pin('outn_d<3:0>', 'outn_d' + dsuf)
        else:
            for name in self.probe_names:
                self.remove_pin(name)
        # design instances
        for idx in range(4):
            inst_name = 'X%d' % idx
            inst = self.instances[inst_name]
            inst.design(ffe_params_list=ffe_params_list, dfe_params_list=dfe_params_list,
                        dfe2_params=dfe2_params)
            if inst.master.en_only:
                net_name = 'en<%d>,en<%d>' % (idx, (idx - 1) % 4)
                self.reconnect_instance_terminal(inst_name, 'en<3:2>', net_name)

        # rename pins
        if num_ffe == 1:
            self.remove_pin('casc<3:0>')
        else:
            self.rename_pin('casc<3:0>', 'casc<%d:4>' % (max_ffe + 3))

        if num_dfe < 0:
            for name in ('sgnp<3:0>', 'sgnn<3:0>', 'bias_s<3:0>', 'inp_d<3:0>', 'inn_d<3:0>',
                         'bias_d<3:0>'):
                self.remove_pin(name)
        else:
            dfe_suf = '<%d:8>' % (max_dfe + 3)
            self.rename_pin('sgnp<3:0>', 'sgnp' + dfe_suf)
            self.rename_pin('sgnn<3:0>', 'sgnn' + dfe_suf)
            self.rename_pin('bias_s<3:0>', 'bias_s' + dfe_suf)

        # reconnect pins
        a_suf = '<%d:0>' % (num_ffe - 1)
        casc_pin = 'casc' if num_ffe == 2 else 'casc<%d:1>' % (num_ffe - 1)
        d_suf = '<%d:2>' % num_dfe
        do_suf = '<%d:3>' % num_dfe
        for cidx in range(4):
            pcidx = (cidx + 1) % 4
            ncidx = (cidx - 1) % 4
            name = 'X%d' % cidx
            # FFE related pins
            if num_ffe == 1:
                self.reconnect_instance_terminal(name, 'inp_a<0>', 'inp_a')
                self.reconnect_instance_terminal(name, 'inn_a<0>', 'inn_a')
                self.reconnect_instance_terminal(name, 'outp_a<0>', 'outp_a<%d>' % cidx)
                self.reconnect_instance_terminal(name, 'outn_a<0>', 'outn_a<%d>' % cidx)
            else:
                if num_ffe == 2:
                    casc_net = 'casc<%d>' % (4 + ncidx)
                else:
                    casc_net = 'casc<%d:%d:4>' % (max_ffe + ncidx, 4 + ncidx)
                self.reconnect_instance_terminal(name, casc_pin, casc_net)
                if num_ffe == 2:
                    self.reconnect_instance_terminal(name, 'inp_a<1:0>',
                                                     'inp_a,outp_a<%d>' % (4 + pcidx))
                    self.reconnect_instance_terminal(name, 'inn_a<1:0>',
                                                     'inn_a,outn_a<%d>' % (4 + pcidx))
                else:
                    cur_a_suf = '<%d:%d:4>' % (max_ffe + pcidx, 4 + pcidx)
                    self.reconnect_instance_terminal(name, 'inp_a' + a_suf,
                                                     'inp_a,outp_a' + cur_a_suf)
                    self.reconnect_instance_terminal(name, 'inn_a' + a_suf,
                                                     'inn_a,outn_a' + cur_a_suf)
                cur_a_suf = '<%d:%d:4>' % (max_ffe + cidx, cidx)
                self.reconnect_instance_terminal(name, 'outp_a' + a_suf, 'outp_a' + cur_a_suf)
                self.reconnect_instance_terminal(name, 'outn_a' + a_suf, 'outn_a' + cur_a_suf)

            # DFE related pins
            if num_dfe >= 0:
                cur_d_suf = '<%d:%d:4>' % (max_dfe + cidx, 12 + cidx)
                self.reconnect_instance_terminal(name, 'outp_d' + do_suf, 'outp_d' + cur_d_suf)
                self.reconnect_instance_terminal(name, 'outn_d' + do_suf, 'outn_d' + cur_d_suf)
                cur_d_suf = '<%d:%d:4>' % (max_dfe - 4 + pcidx, 12 + pcidx)
                net = 'out{0}_d%s,in{0}_d<%d>,in{0}_d<%d>' % (cur_d_suf, pcidx, cidx)
                self.reconnect_instance_terminal(name, 'inp_d' + d_suf, net.format('p'))
                self.reconnect_instance_terminal(name, 'inn_d' + d_suf, net.format('n'))
                cur_d_suf = '<%d:%d:4>' % (max_dfe + ncidx, 8 + ncidx)
                self.reconnect_instance_terminal(name, 'biasn_s' + d_suf, 'bias_s' + cur_d_suf)
                self.reconnect_instance_terminal(name, 'sgnp' + d_suf, 'sgnp' + cur_d_suf)
                self.reconnect_instance_terminal(name, 'sgnn' + d_suf, 'sgnn' + cur_d_suf)
