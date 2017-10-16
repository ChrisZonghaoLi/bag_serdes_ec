# -*- coding: utf-8 -*-

from bag.core import BagProject

from serdes_ec.simulation.clkamp import ClkAmpChar


def characterize_linearity(prj):
    specs_fname = 'specs_design/clkamp.yaml'

    sim = ClkAmpChar(prj, specs_fname)
    sim.setup_linearity()

    sim.create_designs(tb_type='tb_pss_dc', extract=False)


if __name__ == '__main__':
    local_dict = locals()
    if 'bprj' not in local_dict:
        print('creating BAG project')
        bprj = BagProject()

    else:
        print('loading BAG project')
        bprj = local_dict['bprj']

    characterize_linearity(bprj)
