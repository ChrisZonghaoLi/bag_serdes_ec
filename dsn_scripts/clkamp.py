# -*- coding: utf-8 -*-

from bag.core import BagProject

from serdes_ec.simulation.clkamp import ClkAmpChar


def characterize_linearity(prj):
    specs_fname = 'specs_design/clkamp.yaml'

    sim = ClkAmpChar(prj, specs_fname)
    sim.setup_linearity()

    sim.create_designs(tb_type='tb_pss_dc', extract=False)


def load_sim_data(prj, tb_type):
    specs_fname = 'data/clkamp/specs.yaml'

    sim = ClkAmpChar(prj, specs_fname)
    combo_list_list = list(sim.get_combinations_iter())
    return sim.get_sim_results(tb_type, combo_list_list[0])


if __name__ == '__main__':
    local_dict = locals()
    if 'bprj' not in local_dict:
        print('creating BAG project')
        bprj = BagProject()

    else:
        print('loading BAG project')
        bprj = local_dict['bprj']

    # characterize_linearity(bprj)
    results = load_sim_data(bprj, 'tb_pss_dc')
