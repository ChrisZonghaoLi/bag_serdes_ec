# -*- coding: utf-8 -*-

import yaml

from bag.core import BagProject

from serdes_ec.layout.qdr_hybrid.top import RXFrontend


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

    # bprj.generate_cell(block_specs, RXFrontend, debug=True)
    bprj.generate_cell(block_specs, RXFrontend, gen_lay=False, gen_sch=True, debug=True)
