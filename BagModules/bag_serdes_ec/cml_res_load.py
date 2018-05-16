# -*- coding: utf-8 -*-

from typing import Dict, Any

import os
import pkg_resources

from bag.design import Module


yaml_file = pkg_resources.resource_filename(__name__, os.path.join('netlist_info',
                                                                   'cml_res_load.yaml'))


# noinspection PyPep8Naming
class bag_serdes_ec__cml_res_load(Module):
    """Module for library bag_serdes_ec cell cml_res_load.

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
            npar='number of resistors in parallel.',
            ndum='number of dummy resistors.',
            sub_name='substrate name.  Empty string to disable.',
        )

    @classmethod
    def get_default_param_values(cls):
        # type: () -> Dict[str, Any]
        return dict(
            sub_name='VSS',
        )

    def design(self, l, w, intent, npar, ndum, sub_name):
        if ndum < 0 or npar <= 0:
            raise ValueError('Illegal values of ndum or npar.')
        if not sub_name:
            raise ValueError('sub_name must be non-empty.')

        # handle substrate pin
        rename_flag = (sub_name != 'VSS')
        if rename_flag:
            self.rename_pin('VSS', sub_name)

        # design dummy
        if ndum == 0:
            self.delete_instance('XRDUM')
        else:
            self.instances['XRDUM'].design(w=w, l=l, intent=intent)
            if ndum > 1:
                if rename_flag:
                    term_list = [dict(BULK=sub_name)]
                else:
                    term_list = None
                self.array_instance('XRDUM', ['XRDUM<%d:0>' % (ndum - 1)], term_list=term_list)
            elif rename_flag:
                self.reconnect_instance_terminal('XRDUM', 'BULK', sub_name)

        # design main resistors
        self.instances['XR'].design(w=w, l=l, intent=intent)
        if npar == 1:
            if rename_flag:
                self.reconnect_instance_terminal('XR', 'BULK', sub_name)
        else:
            if rename_flag:
                term_list = [dict(BULK=sub_name)]
            else:
                term_list = None
            self.array_instance('XR', ['XR<%d:0>' % (npar - 1)], term_list=term_list)
