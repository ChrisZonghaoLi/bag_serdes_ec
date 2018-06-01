# -*- coding: utf-8 -*-

from typing import Dict, Any

import os
import pkg_resources

from bag.design import Module


yaml_file = pkg_resources.resource_filename(__name__, os.path.join('netlist_info', 'integ_gm.yaml'))


# noinspection PyPep8Naming
class bag_serdes_ec__integ_gm(Module):
    """Module for library bag_serdes_ec cell integ_gm.

    Fill in high level description here.
    """

    def __init__(self, bag_config, parent=None, prj=None, **kwargs):
        Module.__init__(self, bag_config, yaml_file, parent=parent, prj=prj, **kwargs)
        self.has_set = False
        self.has_casc = False
        self.has_but = False
        self.has_tsw = False

    @classmethod
    def get_params_info(cls):
        # type: () -> Dict[str, str]
        return dict(
            lch='channel length, in meters.',
            w_dict='NMOS/PMOS width dictionary.',
            th_dict='NMOS/PMOS threshold flavor dictionary.',
            seg_dict='number of segments dictionary.',
            hp_params='high-pass parameters.  If None, delete it.',
            dum_info='Dummy information data structure.',
            export_probe='True to export probe ports.',
        )

    @classmethod
    def get_default_param_values(cls):
        # type: () -> Dict[str, Any]
        return dict(
            hp_params=None,
            dum_info=None,
            export_probe=False,
            is_model=False,
        )

    def get_master_basename(self):
        # type: () -> str
        seg_dict = self.params['seg_dict']

        if seg_dict.get('casc', 0) > 0:
            name = self.orig_cell_name + '_cascode'
        elif seg_dict.get('but', 0) > 0:
            name = self.orig_cell_name + '_butterfly'
        else:
            name = self.orig_cell_name

        if self.params['hp_params'] is not None:
            name += '_hp'
        return name

    def design(self, lch, w_dict, th_dict, seg_dict, hp_params, dum_info, export_probe):
        seg_set = seg_dict.get('set', 0)
        seg_sen = seg_dict.get('sen', 0)
        seg_casc = seg_dict.get('casc', 0)
        seg_casc1 = seg_dict.get('but', 0)
        seg_tsw = seg_dict.get('tsw', 0)
        seg_cap = seg_dict.get('cap', 0)
        stack_in = seg_dict.get('stack_in', 1)

        if seg_casc > 0 and seg_casc1 > 0:
            raise ValueError('Cannot have both cascode transistor and butterfly switch.')

        seg_casc0 = max(seg_casc, seg_casc1)
        tran_info_list = [('XTAILP', 'tail'), ('XTAILN', 'tail'),
                          ('XNENP', 'nen'), ('XNENN', 'nen'),
                          ('XCASP0', 'casc', seg_casc0), ('XCASN0', 'casc', seg_casc0),
                          ('XCASP1', 'casc', seg_casc1), ('XCASN1', 'casc', seg_casc1),
                          ('XSETP', 'in', seg_set), ('XSETN', 'in', seg_set),
                          ('XSENP', 'nen', seg_sen), ('XSENN', 'nen', seg_sen),
                          ('XTSW', 'nen', seg_tsw),
                          ]

        for inst_info in tran_info_list:
            if len(inst_info) <= 2:
                inst_name, inst_type = inst_info
                seg = seg_dict.get(inst_type, 0)
            else:
                inst_name, inst_type, seg = inst_info
            w = w_dict.get(inst_type, 0)
            th = th_dict.get(inst_type, 'standard')
            if seg <= 0:
                self.delete_instance(inst_name)
            else:
                self.instances[inst_name].design(w=w, l=lch, nf=seg, intent=th)

        seg_in = seg_dict['in']
        w_in = w_dict['in']
        th_in = th_dict['in']
        self.instances['XINP'].design(w=w_in, l=lch, seg=seg_in, intent=th_in, stack=stack_in)
        self.instances['XINN'].design(w=w_in, l=lch, seg=seg_in, intent=th_in, stack=stack_in)

        if seg_cap > 0:
            self.instances['XCAPL'].design(w=w_in, l=lch, seg=seg_cap, intent=th_in, stack=2)
            self.instances['XCAPR'].design(w=w_in, l=lch, seg=seg_cap, intent=th_in, stack=2)
        else:
            self.delete_instance('XCAPL')
            self.delete_instance('XCAPR')

        if seg_casc > 0:
            self.has_casc = True
            self.rename_pin('casc<1:0>', 'casc')
            self.reconnect_instance_terminal('XCASP0', 'G', 'casc')
            self.reconnect_instance_terminal('XCASN0', 'G', 'casc')
        elif seg_casc1 <= 0:
            self.remove_pin('casc<1:0>')
            self.reconnect_instance_terminal('XINP', 'D', 'outp')
            self.reconnect_instance_terminal('XINN', 'D', 'outn')
        else:
            self.has_but = True

        if seg_set <= 0:
            for name in ('setp', 'setn', 'pulse'):
                self.remove_pin(name)
        else:
            self.has_set = True

        if seg_tsw <= 0:
            self.remove_pin('clkn')
            self.remove_pin('VDD')
        else:
            self.has_tsw = True

        self.design_dummy_transistors(dum_info, 'XDUM', 'VDD', 'VSS')
        if not export_probe:
            self.remove_pin('tail')
            self.remove_pin('foot')

        if hp_params is None:
            self.delete_instance('XHP')
            self.remove_pin('clkp')
            self.reconnect_instance_terminal('XTAILP', 'G', 'biasp')
            self.reconnect_instance_terminal('XTAILN', 'G', 'biasp')
        else:
            self.instances['XHP'].design(**hp_params)
