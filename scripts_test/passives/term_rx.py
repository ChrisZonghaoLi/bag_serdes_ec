# -*- coding: utf-8 -*-

import os

import yaml

from bag.core import BagProject

from serdes_ec.layout.analog.passives import TermRXSingle


def run_main(prj):
    root_dir = 'specs_test/serdes_ec/passives'
    esd_fname = 'esd_params.yaml'
    spec_fname = 'term_rx.yaml'

    with open(os.path.join(root_dir, esd_fname), 'r') as f:
        esd_params = yaml.load(f)

    with open(os.path.join(root_dir, spec_fname), 'r') as f:
        specs = yaml.load(f)

    specs['params']['esd_params'] = esd_params

    prj.generate_cell(specs, TermRXSingle, debug=True)
    # prj.generate_cell(block_specs, TermRXSingle, gen_sch=True, debug=True)


if __name__ == '__main__':
    local_dict = locals()
    if 'bprj' not in local_dict:
        print('creating BAG project')
        bprj = BagProject()

    else:
        print('loading BAG project')
        bprj = local_dict['bprj']

    run_main(bprj)
