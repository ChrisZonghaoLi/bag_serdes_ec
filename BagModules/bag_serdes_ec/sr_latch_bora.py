# -*- coding: utf-8 -*-

from typing import Dict

import os
import pkg_resources

from bag.design import Module


yaml_file = pkg_resources.resource_filename(__name__, os.path.join('netlist_info',
                                                                   'sr_latch_bora.yaml'))


# noinspection PyPep8Naming
class bag_serdes_ec__sr_latch_bora(Module):
    """Module for library bag_serdes_ec cell sr_latch_bora.

    The Nikolic static SR latch with balanced output delay.
    """

    def __init__(self, bag_config, parent=None, prj=None, **kwargs):
        Module.__init__(self, bag_config, yaml_file, parent=parent, prj=prj, **kwargs)

    @classmethod
    def get_params_info(cls):
        # type: () -> Dict[str, str]
        return dict(
            lch='channel length, in meters.',
            w_dict='NMOS/PMOS width dictionary.',
            th_dict='NMOS/PMOS threshold flavor dictionary.',
            seg_dict='number of segments dictionary.',
        )

    def design(self, lch, w_dict, th_dict, seg_dict):
        seg_nand = seg_dict['nand']
        seg_inv = seg_dict['inv']
        seg_drv = seg_dict['drv']
        seg_set = seg_dict.get('set', 0)
        seg_pnor = seg_dict.get('pnor', 0)
        seg_nnor = seg_dict.get('nnor', 0)
        seg_nsinv = seg_dict.get('nsinv', 0)
        seg_psinv = seg_dict.get('psinv', 0)

        if seg_set == 0:
            self.remove_pin('scan_s')
            self.remove_pin('en')

        tran_info = [('XNDL', 'n', seg_drv), ('XNDR', 'n', seg_drv),
                     ('XNINVL', 'n', seg_inv), ('XNINVR', 'n', seg_inv),
                     ('XNNL0', 'n', seg_nand), ('XNNL1', 'n', seg_nand),
                     ('XNNR0', 'n', seg_nand), ('XNNR1', 'n', seg_nand),
                     ('XSL', 's', seg_set), ('XSR', 's', seg_set),
                     ('XNOL0', 'nl', seg_nnor), ('XNOL1', 'nl', seg_nnor),
                     ('XNOR0', 'nl', seg_nnor), ('XNOR1', 'nl', seg_nnor),
                     ('XNSINV', 'nl', seg_nsinv),
                     ('XPDL', 'p', seg_drv), ('XPDR', 'p', seg_drv),
                     ('XPINVL', 'p', seg_inv), ('XPINVR', 'p', seg_inv),
                     ('XPNL0', 'p', seg_nand), ('XPNL1', 'p', seg_nand),
                     ('XPNR0', 'p', seg_nand), ('XPNR1', 'p', seg_nand),
                     ('XPOL0', 'pl', seg_pnor), ('XPOL1', 'pl', seg_pnor),
                     ('XPOR0', 'pl', seg_pnor), ('XPOR1', 'pl', seg_pnor),
                     ('XPSINV', 'pl', seg_psinv),
                     ]
        for name, row, seg in tran_info:
            if seg == 0:
                self.delete_instance(name)
            w = w_dict[row]
            th = th_dict[row]
            self.instances[name].design(w=w, l=lch, nf=seg, intent=th)
