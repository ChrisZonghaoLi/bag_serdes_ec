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

        if seg_nand < 1:
            raise ValueError('seg_nand must be >= 1.')

        # design initialization related blocks
        if seg_set == 0:
            self.remove_pin('scan_s')
            self.remove_pin('en')
            for inst_name in ('XNORL', 'XNORR', 'XSCINV'):
                self.delete_instance(inst_name)
        else:
            dig_params = dict(
                nin=2,
                lch=lch,
                wp=w_dict['pl'],
                wn=w_dict['nl'],
                thp=th_dict['pl'],
                thn=th_dict['nl'],
                segp=seg_pnor,
                segn=seg_nnor,
            )
            self.instances['XNORL'].design(**dig_params)
            self.instances['XNORR'].design(**dig_params)
            del dig_params['nin']
            dig_params['segp'] = seg_psinv
            dig_params['segn'] = seg_nsinv
            self.instances['XSCINV'].design(**dig_params)

        # design inverters
        dig_params = dict(
            lch=lch,
            wp=w_dict['p'],
            wn=w_dict['n'],
            thp=th_dict['p'],
            thn=th_dict['n'],
            segp=seg_inv,
            segn=seg_inv,
        )
        self.instances['XRINV'].design(**dig_params)
        self.instances['XSINV'].design(**dig_params)

        # design transistors
        tran_info = [('XNDL', 'n', seg_drv), ('XNDR', 'n', seg_drv),
                     ('XSL', 's', seg_set), ('XSR', 's', seg_set),
                     ('XPDL', 'p', seg_drv), ('XPDR', 'p', seg_drv),
                     ]
        for name, row, seg in tran_info:
            if seg == 0:
                self.delete_instance(name)
            w = w_dict[row]
            th = th_dict[row]
            self.instances[name].design(w=w, l=lch, nf=seg, intent=th)

        # design stack transistors
        tran_info = [('XNNL0', 'n'), ('XNNL1', 'n'),
                     ('XNNR0', 'n'), ('XNNR1', 'n'),
                     ('XPNL0', 'p'), ('XPNL1', 'p'),
                     ('XPNR0', 'p'), ('XPNR1', 'p'),
                     ]
        seg_str = '<%d:0>' % (seg_nand - 1)
        for name, row in tran_info:
            w = w_dict[row]
            th = th_dict[row]
            self.instances[name].design(w=w, l=lch, nf=1, intent=th)
            if seg_nand > 1:
                # parallelize the segments
                new_name = name + seg_str
                idx = int(name[4])
                net = name[1:4] + seg_str
                if idx == 0:
                    new_term = dict(D=net)
                else:
                    new_term = dict(S=net)
                self.array_instance(name, [new_name], term_list=[new_term])
