# -*- coding: utf-8 -*-

import os

import yaml

from bag.core import BagProject

from serdes_ec.layout.analog.passives import CMLResLoad
from serdes_ec.layout.analog.cml import CMLGmPMOS


def run_main(prj):
    root_name = 'specs_test/serdes_ec'
    test_fname = os.path.join(root_name, 'analog/cml_gm_info.yaml')
    if not os.path.isfile(test_fname):
        with open(os.path.join(root_name, 'passives/cml_load.yaml'), 'r') as f:
            dep_specs = yaml.load(f)

        impl_lib = dep_specs['impl_lib']
        grid_specs = dep_specs['routing_grid']

        tdb = prj.make_template_db(impl_lib, grid_specs)
        dep = tdb.new_template(params=dep_specs['params'], temp_cls=CMLResLoad)
        save_info = dict(output_tracks=dep.output_tracks,
                         tot_width=dep.bound_box.width_unit,
                         )

        with open(test_fname, 'w') as f:
            yaml.dump(save_info, f)
    else:
        with open(test_fname, 'r') as f:
            save_info = yaml.load(f)

    with open(os.path.join(root_name, 'analog/cml_gm.yaml'), 'r') as f:
        specs = yaml.load(f)

    specs['params'].update(save_info)
    prj.generate_cell(specs, CMLGmPMOS, debug=True)
    # prj.generate_cell(div_specs, CMLCorePMOS, gen_sch=True, debug=True)


if __name__ == '__main__':
    local_dict = locals()
    if 'bprj' not in local_dict:
        print('creating BAG project')
        bprj = BagProject()

    else:
        print('loading BAG project')
        bprj = local_dict['bprj']

    run_main(bprj)
