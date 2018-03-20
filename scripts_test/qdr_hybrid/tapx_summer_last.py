# -*- coding: utf-8 -*-

import yaml

from bag.core import BagProject


from serdes_ec.layout.qdr_hybrid.tapx import TapXSummerCell
from serdes_ec.layout.qdr_hybrid.tapx import TapXSummerLast


def generate(prj, specs, gen_sch=True, run_lvs=False, use_cybagoa=False):
    impl_lib = specs['impl_lib']
    grid_specs = specs['routing_grid']
    cell_params = specs['cell_params']
    params = specs['params']

    temp_db = prj.make_template_db(impl_lib, grid_specs)
    temp1 = temp_db.new_template(params=cell_params, temp_cls=TapXSummerCell, debug=False)

    params['row_layout_info'] = temp1.lat_row_layout_info
    params['lat_tr_info'] = temp1.lat_track_info
    prj.generate_cell(specs, TapXSummerLast, gen_sch=gen_sch, run_lvs=run_lvs,
                      use_cybagoa=use_cybagoa)


if __name__ == '__main__':
    with open('specs_test/qdr_hybrid/tapx_summer_last.yaml', 'r') as f:
        block_specs = yaml.load(f)

    local_dict = locals()
    if 'bprj' not in local_dict:
        print('creating BAG project')
        bprj = BagProject()

    else:
        print('loading BAG project')
        bprj = local_dict['bprj']

    # generate(bprj, block_specs, gen_sch=False, run_lvs=False, use_cybagoa=True)
    generate(bprj, block_specs, gen_sch=True, run_lvs=False, use_cybagoa=True)
