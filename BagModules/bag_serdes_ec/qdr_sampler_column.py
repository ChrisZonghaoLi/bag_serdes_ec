# -*- coding: utf-8 -*-

from typing import Dict, Any

import os
import pkg_resources

from bag.design import Module


yaml_file = pkg_resources.resource_filename(__name__, os.path.join('netlist_info',
                                                                   'qdr_sampler_column.yaml'))


# noinspection PyPep8Naming
class bag_serdes_ec__qdr_sampler_column(Module):
    """Module for library bag_serdes_ec cell qdr_sampler_column.

    Fill in high level description here.
    """

    def __init__(self, bag_config, parent=None, prj=None, **kwargs):
        Module.__init__(self, bag_config, yaml_file, parent=parent, prj=prj, **kwargs)

    @classmethod
    def get_params_info(cls):
        # type: () -> Dict[str, str]
        return dict(
            sa_params='sense-amp column parameters.',
            div_params='divider column parameters.',
            re_params='retimer column parameters.',
            export_probe='True to export probe ports.',
        )

    @classmethod
    def get_default_param_values(cls):
        # type: () -> Dict[str, Any]
        return dict(
            export_probe=False,
        )

    def design(self, sa_params, div_params, re_params, export_probe):
        self.instances['XSA'].design(**sa_params)
        self.instances['XDIV'].design(**div_params)
        self.instances['XRE'].design(**re_params)

        if not export_probe:
            self.remove_pin('en<3:0>')
            self.remove_pin('sa_data<3:0>')
            self.remove_pin('sa_dlev<3:0>')
