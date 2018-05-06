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

    def __init__(self, bag_config, parent=None, prj=None, **kwargs):
        Module.__init__(self, bag_config, yaml_file, parent=parent, prj=prj, **kwargs)
        self._num_ffe = None
        self._num_dfe = None
        self._has_set = None

    @property
    def num_ffe(self):
        return self._num_ffe

    @property
    def num_dfe(self):
        return self._num_dfe

    @property
    def has_set(self):
        return self._has_set

    @classmethod
    def get_params_info(cls):
        # type: () -> Dict[str, str]
        return dict(
            div_params='Divider column parameters.',
            ffe_params_list='List of FFE summer cell parameters.',
            dfe_params_list='List of DFE summer cell parameters.',
            last_params_list='List of last summer cell parameters, from bottom to top.',
            export_probe='True to export probe ports.',
        )

    @classmethod
    def get_default_param_values(cls):
        # type: () -> Dict[str, Any]
        return dict(
            export_probe=False,
        )

    def design(self, div_params, ffe_params_list, dfe_params_list, last_params_list, export_probe):
        # design divider
        self.instances['XDIV'].design(**div_params)

        num_ffe = len(ffe_params_list)
        num_dfe = len(dfe_params_list) + 2
        self._num_ffe = num_ffe - 1
        self._num_dfe = num_dfe

        if not export_probe:
            self.remove_pin('en<3:0>')

        if num_dfe == 2 or num_dfe == 3:
            # TODO: add support for 2 or 3 taps.
            raise NotImplementedError('Did not implement 2/3 taps schematic generator yet.')

        # design instances
        for idx, name in enumerate(['X3', 'X0', 'X2', 'X1']):
            self.instances[name].design(ffe_params_list=ffe_params_list,
                                        dfe_params_list=dfe_params_list,
                                        last_params=last_params_list[idx])

        # rename pins
        max_ffe = 4 * (num_ffe - 1)
        if num_ffe == 1:
            self.remove_pin('casc<3:0>')
        else:
            self.rename_pin('casc<3:0>', 'casc<%d:4>' % (max_ffe + 3))

        max_dfe = 4 * num_dfe
        dfe_suf = '<%d:8>' % (max_dfe + 3)
        self.rename_pin('sgnp<3:0>', 'sgnp' + dfe_suf)
        self.rename_pin('sgnn<3:0>', 'sgnn' + dfe_suf)
        self.rename_pin('bias_s<3:0>', 'bias_s' + dfe_suf)

        # remove pins if not needed
        if 'pulse_in' not in self.instances['X0'].master.pin_list:
            self._has_set = False
            self.remove_pin('setp')
            self.remove_pin('setn')
        else:
            # TODO: handle setp/setn logic
            self._has_set = True
            pass

        # reconnect pins
        a_suf = '<%d:0>' % (num_ffe - 1)
        casc_pin = 'casc<1>' if num_ffe == 2 else 'casc<%d:1>' % (num_ffe - 1)
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
