# -*- coding: utf-8 -*-

import yaml

from bag.core import BagProject

from serdes_ec.layout.qdr_hybrid.top import RXFrontend


def gen_top_sch(prj, specs):
    impl_lib = specs['impl_lib']
    sch_lib = specs['sch_lib']
    gds_lay_file = specs.get('gds_lay_file', '')
    grid_specs = specs['routing_grid']
    params = specs['params']

    temp_db = prj.make_template_db(impl_lib, grid_specs, use_cybagoa=True,
                                   gds_lay_file=gds_lay_file)

    print('computing layout...')
    temp = temp_db.new_template(params=params, temp_cls=RXFrontend, debug=True)
    print('computation done.')

    dsn = prj.create_design_module(lib_name=sch_lib, cell_name='qdr_top')
    print('computing schematic...')
    sch_params = dict(
        dp_params=temp.sch_params,
    )
    dsn.design(**sch_params)
    print('creating schematic...')
    dsn.implement_design(impl_lib, top_cell_name='QDR_TOP')
    print('schematic done.')


if __name__ == '__main__':
    with open('specs_test/serdes_ec/qdr_hybrid/frontend.yaml', 'r') as f:
        block_specs = yaml.load(f)

    local_dict = locals()
    if 'bprj' not in local_dict:
        print('creating BAG project')
        bprj = BagProject()

    else:
        print('loading BAG project')
        bprj = local_dict['bprj']

    gen_top_sch(bprj, block_specs)
    # bprj.generate_cell(block_specs, RXFrontend, debug=True)
    # bprj.generate_cell(block_specs, RXDatapath, gen_sch=True, run_lvs=True)
