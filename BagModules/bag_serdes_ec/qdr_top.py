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
            dp_params='datapath parameters.',
        )

    def design(self, dp_params):
        self.instances['XDP'].design(**dp_params)
        pin_list = self.instances['XDP'].master.pin_list

        has_set = False
        num_ffe = num_dfe = 0
        for name in pin_list:
            if name.startswith('setp'):
                has_set = True
                # TODO: figure out the rest
            elif name.startswith('bias_ffe'):
                suffix = name[8:]
                max_idx = int(suffix[1:].split(':')[0])
                num_ffe = (max_idx + 1) // 4 - 1
            elif name.startswith('sgnp_dfe'):
                suffix = name[8:]
                max_idx = int(suffix[1:].split(':')[0])
                num_dfe = (max_idx + 1) // 4 - 1

        if num_ffe < 1:
            raise ValueError('Only support 1+ FFE.')
        if num_dfe < 2:
            raise ValueError('Only support 2+ DFE')

        if not has_set:
            self.remove_pin('setp')
            self.remove_pin('setn')
        for way_idx in range(4):
            for ffe_idx in range(2, num_ffe + 1):
                self.add_pin('bias_way%d_ffe_%d<7:0>' % (way_idx, ffe_idx), 'input')
            for dfe_idx in range(3, num_dfe + 1):
                self.add_pin('bias_way%d_dfe_%d_s<1:0>' % (way_idx, dfe_idx), 'input')
                self.add_pin('bias_way%d_dfe_%d_m<7:0>' % (way_idx, dfe_idx), 'input')
