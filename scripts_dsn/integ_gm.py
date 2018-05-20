# -*- coding: utf-8 -*-

from bag.core import BagProject
from bag.io.sim_data import load_sim_results, save_sim_results


def simulate(prj):
    tb_lib = 'bag_serdes_testbenches_ec'
    tb_cell = 'gm_char_dc'
    dut_lib = 'CHAR_INTEG_AMP_FG4'
    dut_cell = 'INTEG_AMP'
    impl_lib = 'CHAR_INTEG_AMP_FG4_TB'
    impl_cell = tb_cell
    save_fname = 'blocks_ec_tsmcN16/data/gm_char_dc/linearity_fg4.hdf5'
    env_list = ['tt', 'ff_hot', 'ss_cold']
    sim_view = 'av_extracted'

    vck_amp = 0.4
    vdd = 0.9
    vstar_max = 0.3
    vstar_num = 31
    params = dict(
        incm=0.7,
        vdd=vdd,
        outcm=0.8,
        vb0=-vck_amp,
        vb1=vdd,
        num=41,
    )
    vstar_step = vstar_max * 2 / (vstar_num - 1)

    print('compute design')
    dsn = prj.create_design_module(tb_lib, tb_cell)
    dsn.design(dut_lib=dut_lib, dut_cell=dut_cell)
    print('implement design')
    dsn.implement_design(impl_lib, top_cell_name=impl_cell)

    print('create testbench')
    tb = prj.configure_testbench(impl_lib, tb_cell)
    tb.set_simulation_environments(env_list)
    tb.set_simulation_view(dut_lib, dut_cell, sim_view)

    for key, val in params.items():
        tb.set_parameter(key, val)
    tb.set_sweep_parameter('indm', start=-vstar_max, stop=vstar_max, step=vstar_step)
    tb.add_output('ioutp', """getData("/VOP/MINUS", ?result 'dc)""")
    tb.add_output('ioutn', """getData("/VON/MINUS", ?result 'dc)""")

    print('update testbench')
    tb.update_testbench()
    print('run simulation')
    save_dir = tb.run_simulation()
    print('load data')
    data = load_sim_results(save_dir)
    print('save_data')
    save_sim_results(data, save_fname)


if __name__ == '__main__':
    local_dict = locals()
    if 'bprj' not in local_dict:
        print('creating BAG project')
        bprj = BagProject()

    else:
        print('loading BAG project')
        bprj = local_dict['bprj']

    simulate(bprj)
