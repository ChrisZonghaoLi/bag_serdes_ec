# -*- coding: utf-8 -*-

import yaml

from bag.core import BagProject

from serdes_ec.layout.tx.ser import Serializer32


if __name__ == '__main__':
    with open('specs_test/serdes_ec/tx/ser32.yaml', 'r') as f:
        block_specs = yaml.load(f)

    local_dict = locals()
    if 'bprj' not in local_dict:
        print('creating BAG project')
        bprj = BagProject()

    else:
        print('loading BAG project')
        bprj = local_dict['bprj']

    bprj.generate_cell(block_specs, Serializer32, debug=True)
    # bprj.generate_cell(block_specs, Serializer32, gen_sch=True, debug=True)
