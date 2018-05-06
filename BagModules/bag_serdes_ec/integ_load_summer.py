# -*- coding: utf-8 -*-

from typing import Dict

import os
import pkg_resources

from bag.design import Module


yaml_file = pkg_resources.resource_filename(__name__, os.path.join('netlist_info',
                                                                   'integ_load_summer.yaml'))


# noinspection PyPep8Naming
class bag_serdes_ec__integ_load_summer(Module):
    """Module for library bag_serdes_ec cell integ_load_summer.

    Fill in high level description here.
    """

    def __init__(self, bag_config, parent=None, prj=None, **kwargs):
        Module.__init__(self, bag_config, yaml_file, parent=parent, prj=prj, **kwargs)

    @classmethod
    def get_params_info(cls):
        # type: () -> Dict[str, str]
        return dict(
            load_params_list='load parameters list.',
            nin='number of inputs.',
        )

    def design(self, load_params_list, nin):
        num_load = len(load_params_list)
        if num_load > 1:
            load_name_list = ['XLOAD%d' % idx for idx in range(num_load)]
            self.array_instance('XLOAD', load_name_list)
            for inst, params in zip(self.instances['XLOAD'], load_params_list):
                inst.design(**params)
        else:
            self.instances['XLOAD'].design(**load_params_list[0])

        if nin > 1:
            suf = '<%d:0>' % (nin - 1)
            self.rename_pin('iip', 'iip' + suf)
            self.rename_pin('iin', 'iin' + suf)
            self.array_instance('XTHP', ['XTHP' + suf], term_list=[dict(src='iip' + suf)])
            self.array_instance('XTHN', ['XTHN' + suf], term_list=[dict(src='iin' + suf)])
