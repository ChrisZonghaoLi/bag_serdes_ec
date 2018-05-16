# -*- coding: utf-8 -*-

import yaml

from bag.core import BagProject

from serdes_ec.layout.analog.cml import CMLAmpPMOS


if __name__ == '__main__':
    with open('specs_test/serdes_ec/analog/cml_amp.yaml', 'r') as f:
        block_specs = yaml.load(f)

    local_dict = locals()
    if 'bprj' not in local_dict:
        print('creating BAG project')
        bprj = BagProject()

    else:
        print('loading BAG project')
        bprj = local_dict['bprj']

    bprj.generate_cell(block_specs, CMLAmpPMOS, debug=True)
    # bprj.generate_cell(block_specs, CMLAmpPMOS, gen_sch=True, debug=True)
