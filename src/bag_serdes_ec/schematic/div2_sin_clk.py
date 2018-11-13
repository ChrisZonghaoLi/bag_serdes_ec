# -*- coding: utf-8 -*-

from typing import Dict

import os
import pkg_resources

from bag.design import Module


yaml_file = pkg_resources.resource_filename(__name__, os.path.join('netlist_info',
                                                                   'div2_sin_clk.yaml'))


# noinspection PyPep8Naming
class bag_serdes_ec__div2_sin_clk(Module):
    """Module for library bag_serdes_ec cell div2_sin_clk.

    A sinusoidal clock divider with differential outputs, enable, and initial state setting.
    """

    tran_info = [('XINTCLK', 'n0', 'int_clk'), ('XINTEN', 'n1', 'int_en'),
                 ('XINVCLK', 'p1', 'inv_clk'), ('XINVEN', 'p1', 'inv_en'),
                 ('XNINTL', 'n2', 'int_in'), ('XNINTR', 'n2', 'int_in'),
                 ('XNINVL', 'n2', 'inv_inv'), ('XNINVR', 'n2', 'inv_inv'),
                 ('XPENL', 'p0', 'int_pen'), ('XPENR', 'p0', 'int_pen'),
                 ('XPINTL', 'p0', 'int_rst'), ('XPINTR', 'p0', 'int_rst'),
                 ('XPINVL', 'p0', 'inv_inv'), ('XPINVR', 'p0', 'inv_inv'),
                 ('XPEI', 'p0', 'nor_inv'), ('XNEI', 'n2', 'nor_inv'),
                 ('XPDRVL', 'p0', 'nor_pdrv'), ('XPDRVR', 'p0', 'nor_pdrv'),
                 ('XNDRVL', 'n2', 'nor_ndrv'), ('XNDRVR', 'n2', 'nor_ndrv'),
                 ('XNSETL', 'n2', 'nor_set'), ('XNSETR', 'n2', 'nor_set'),
                 ('XPEN', 'p1', 'nor_pen'),
                 ]

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
            sr_params='SR latch parameters.',
        )

    def design(self, lch, w_dict, th_dict, seg_dict, sr_params):
        self.instances['XSR'].design(**sr_params)
        for name, row, seg_name in self.tran_info:
            seg = seg_dict[seg_name]
            w = w_dict[row]
            th = th_dict[row]
            self.instances[name].design(w=w, l=lch, nf=seg, intent=th)
