# -*- coding: utf-8 -*-

import yaml

from bag.core import BagProject

from serdes_ec.layout.qdr_hybrid.tap1 import Tap1Summer
from serdes_ec.layout.qdr_hybrid.sampler import DividerColumn


def run_main(prj):
    with open('specs_test/qdr_hybrid/divider_column.yaml', 'r') as f:
        div_specs = yaml.load(f)
    with open('specs_test/qdr_hybrid/tap1_summer.yaml', 'r') as f:
        sum_specs = yaml.load(f)

    impl_lib = div_specs['impl_lib']
    grid_specs = div_specs['routing_grid']

    tdb = prj.make_template_db(impl_lib, grid_specs)
    summer = tdb.new_template(params=sum_specs['params'], temp_cls=Tap1Summer)

    params = div_specs['params']
    params['sum_row_info'] = summer.sum_row_info
    params['lat_row_info'] = summer.lat_row_info
    params['tr_info'] = summer.div_tr_info

    prj.generate_cell(div_specs, DividerColumn, debug=True)
    # bprj.generate_cell(block_specs, DividerColumn, gen_sch=True, run_lvs=True)


if __name__ == '__main__':
    local_dict = locals()
    if 'bprj' not in local_dict:
        print('creating BAG project')
        bprj = BagProject()

    else:
        print('loading BAG project')
        bprj = local_dict['bprj']

    run_main(bprj)
