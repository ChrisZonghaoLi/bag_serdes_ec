# -*- coding: utf-8 -*-

import os

import yaml

from bag.core import BagProject

from serdes_ec.layout.qdr_hybrid.tapx import TapXSummer
from serdes_ec.layout.qdr_hybrid.sampler import DividerColumn


def run_main(prj):
    root_name = 'specs_test/serdes_ec/qdr_hybrid'
    test_fname = os.path.join(root_name, 'divider_column_info.yaml')
    if not os.path.isfile(test_fname):
        with open(os.path.join(root_name, 'tapx_summer.yaml'), 'r') as f:
            sum_specs = yaml.load(f)

        impl_lib = sum_specs['impl_lib']
        grid_specs = sum_specs['routing_grid']

        tdb = prj.make_template_db(impl_lib, grid_specs)
        summer = tdb.new_template(params=sum_specs['params'], temp_cls=TapXSummer)
        div_info = dict(sum_row_info=summer.sum_row_info,
                        lat_row_info=summer.lat_row_info,
                        div_tr_info=summer.div_tr_info,
                        right_edge_info=summer.lr_edge_info[0],
                        sup_tids=summer.sup_tids)

        with open(test_fname, 'w') as f:
            yaml.dump(div_info, f)
    else:
        with open(test_fname, 'r') as f:
            div_info = yaml.load(f)

    div_info['right_edge_info'] = None
    div_info['en2_tr_idx'] = 'default'
    div_info['add_dummy'] = False

    with open(os.path.join(root_name, 'divider_column.yaml'), 'r') as f:
        div_specs = yaml.load(f)

    div_specs['params'].update(div_info)
    prj.generate_cell(div_specs, DividerColumn, debug=True)
    # prj.generate_cell(div_specs, DividerColumn, gen_sch=True, debug=True)


if __name__ == '__main__':
    local_dict = locals()
    if 'bprj' not in local_dict:
        print('creating BAG project')
        bprj = BagProject()

    else:
        print('loading BAG project')
        bprj = local_dict['bprj']

    run_main(bprj)
