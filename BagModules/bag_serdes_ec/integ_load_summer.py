# -*- coding: utf-8 -*-

from typing import Dict

import os
import pkg_resources

from bag.design import Module

from .integ_load import bag_serdes_ec__integ_load

yaml_file = pkg_resources.resource_filename(__name__, os.path.join('netlist_info',
                                                                   'integ_load_summer.yaml'))


# noinspection PyPep8Naming
class bag_serdes_ec__integ_load_summer(Module):
    """Module for library bag_serdes_ec cell integ_load_summer.

    Fill in high level description here.
    """

    def __init__(self, bag_config, parent=None, prj=None, **kwargs):
        Module.__init__(self, bag_config, yaml_file, parent=parent, prj=prj, **kwargs)
        self.has_clk = False
        self.has_en = False
        self.en_only = False

    @classmethod
    def get_params_info(cls):
        # type: () -> Dict[str, str]
        return dict(
            load_params_list='load parameters list.',
            nin='number of inputs.',
        )

    def get_master_basename(self):
        # type: () -> str
        return self.orig_cell_name + ('_nin%d' % self.params['nin'])

    def design(self, load_params_list, nin):
        load_name_list = []
        new_params_list = []
        num_load = 0
        for load_params in load_params_list:
            if not bag_serdes_ec__integ_load.is_empty(load_params['seg_dict'],
                                                      load_params['dum_info']):
                load_name_list.append('XLOAD%d' % num_load)
                new_params_list.append(load_params)
                num_load += 1

        if num_load == 0:
            self.delete_instance('XLOAD')
        elif num_load == 1:
            inst = self.instances['XLOAD']
            inst.design(**new_params_list[0])
            master = inst.master
            self.has_clk = master.has_clk
            self.has_en = master.has_en
            if master.en_only:
                self.en_only = True
                self.reconnect_instance_terminal('XLOAD', 'en<3>', 'en<3>')
        else:
            self.array_instance('XLOAD', load_name_list)
            for idx, (inst, params) in enumerate(zip(self.instances['XLOAD'], new_params_list)):
                inst.design(**params)
                master = inst.master
                self.has_clk |= master.has_clk
                self.has_en |= master.has_en
                if master.en_only:
                    self.en_only = True
                    self.reconnect_instance_terminal('XLOAD', 'en<3>', 'en<3>', index=idx)

        if nin > 1:
            suf = '<%d:0>' % (nin - 1)
            self.rename_pin('iip', 'iip' + suf)
            self.rename_pin('iin', 'iin' + suf)
            pname = self._get_arr_name('iip', nin)
            nname = self._get_arr_name('iin', nin)
            self.array_instance('XTHP', ['XTHP' + suf], term_list=[dict(src=pname)])
            self.array_instance('XTHN', ['XTHN' + suf], term_list=[dict(src=nname)])

        if not self.has_clk:
            self.remove_pin('clkp')
            self.remove_pin('clkn')
        if not self.has_en:
            self.remove_pin('en<3:2>')
        elif self.en_only:
            self.rename_pin('en<3:2>', 'en<3>')

    @classmethod
    def _get_arr_name(cls, base, n):
        return ','.join(('%s<%d>' % (base, idx) for idx in range(n - 1, -1, -1)))
