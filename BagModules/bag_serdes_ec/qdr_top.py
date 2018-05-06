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
            fe_params='frontend parameters.',
            dac_params='dac parameters.',
        )

    def design(self, fe_params, dac_params):
        self.instances['XFE'].design(**fe_params)
        self.instances['XDAC'].design(**dac_params)
        pin_list = self.instances['XDAC'].master.pin_list

        for name in pin_list:
            self.reconnect_instance_terminal('XDAC', name, name)
            if name.startswith('v_'):
                self.reconnect_instance_terminal('XFE', name, name)

        fe_master = self.instances['XFE'].master
        has_set = fe_master.has_set
        num_ffe = fe_master.num_ffe
        num_dfe = fe_master.num_dfe

        if num_ffe < 1:
            raise ValueError('Only support 1+ FFE.')
        if num_dfe < 2:
            raise ValueError('Only support 2+ DFE')

        if not has_set:
            self.remove_pin('setp')
            self.remove_pin('setn')
        for way_idx in range(4):
            for ffe_idx in range(2, num_ffe + 1):
                self.add_pin('bias_way_%d_ffe_%d<7:0>' % (way_idx, ffe_idx), 'input')
            for dfe_idx in range(3, num_dfe + 1):
                sgn_name = 'bias_way_%d_dfe_%d_s<1:0>' % (way_idx, dfe_idx)
                self.add_pin(sgn_name, 'input')
                self.add_pin('bias_way_%d_dfe_%d_m<7:0>' % (way_idx, dfe_idx), 'input')
                self.reconnect_instance_terminal('XFE', sgn_name, sgn_name)
