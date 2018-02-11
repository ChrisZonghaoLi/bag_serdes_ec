# -*- coding: utf-8 -*-

import yaml

from bag import float_to_si_string
from bag.core import BagProject
from bag.layout import RoutingGrid, TemplateDB

from serdes_ec.layout.analog.amplifier import DiffAmp


def make_tdb(prj, target_lib, specs):
    grid_specs = specs['routing_grid']
    layers = grid_specs['layers']
    spaces = grid_specs['spaces']
    widths = grid_specs['widths']
    bot_dir = grid_specs['bot_dir']

    routing_grid = RoutingGrid(prj.tech_info, layers, spaces, widths, bot_dir)
    tdb = TemplateDB('template_libs.def', routing_grid, target_lib, use_cybagoa=True)
    return tdb


def generate(prj, specs, gen_sch=True, run_lvs=False):
    impl_lib = specs['impl_lib']
    sch_lib = specs['sch_lib']
    sch_cell = specs['sch_cell']
    params = specs['params']
    lch_list = specs['swp_params']['lch']
    gr_nf_list = specs['swp_params']['guard_ring_nf']
    sub_par_list = specs['swp_params'].get('sub_parity', [0])

    temp_db = make_tdb(prj, impl_lib, specs)

    temp_list = []
    name_list = []
    name_fmt = 'DIFFAMP_L%s_gr%d_spar%d'
    for gr_nf in gr_nf_list:
        for lch in lch_list:
            for sub_par in sub_par_list:
                cur_name = name_fmt % (float_to_si_string(lch), gr_nf, sub_par)

                params['lch'] = lch
                params['guard_ring_nf'] = gr_nf
                params['options']['sub_parity'] = sub_par
                temp = temp_db.new_template(params=params, temp_cls=DiffAmp, debug=False)
                temp_list.append(temp)
                name_list.append(cur_name)

                if gen_sch:
                    dsn = prj.create_design_module(lib_name=sch_lib, cell_name=sch_cell)
                    dsn.design(**temp.sch_params)
                    print('creating schematic for %s' % cur_name)
                    dsn.implement_design(impl_lib, top_cell_name=cur_name)

    print('creating layout')
    temp_db.batch_layout(prj, temp_list, name_list)
    print('layout done')
    
    if run_lvs:
        print('running lvs')
        lvs_passed, lvs_log = prj.run_lvs(impl_lib, name_list[0])
        print('LVS log: %s' % lvs_log)
        if lvs_passed:
            print('LVS passed!')
        else:
            print('LVS failed...')


if __name__ == '__main__':
    with open('specs_test/diffamp_serdes.yaml', 'r') as f:
        block_specs = yaml.load(f)

    local_dict = locals()
    if 'bprj' not in local_dict:
        print('creating BAG project')
        bprj = BagProject()

    else:
        print('loading BAG project')
        bprj = local_dict['bprj']

    generate(bprj, block_specs, gen_sch=False, run_lvs=False)
