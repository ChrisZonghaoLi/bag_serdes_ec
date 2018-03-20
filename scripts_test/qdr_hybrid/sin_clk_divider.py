# -*- coding: utf-8 -*-

import yaml

from bag.core import BagProject

from serdes_ec.layout.qdr_hybrid.tap1 import IntegAmp
from serdes_ec.layout.laygo.divider import SinClkDivider


def generate(prj, specs, gen_sch=True, run_lvs=False, use_cybagoa=False):
    impl_lib = specs['impl_lib']
    grid_specs = specs['routing_grid']
    ana_params = specs['ana_params']
    params = specs['params']

    temp_db = prj.make_template_db(impl_lib, grid_specs)
    temp1 = temp_db.new_template(params=ana_params, temp_cls=IntegAmp, debug=False)

    params['row_layout_info'] = temp1.row_layout_info
    prj.generate_cell(specs, SinClkDivider, gen_sch=gen_sch, run_lvs=run_lvs,
                      use_cybagoa=use_cybagoa)


if __name__ == '__main__':
    with open('specs_test/qdr_hybrid/sin_clk_divider.yaml', 'r') as f:
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
