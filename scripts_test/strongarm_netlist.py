# -*- coding: utf-8 -*-

import pprint

import yaml

from bag.core import BagProject

from serdes_ec.layout.laygo.strongarm import SenseAmpStrongArm


def netlist_test(prj, specs, gen_lay=False, gen_sch=False):
    impl_lib = specs['impl_lib']
    impl_cell = specs['impl_cell']
    sch_lib = specs['sch_lib']
    sch_cell = specs['sch_cell']
    grid_specs = specs['routing_grid']
    params = specs['params']

    temp_db = prj.make_template_db(impl_lib, grid_specs, use_cybagoa=False)

    name_list = [impl_cell]
    print('computing layout...')

    temp = temp_db.new_template(params=params, temp_cls=SenseAmpStrongArm, debug=True)
    print('computation done.')
    temp_list = [temp]

    if gen_lay:
        print('creating layout...')
        temp_db.batch_layout(prj, temp_list, name_list, debug=True)
        print('layout done.')

    if gen_sch:
        dsn = prj.create_design_module(lib_name=sch_lib, cell_name=sch_cell)
        print('schematic parameters:')
        pprint.pprint(temp.sch_params)
        print('computing schematic...')
        dsn.design(**temp.sch_params)
        print('creating schematic...')
        dsn.implement_design(impl_lib, top_cell_name=impl_cell, output='schematic',
                             format='spice', cell_map='cell_map.yaml', fname='strongarm.sp')
        print('schematic done.')


if __name__ == '__main__':
    with open('specs_test/serdes_ec/qdr_hybrid/strongarm.yaml', 'r') as f:
        block_specs = yaml.load(f)

    local_dict = locals()
    if 'bprj' not in local_dict:
        print('creating BAG project')
        bprj = BagProject()

    else:
        print('loading BAG project')
        bprj = local_dict['bprj']

    netlist_test(bprj, block_specs, gen_sch=True)
