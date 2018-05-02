# -*- coding: utf-8 -*-

import yaml

from bag.core import BagProject

from serdes_ec.layout.qdr_hybrid.tap1 import Tap1Summer
from serdes_ec.layout.laygo.divider import SinClkDivider


def run_main(prj):
    with open('specs_test/serdes_ec/qdr_hybrid/sin_clk_divider.yaml', 'r') as f:
        div_specs = yaml.load(f)
    with open('specs_test/serdes_ec/qdr_hybrid/tap1_summer.yaml', 'r') as f:
        sum_specs = yaml.load(f)

    impl_lib = div_specs['impl_lib']
    grid_specs = div_specs['routing_grid']

    tdb = prj.make_template_db(impl_lib, grid_specs)
    summer = tdb.new_template(params=sum_specs['params'], temp_cls=Tap1Summer)

    params = div_specs['params']
    params['row_layout_info'] = summer.lat_row_info
    params['tr_info'] = summer.div_tr_info
    prj.generate_cell(div_specs, SinClkDivider, debug=True)
    # prj.generate_cell(div_specs, SinClkDivider, gen_sch=True, run_lvs=False,
    #                   run_rcx=True, debug=True)


if __name__ == '__main__':
    local_dict = locals()
    if 'bprj' not in local_dict:
        print('creating BAG project')
        bprj = BagProject()

    else:
        print('loading BAG project')
        bprj = local_dict['bprj']

    run_main(bprj)
