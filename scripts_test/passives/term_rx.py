# -*- coding: utf-8 -*-

import os

import yaml

from bag.core import BagProject

from serdes_ec.layout.analog.passives import TermRX


def run_main(prj):
    root_dir = 'specs_test/serdes_ec/passives'
    spec_fname = 'term_rx.yaml'

    with open(os.path.join(root_dir, spec_fname), 'r') as f:
        specs = yaml.load(f)

    prj.generate_cell(specs, TermRX, debug=True)
    # prj.generate_cell(specs, TermRX, gen_sch=True, debug=True)


if __name__ == '__main__':
    local_dict = locals()
    if 'bprj' not in local_dict:
        print('creating BAG project')
        bprj = BagProject()

    else:
        print('loading BAG project')
        bprj = local_dict['bprj']

    run_main(bprj)
