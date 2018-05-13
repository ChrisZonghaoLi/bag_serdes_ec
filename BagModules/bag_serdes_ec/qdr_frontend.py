# -*- coding: utf-8 -*-

from typing import Dict, Any

import os
import pkg_resources

from bag.design import Module


yaml_file = pkg_resources.resource_filename(__name__, os.path.join('netlist_info',
                                                                   'qdr_frontend.yaml'))


# noinspection PyPep8Naming
class bag_serdes_ec__qdr_frontend(Module):
    """Module for library bag_serdes_ec cell qdr_frontend.

    Fill in high level description here.
    """

    def __init__(self, bag_config, parent=None, prj=None, **kwargs):
        Module.__init__(self, bag_config, yaml_file, parent=parent, prj=prj, **kwargs)
        self._num_ffe = None
        self._num_dfe = None

    @property
    def num_ffe(self):
        return self._num_ffe

    @property
    def num_dfe(self):
        return self._num_dfe

    @classmethod
    def get_params_info(cls):
        # type: () -> Dict[str, str]
        return dict(
            ctle_params='CTLE parameters.',
            tapx_params='TapX summer parmeters.',
            off_params='Offset cancel parameters.',
            tap1_params='Tap1 summer parameters.',
            loff_params='dlev offset parameters.',
            samp_params='sampler parameters.',
            hp_params='high-pass filter parameters.',
            ndum_res='number of dummy resistors total.',
            export_probe='True to export probe ports.',
        )

    @classmethod
    def get_default_param_values(cls):
        # type: () -> Dict[str, Any]
        return dict(
            export_probe=False,
        )

    def design(self, ctle_params, tapx_params, off_params, tap1_params, loff_params, samp_params,
               hp_params, ndum_res, export_probe):
        # design instances
        self.instances['XCTLE'].design(**ctle_params)
        self.instances['XDP'].design(tapx_params=tapx_params, off_params=off_params,
                                     tap1_params=tap1_params, loff_params=loff_params,
                                     samp_params=samp_params)

        # design resistor dummies
        l = hp_params['l']
        w = hp_params['w']
        intent = hp_params['intent']
        sub_name = hp_params['sub_name']
        self.instances['XRDUM'].design(l=l, w=w, intent=intent, ndum=ndum_res, sub_name=sub_name)

        # design high-pass filters that are always there
        for name in ('XHPA<3:0>', 'XHPDLX<3:0>', 'XHPDL1<3:0>', 'XHPTAP1<3:0>'):
            self.instances[name].design(**hp_params)

        # modify pins and update connections
        dp_master = self.instances['XDP'].master
        self._num_ffe = dp_master.num_ffe
        self._num_dfe = dp_master.num_dfe
        has_hp = dp_master.has_hp

        # handle FFE pins
        way_order = (0, 3, 2, 1)
        if self._num_ffe == 0:
            for way_idx in range(4):
                self.remove_pin('v_way_%d_ffe_1' % way_idx)
        elif self._num_ffe > 1:
            raise ValueError('More than 1 FFE taps not supported yet.')

        if self._num_dfe < 2:
            raise ValueError('Cannot handle < 2 DFE taps for now.')

        # add new DFE pins
        for way_idx in range(4):
            for dfe_idx in range(3, self._num_dfe + 1):
                self.add_pin('bias_way_%d_dfe_%d_s<1:0>' % (way_idx, dfe_idx), 'input')
                self.add_pin('v_way_%d_dfe_%d_m' % (way_idx, dfe_idx), 'input')
        max_dfe_idx = 4 * self._num_dfe + 3
        # connect sign bits
        dfe_suf = '<%d:8>' % max_dfe_idx
        sgnp_term = 'sgnp_dfe' + dfe_suf
        sgnn_term = 'sgnn_dfe' + dfe_suf
        sgnp_nets = []
        sgnn_nets = []
        for dfe_idx in range(self._num_dfe, 1, -1):
            for way_idx in way_order:
                sgnp_nets.append('bias_way_%d_dfe_%d_s<0>' % (way_idx, dfe_idx))
                sgnn_nets.append('bias_way_%d_dfe_%d_s<1>' % (way_idx, dfe_idx))
        self.reconnect_instance_terminal('XDP', sgnp_term, ','.join(sgnp_nets))
        self.reconnect_instance_terminal('XDP', sgnn_term, ','.join(sgnn_nets))

        # handle probe exports
        if export_probe:
            self.add_pin('clk_analog<3:0>', 'output')
            self.add_pin('clk_digital_tapx<3:0>', 'output')
            self.add_pin('clk_digital_tap1<3:0>', 'output')
            self.add_pin('clk_tap1<3:0>', 'output')
            self.add_pin('clk_main<3:0>', 'output')
            self.add_pin('clk_dfe<%d:4>' % (self._num_dfe * 4 + 3), 'output')

        # handle high pass filters
        if has_hp:
            self.delete_instance('XHPD<3:0>')
            self.instances['XHPM<3:0>'].design(**hp_params)

            # handle DFE
            dfe_term = 'clk_dfe<%d:4>' % max_dfe_idx
            dfe_nets = []
            for dfe_idx in range(self._num_dfe, 1, -1):
                for way_idx in way_order:
                    dfe_nets.append('v_way_%d_dfe_%d_m' % (way_idx, dfe_idx))
            # way order for tap 1 is different
            for way_idx in (1, 0, 3, 2):
                dfe_nets.append('v_way_%d_dfe_1_m' % way_idx)
            self.reconnect_instance_terminal('XDP', dfe_term, ','.join(dfe_nets))
        else:
            # design high-pass filters
            for name in ('XHPM<3:0>', 'XHPD<3:0>'):
                self.instances[name].design(**hp_params)

            # connect DFE clocks
            term_name = 'clk_dfe<%d:4>' % max_dfe_idx
            self.reconnect_instance_terminal('XDP', term_name, term_name)

            if self._num_dfe > 1:
                # array high-pass filters
                name_list = []
                term_list = []
                for dfe_idx in range(1, self._num_dfe + 1):
                    name_list.append('XHPD%d<3:0>' % dfe_idx)
                    if dfe_idx == 1:
                        term_list.append(None)
                    else:
                        bias_nets = []
                        for way_idx in way_order:
                            bias_nets.append('v_way_%d_dfe_%d_m' % (way_idx, dfe_idx))
                        clk_name = 'clk_dfe<%d:%d>' % (dfe_idx * 4 + 3, dfe_idx * 4)
                        term_dict = {'in': 'clkp,clkn,clkp,clkn', 'out': clk_name,
                                     'VSS': 'VSS', 'bias': ','.join(bias_nets)}
                        term_list.append(term_dict)
                self.array_instance('XHPD<3:0>', name_list, term_list=term_list)
