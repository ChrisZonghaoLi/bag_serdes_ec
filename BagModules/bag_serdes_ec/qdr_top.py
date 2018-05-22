# -*- coding: utf-8 -*-

from typing import Dict

import os
import pkg_resources

from bag.design import Module


yaml_file = pkg_resources.resource_filename(__name__, os.path.join('netlist_info', 'qdr_top.yaml'))


# noinspection PyPep8Naming
class bag_serdes_ec__qdr_top(Module):
    """Module for library bag_serdes_ec cell qdr_top.

    Fill in high level description here.
    """

    def __init__(self, bag_config, parent=None, prj=None, **kwargs):
        Module.__init__(self, bag_config, yaml_file, parent=parent, prj=prj, **kwargs)

    @classmethod
    def get_params_info(cls):
        # type: () -> Dict[str, str]
        return dict(
            term_params='termination parameters.',
            fe_params='frontend parameters.',
            dac_params='dac parameters.',
            bufb_params='bottom scan buffer parameters.',
            buft_params='top scan buffer parameters.',
        )

    def design(self, term_params, fe_params, dac_params, bufb_params, buft_params):
        # design instances
        self.instances['XFE'].design(**fe_params)
        self.instances['XDAC'].design(**dac_params)
        self.instances['XBUFB'].design(**bufb_params)
        self.instances['XBUFT'].design(**buft_params)
        self.instances['XTERM'].design(**term_params)
        pin_list = self.instances['XDAC'].master.pin_list

        # connect DAC/FE bias signals
        for name in pin_list:
            self.reconnect_instance_terminal('XDAC', name, name)
            if name.startswith('v_'):
                self.reconnect_instance_terminal('XFE', name, name)

        fe_master = self.instances['XFE'].master
        num_ffe = fe_master.num_ffe
        num_dfe = fe_master.num_dfe

        if num_ffe < 1:
            raise ValueError('Only support 1+ FFE.')
        if num_dfe < 2:
            raise ValueError('Only support 2+ DFE')

        # add new pins
        for way_idx in range(4):
            for ffe_idx in range(2, num_ffe + 1):
                self.add_pin('bias_way_%d_ffe_%d<7:0>' % (way_idx, ffe_idx), 'input')
            for dfe_idx in range(3, num_dfe + 1):
                sgn_name = 'bias_way_%d_dfe_%d_s<1:0>' % (way_idx, dfe_idx)
                self.add_pin(sgn_name, 'input')
                self.add_pin('bias_way_%d_dfe_%d_m<7:0>' % (way_idx, dfe_idx), 'input')

        # connect scan signals to buffer array
        for inst_name, is_bot in (('XBUFB', True), ('XBUFT', False)):
            out_scan_names = []
            num_bits = 0
            in_scan_names = []
            for name, nbit in self._scan_name_iter(num_dfe, is_bot=is_bot):
                cur_out = 'buf_' + name
                out_scan_names.append(cur_out)
                num_bits += nbit
                self.reconnect_instance_terminal('XFE', name, cur_out)
                in_scan_names.append(name)

            suf = '<%d:0>' % (num_bits - 1)
            in_names = ','.join(in_scan_names)
            out_names = ','.join(out_scan_names)
            self.reconnect_instance_terminal(inst_name, 'in' + suf, in_names)
            self.reconnect_instance_terminal(inst_name, 'out' + suf, out_names)

    @classmethod
    def _scan_name_iter(cls, num_dfe, is_bot=False):
        if is_bot:
            ways = (3, 0)
            sgn = 'n'
        else:
            ways = (2, 1)
            sgn = 'p'

        for dfe_idx in range(num_dfe, 1, -1):
            for way in ways:
                yield ('bias_way_%d_dfe_%d_s<1:0>' % (way, dfe_idx)), 2
        yield ('scan_divider_clk' + sgn), 1
        if is_bot:
            yield 'enable_divider', 1
