# -*- coding: utf-8 -*-

import yaml

from bag.core import BagProject
from bag.layout.routing import RoutingGrid
from bag.layout.template import TemplateDB

from serdes_ec.layout.qdr.tap1 import Tap1Summer


def make_tdb(prj, target_lib, specs):
    grid_specs = specs['routing_grid']
    layers = grid_specs['layers']
    widths = grid_specs['widths']
    spaces = grid_specs['spaces']
    bot_dir = grid_specs['bot_dir']
    width_override = grid_specs.get('width_override', None)

    routing_grid = RoutingGrid(prj.tech_info, layers, spaces, widths, bot_dir,
                               width_override=width_override)
    tdb = TemplateDB('template_libs.def', routing_grid, target_lib, use_cybagoa=True)
    return tdb


def generate(prj, specs, gen_sch=True, run_lvs=False):
    impl_lib = specs['impl_lib']
    impl_cell = specs['impl_cell']
    sch_lib = specs['sch_lib']
    sch_cell = specs['sch_cell']
    params = specs['params']

    temp_db = make_tdb(prj, impl_lib, specs)

    name_list = [impl_cell]
    temp = temp_db.new_template(params=params, temp_cls=Tap1Summer, debug=False)
    temp_list = [temp]
    print('creating layout')
    temp_db.batch_layout(prj, temp_list, name_list)
    print('layout done')

    if gen_sch:
        dsn = prj.create_design_module(lib_name=sch_lib, cell_name=sch_cell)
        dsn.design(**temp.sch_params)
        print('creating schematic')
        dsn.implement_design(impl_lib, top_cell_name=impl_cell)
    if run_lvs:
        print('running lvs')
        lvs_passed, lvs_log = prj.run_lvs(impl_lib, impl_cell)
        print('LVS log: %s' % lvs_log)
        if lvs_passed:
            print('LVS passed!')
        else:
            print('LVS failed...')


if __name__ == '__main__':
    with open('specs_test/qdr/tap1_summer.yaml', 'r') as f:
        block_specs = yaml.load(f)

    local_dict = locals()
    if 'bprj' not in local_dict:
        print('creating BAG project')
        bprj = BagProject()

    else:
        print('loading BAG project')
        bprj = local_dict['bprj']

    generate(bprj, block_specs, gen_sch=False, run_lvs=False)
