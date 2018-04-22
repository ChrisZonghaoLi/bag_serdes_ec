# -*- coding: utf-8 -*-

import yaml

from bag.core import BagProject

from analog_ec.layout.passives.filter.highpass import HighPassDiff

from serdes_ec.layout.qdr_hybrid.tap1 import Tap1Column
from serdes_ec.layout.qdr_hybrid.offset import HighPassColumn
from serdes_ec.layout.qdr_hybrid.tapx import TapXColumn


def run_main(prj):
    impl_lib = 'craft2_serdes_rx_top'
    rc_fname = 'specs_test/filter/highpass_diff.yaml'
    tap1_fname = 'specs_test/qdr_hybrid/tap1_column.yaml'
    tapx_fname = 'specs_test/qdr_hybrid/tapx_column.yaml'
    highpass_fname = 'specs_test/qdr_hybrid/highpass_column.yaml'

    with open(rc_fname, 'r') as f:
        rc_specs = yaml.load(f)
    with open(tap1_fname, 'r') as f:
        tap1_specs = yaml.load(f)
    with open(tapx_fname, 'r') as f:
        tapx_specs = yaml.load(f)
    with open(highpass_fname, 'r') as f:
        highpass_specs = yaml.load(f)

    tdb = prj.make_template_db(impl_lib, tap1_specs['routing_grid'])
    name_list = ['HIGHPASS_DIFF',
                 'TAP1_COLUMN',
                 'TAPX_COLUMN',
                 'HIGHPASS_COLUMN',
                 ]
    print('computing layout...')
    temp_list = [tdb.new_template(params=rc_specs['params'], temp_cls=HighPassDiff),
                 tdb.new_template(params=tap1_specs['params'], temp_cls=Tap1Column),
                 tdb.new_template(params=tapx_specs['params'], temp_cls=TapXColumn),
                 tdb.new_template(params=highpass_specs['params'], temp_cls=HighPassColumn),
                 ]
    print('computation done.')
    print('creating layout...')
    tdb.batch_layout(prj, temp_list, name_list)
    print('layout creation done.')


if __name__ == '__main__':
    local_dict = locals()
    if 'bprj' not in local_dict:
        print('creating BAG project')
        bprj = BagProject()

    else:
        print('loading BAG project')
        bprj = local_dict['bprj']

    run_main(bprj)
