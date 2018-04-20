# -*- coding: utf-8 -*-

from typing import Dict, Any

import os
import pkg_resources

from bag.design import Module


yaml_file = pkg_resources.resource_filename(__name__, os.path.join('netlist_info',
                                                                   'qdr_highpass_column.yaml'))


# noinspection PyPep8Naming
class bag_serdes_ec__qdr_highpass_column(Module):
    """Module for library bag_serdes_ec cell qdr_highpass_column.

    Fill in high level description here.
    """

    def __init__(self, bag_config, parent=None, prj=None, **kwargs):
        Module.__init__(self, bag_config, yaml_file, parent=parent, prj=prj, **kwargs)

    @classmethod
    def get_params_info(cls):
        # type: () -> Dict[str, str]
        return dict(
            l='unit resistor length, in meters.',
            w='unit resistor width, in meters.',
            intent='resistor type.',
            nser='number of resistors in series in a branch.',
            ndum='number of dummy resistors.',
            res_in_info='input metal resistor information.',
            res_out_info='output metal resistor information.',
            sub_name='substrate name.  Empty string to disable.',
        )

    @classmethod
    def get_default_param_values(cls):
        # type: () -> Dict[str, Any]
        return dict(
            sub_name='VSS',
        )

    def design(self, l, w, intent, nser, ndum, res_in_info, res_out_info, sub_name):
        rename = False
        if not sub_name:
            self.remove_pin('VSS')
        elif sub_name != 'VSS':
            if sub_name == 'VDD':
                self.remove_pin('VSS')
            else:
                self.rename_pin('VSS', sub_name)
                rename = True

        for idx in range(4):
            name = 'X%d' % idx
            self.instances[name].design(l=l, w=w, intent=intent, nser=nser, ndum=ndum,
                                        res_in_info=res_in_info, res_out_info=res_out_info,
                                        sub_name=sub_name)
            if rename:
                self.reconnect_instance_terminal(name, sub_name, sub_name)
