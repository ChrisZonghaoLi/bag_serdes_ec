# -*- coding: utf-8 -*-

from typing import Dict, Any

import os
import pkg_resources

from bag.design import Module


yaml_file = pkg_resources.resource_filename(__name__, os.path.join('netlist_info',
                                                                   'ctle_passive.yaml'))


# noinspection PyPep8Naming
class bag_serdes_ec__ctle_passive(Module):
    """Module for library bag_serdes_ec cell ctle_passive.

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
            nr1='Number of series resistors connecting input to output.',
            nr2='Number of series resistors connecting output to outcm.',
            ndum='Number of dummy resistors.',
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

    def design(self, l, w, intent, nr1, nr2, ndum, res_in_info, res_out_info, sub_name):
        if nr1 < 0 or nr2 <= 0:
            raise ValueError('Illegal values of nr1 or nr2.')
        if not sub_name:
            raise ValueError('This block must have supply.')

        # handle substrate pin
        if sub_name != 'VSS':
            self.rename_pin('VSS', sub_name)
            rename_sub = True
        else:
            rename_sub = False

        # design dummy
        if ndum <= 0:
            self.delete_instance('RDUM')
        else:
            self.instances['RDUM'].design(w=w, l=l, intent=intent)
            if ndum > 1:
                if rename_sub:
                    term_list = [dict(BULK=sub_name)]
                else:
                    term_list = None
                self.array_instance('RDUM', ['RDUM<%d:0>' % (ndum - 1)], term_list=term_list)
            elif rename_sub:
                self.reconnect_instance_terminal('RDUM', 'BULK', sub_name)

        # design main resistors
        res_list = [('RP1', 'inpr', 'outpr', 'mid_inp', nr1),
                    ('RN1', 'innr', 'outnr', 'mid_inn', nr1),
                    ('RP2', 'outpr', 'outcm', 'mid_outp', nr2),
                    ('RN2', 'outnr', 'outcm', 'mid_outn', nr2)]
        for inst_name, in_name, out_name, mid_name, num in res_list:
            self.instances[inst_name].design(w=w, l=l, intent=intent)
            if num == 1:
                if rename_sub:
                    self.reconnect_instance_terminal(inst_name, 'BULK', sub_name)
            else:
                if num == 2:
                    pos_name = '%s,%s' % (in_name, mid_name)
                    neg_name = '%s,%s' % (mid_name, out_name)
                else:
                    pos_name = '%s,%s<%d:0>' % (in_name, mid_name, num - 2)
                    neg_name = '%s<%d:0>,%s' % (mid_name, num - 2, out_name)
                if rename_sub:
                    term_dict = dict(PLUS=pos_name, MINUS=neg_name, BULK=sub_name)
                else:
                    term_dict = dict(PLUS=pos_name, MINUS=neg_name)
                name_list = ['%s<%d:0>' % (inst_name, num - 1)]
                term_list = [term_dict]

                self.array_instance(inst_name, name_list, term_list=term_list)

        # design metal resistors
        names_list = [('RMIP', 'RMIN'), ('RMOP', 'RMON')]
        info_list = [res_in_info, res_out_info]
        for res_names, (res_lay, res_w, res_l) in zip(names_list, info_list):
            for name in res_names:
                self.instances[name].design(layer=res_lay, w=res_w, l=res_l)
