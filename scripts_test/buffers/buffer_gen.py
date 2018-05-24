# -*- coding: utf-8 -*-

import os

import yaml

from bag.core import BagProject

from serdes_ec.layout.digital.buffer import BufferArray


def run_main(prj, gen_lay=True, gen_sch=False, debug=False):
    root = 'specs_test/tx_buffers'
    buf_list = ['buffer1.yaml',
                'buffer2.yaml',
                'buffer3.yaml',
                'buffer4.yaml',
                ]

    with open(os.path.join(root, buf_list[0]), 'r') as f:
        specs = yaml.load(f)

    impl_lib = specs['impl_lib']
    grid_specs = specs['routing_grid']

    tdb = prj.make_template_db(impl_lib, grid_specs, use_cybagoa=True)
    name_list = []
    lay_list = []
    sch_list = []
    for spec_fname in buf_list:
        with open(os.path.join(root, spec_fname), 'r') as f:
            specs = yaml.load(f)

        cell_name = specs['impl_cell']
        params = specs['params']
        print('computing layout for %s' % cell_name)

        temp = tdb.new_template(params=params, temp_cls=BufferArray)
        name_list.append(cell_name)
        lay_list.append(temp)
        if gen_sch:
            print('computing schematic for %s' % cell_name)
            sch_lib = specs['sch_lib']
            sch_cell = specs['sch_cell']
            dsn = prj.create_design_module(lib_name=sch_lib, cell_name=sch_cell)
            dsn.design(**temp.sch_params)
            sch_list.append(dsn)

    if gen_lay:
        print('creating layouts')
        tdb.batch_layout(prj, lay_list, name_list, debug=debug)
    if gen_sch:
        print('creating schematics')
        prj.batch_schematic(impl_lib, sch_list, name_list, debug=debug)


if __name__ == '__main__':
    local_dict = locals()
    if 'bprj' not in local_dict:
        print('creating BAG project')
        bprj = BagProject()

    else:
        print('loading BAG project')
        bprj = local_dict['bprj']

    run_main(bprj, gen_sch=True, debug=True)
