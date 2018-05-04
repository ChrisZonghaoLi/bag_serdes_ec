# -*- coding: utf-8 -*-

import yaml

from bag.core import BagProject

from digital_ec.layout.stdcells.core import StdCellWrapper


if __name__ == '__main__':
    with open('specs_test/serdes_ec/qdr_hybrid/retimer.yaml', 'r') as f:
        block_specs = yaml.load(f)

    local_dict = locals()
    if 'bprj' not in local_dict:
        print('creating BAG project')
        bprj = BagProject()

    else:
        print('loading BAG project')
        bprj = local_dict['bprj']

    StdCellWrapper.generate_cells(bprj, block_specs, debug=True)
    # StdCellWrapper.generate_cells(bprj, block_specs, gen_sch=True, run_lvs=True)
