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
        self._num_ffe = None
        self._num_dfe = None
        self._has_hp = None

    @property
    def num_ffe(self):
        return self._num_ffe

    @property
    def num_dfe(self):
        return self._num_dfe

    @property
    def has_hp(self):
        return self._has_hp

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

        tapx_master = self.instances['XTAPX'].master
        self._num_ffe = tapx_master.num_ffe
        self._num_dfe = tapx_master.num_dfe
        self._has_hp = self.instances['XTAP1'].master.has_hp

        # handle FFE pins
        if self._num_ffe == 0:
            self.remove_pin('bias_ffe<7:4>')
        else:
            ffe_suf = '<%d:4>' % (4 * self._num_ffe + 3)
            new_name = 'bias_ffe' + ffe_suf
            self.rename_pin('bias_ffe<7:4>', new_name)
            new_net = self._get_arr_name('bias_ffe', 4, 4 * self._num_ffe + 4)
            self.reconnect_instance_terminal('XTAPX', 'casc' + ffe_suf, new_net)

        # handle DFE pins
        if self._num_dfe < 2:
            raise ValueError('Cannot handle < 2 DFE taps for now.')
        else:
            dfe_max_idx = 4 * self._num_dfe + 3
            dfe_suf = '<%d:8>' % dfe_max_idx
            dfe_net = self._get_arr_name('clk_dfe', 8, dfe_max_idx + 1)
            sgnp_name = 'sgnp_dfe' + dfe_suf
            sgnn_name = 'sgnn_dfe' + dfe_suf
            self.rename_pin('sgnp_dfe<11:8>', sgnp_name)
            self.rename_pin('sgnn_dfe<11:8>', sgnn_name)
            self.rename_pin('clk_dfe<11:4>', 'clk_dfe<%d:4>' % dfe_max_idx)
            self.reconnect_instance_terminal('XTAPX', 'sgnp' + dfe_suf, sgnp_name)
            self.reconnect_instance_terminal('XTAPX', 'sgnn' + dfe_suf, sgnn_name)
            self.reconnect_instance_terminal('XTAPX', 'bias_s' + dfe_suf, dfe_net)

    @classmethod
    def _get_arr_name(cls, base, start, stop, step=1):
        return ','.join(('%s<%d>' % (base, idx) for idx in range(stop - 1, start - 1, -step)))
