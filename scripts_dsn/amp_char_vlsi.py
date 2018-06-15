# -*- coding: utf-8 -*-

import os

import yaml
import numpy as np

from bag.core import BagProject
from bag.io.sim_data import load_sim_results, save_sim_results, load_sim_file

from serdes_ec.layout.analog.amplifier import DiffAmp


def gen_lay_sch(prj, specs, fg_load_list):
    impl_lib = specs['impl_lib']
    sch_lib = specs['sch_lib']
    sch_cell = specs['sch_cell']
    grid_specs = specs['routing_grid']
    params = specs['params']
    temp_db = prj.make_template_db(impl_lib, grid_specs, use_cybagoa=True)

    base_name = specs['impl_cell']
    name_list = []
    temp_list = []
    dsn_list = []
    for fg_load in fg_load_list:
        seg_dict = params['seg_dict'].copy()
        seg_dict['load'] = fg_load
        params['seg_dict'] = seg_dict
        cell_name = '%s_fg%d' % (base_name, fg_load)
        temp = temp_db.new_template(params=params, temp_cls=DiffAmp)
        dsn = prj.create_design_module(lib_name=sch_lib, cell_name=sch_cell)
        dsn.design(**temp.sch_params)

        name_list.append(cell_name)
        temp_list.append(temp)
        dsn_list.append(dsn)

    temp_db.batch_layout(prj, temp_list, name_list=name_list)
    prj.batch_schematic(impl_lib, dsn_list, name_list=name_list)

    return name_list


def simulate(prj, name_list, sim_params):
    impl_lib = sim_params['impl_lib']
    save_root = sim_params['save_root']
    tb_lib = sim_params['tb_lib']
    tb_cell = sim_params['tb_cell']
    env_list = sim_params['env_list']
    vload_list = sim_params['vload_list']
    sim_view = sim_params['sim_view']
    params = sim_params['params']

    for name in name_list:
        print('DUT: ', name)
        dut_cell = name
        impl_cell = name + '_TB'
        save_fname = os.path.join(save_root, '%s.hdf5' % name)

        print('run lvs')
        lvs_passed, lvs_log = prj.run_lvs(impl_lib, dut_cell)
        if not lvs_passed:
            raise ValueError('LVS failed...')
        print('run rcx')
        rcx_passed, rcx_log = prj.run_rcx(impl_lib, dut_cell)
        if not rcx_passed:
            raise ValueError('RCX failed...')

        print('make tb')
        dsn = prj.create_design_module(tb_lib, tb_cell)
        dsn.design(dut_lib=impl_lib, dut_cell=dut_cell)
        dsn.implement_design(impl_lib, top_cell_name=impl_cell)

        print('update testbench')
        tb = prj.configure_testbench(impl_lib, tb_cell)
        tb.set_simulation_environments(env_list)
        tb.set_simulation_view(impl_lib, dut_cell, sim_view)

        for key, val in params.items():
            tb.set_parameter(key, val)
        tb.set_sweep_parameter('vload', values=vload_list)
        tb.add_output('vout', """getData("/outac", ?result 'ac)""")

        tb.update_testbench()
        print('run simulation')
        save_dir = tb.run_simulation()
        print('load data')
        data = load_sim_results(save_dir)
        print('save_data')
        save_sim_results(data, save_fname)


def run_main(prj):
    fname = 'specs_test/serdes_ec/analog/diffamp.yaml'
    fg_load_list = [2, 4, 6, 8]

    with open(fname, 'r') as f:
        specs = yaml.load(f)

    impl_lib = specs['impl_lib']

    sim_params = dict(
        impl_lib=impl_lib,
        save_root='blocks_ec_tsmcN16/data/amp_vlsi/',
        tb_lib='bag_serdes_testbenches_ec',
        tb_cell='amp_char_vlsi',
        env_list=['tt', 'ff_hot', 'ss_cold'],
        vload_list=np.linspace(0.15, 0.45, 13, endpoint=True).tolist(),
        sim_view='av_extracted',
        params=dict(
            vincm=0.78,
            vdd=0.9,
            vtail=0.55,
            cload=5e-15,
        )
    )

    name_list = gen_lay_sch(prj, specs, fg_load_list)
    simulate(prj, name_list, sim_params)


if __name__ == '__main__':
    local_dict = locals()
    if 'bprj' not in local_dict:
        print('creating BAG project')
        bprj = BagProject()

    else:
        print('loading BAG project')
        bprj = local_dict['bprj']

    run_main(bprj)
