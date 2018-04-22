# -*- coding: utf-8 -*-

from typing import Dict, Any

import os
import pkg_resources

from bag.design import Module


yaml_file = pkg_resources.resource_filename(__name__, os.path.join('netlist_info',
                                                                   'sense_amp_strongarm.yaml'))


# noinspection PyPep8Naming
class bag_serdes_ec__sense_amp_strongarm(Module):
    """Module for library bag_serdes_ec cell sense_amp_strongarm.

    Fill in high level description here.
    """

    def __init__(self, bag_config, parent=None, prj=None, **kwargs):
        Module.__init__(self, bag_config, yaml_file, parent=parent, prj=prj, **kwargs)

    @classmethod
    def get_params_info(cls):
        # type: () -> Dict[str, str]
        return dict(
            lch='Channel length, in meters.',
            w_dict='width dictionary.',
            th_dict='threshold dictionary.',
            seg_dict='number of segments dictionary.',
            dum_info='Dummy information data structure.',
            export_probe='True to export probe pins.',
        )

    @classmethod
    def get_default_param_values(cls):
        # type: () -> Dict[str, Any]
        return dict(
            dum_info=None,
            export_probe=False,
        )

    def design(self, lch, w_dict, th_dict, seg_dict, dum_info, export_probe):
        if not export_probe:
            for name in ['midp', 'midn', 'qp', 'qn']:
                self.remove_pin(name)

        tran_info_list = [('XTAILL', 'tail'), ('XTAILR', 'tail'),
                          ('XINL', 'in'), ('XINR', 'in'),
                          ('XNINVL', 'ninv'), ('XNINVR', 'ninv'),
                          ('XPINVL', 'pinv'), ('XPINVR', 'pinv'),
                          ('XRML', 'pinv', 'rst'), ('XRMR', 'pinv', 'rst'),
                          ('XRIL', 'pinv', 'rst'), ('XRIR', 'pinv', 'rst'),
                          ]

        for inst_info in tran_info_list:
            w = w_dict[inst_info[1]]
            th = th_dict[inst_info[1]]
            if len(inst_info) < 3:
                seg = seg_dict[inst_info[1]]
            else:
                seg = seg_dict[inst_info[2]]
            self.instances[inst_info[0]].design(w=w, l=lch, nf=seg, intent=th)

        # design dummies
        self.design_dummy_transistors(dum_info, 'XDUM', 'VDD', 'VSS')

        # design NAND gates
        w_ninv = w_dict['ninv']
        w_pinv = w_dict['pinv']
        th_ninv = th_dict['ninv']
        th_pinv = th_dict['pinv']
        seg_nand = seg_dict['nand']
        self.instances['XNANDL'].design(nin=2, lch=lch, wp=w_pinv, wn=w_ninv,
                                        thp=th_pinv, thn=th_ninv, segp=seg_nand,
                                        segn=seg_nand)
        self.instances['XNANDR'].design(nin=2, lch=lch, wp=w_pinv, wn=w_ninv,
                                        thp=th_pinv, thn=th_ninv, segp=seg_nand,
                                        segn=seg_nand)

        # design buffers
        seg_buf = seg_dict['buf']
        self.instances['XINVL'].design(lch=lch, wp=w_pinv, wn=w_ninv, thp=th_pinv,
                                       thn=th_ninv, segp=seg_buf, segn=seg_buf)
        self.instances['XINVR'].design(lch=lch, wp=w_pinv, wn=w_ninv, thp=th_pinv,
                                       thn=th_ninv, segp=seg_buf, segn=seg_buf)
