# -*- coding: utf-8 -*-

from bag.core import BagProject

from serdes_ec.simulation.clkamp import ClkAmpChar


def characterize(prj):
    specs_fname = 'specs_design/clkamp.yaml'

    sim = ClkAmpChar(prj, specs_fname)
    sim.create_designs(extract=False)
    for val_list in sim.get_combinations_iter():
        sim.setup_testbench('tb_pss', val_list)


if __name__ == '__main__':
    local_dict = locals()
    if 'bprj' not in local_dict:
        print('creating BAG project')
        bprj = BagProject()

    else:
        print('loading BAG project')
        bprj = local_dict['bprj']

    characterize(bprj)
