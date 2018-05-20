# -*- coding: utf-8 -*-

import numpy as np

import matplotlib.pyplot as plt
# noinspection PyUnresolvedReferences
from mpl_toolkits.mplot3d import Axes3D
from matplotlib import cm
from matplotlib import ticker

from bag.core import BagProject
from bag.io.sim_data import load_sim_results, save_sim_results, load_sim_file


def simulate(prj, save_fname):
    tb_lib = 'bag_serdes_testbenches_ec'
    tb_cell = 'gm_char_dc'
    dut_lib = 'CHAR_INTEG_AMP_FG4'
    dut_cell = 'INTEG_AMP'
    impl_lib = 'CHAR_INTEG_AMP_FG4_TB'
    impl_cell = tb_cell
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
        num=40,
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


def get_data(save_fname):
    result = load_sim_file(save_fname)
    return result


def plot_data_2d(result, name, sim_env=None):
    """Get interpolation function and plot/query."""

    swp_pars = result['sweep_params'][name]
    data = result[name]

    if sim_env is not None:
        corners = result['corner']
        corner_idx = swp_pars.index('corner')
        env_idx = np.argwhere(corners == sim_env)[0][0]
        data = np.take(data, env_idx, axis=corner_idx)
        swp_pars = swp_pars[:corner_idx] + swp_pars[corner_idx + 1:]

    xvec = result[swp_pars[0]]
    yvec = result[swp_pars[1]]

    xmat, ymat = np.meshgrid(xvec, yvec, indexing='ij', copy=False)

    formatter = ticker.ScalarFormatter(useMathText=True)
    formatter.set_scientific(True)
    formatter.set_powerlimits((-2, 3))

    fig = plt.figure(1)
    ax = fig.add_subplot(111, projection='3d')
    ax.plot_surface(xmat, ymat, data, rstride=1, cstride=1, linewidth=0, cmap=cm.cubehelix)
    ax.set_xlabel(swp_pars[0])
    ax.set_ylabel(swp_pars[1])
    ax.set_zlabel(name)
    ax.w_zaxis.set_major_formatter(formatter)

    plt.show()


def run_main(prj):
    save_fname = 'blocks_ec_tsmcN16/data/gm_char_dc/linearity.hdf5'

    # simulate(prj, save_fname)
    data = get_data(save_fname)
    plot_data_2d(data, 'ioutp', sim_env='tt')


if __name__ == '__main__':
    local_dict = locals()
    if 'bprj' not in local_dict:
        print('creating BAG project')
        bprj = BagProject()

    else:
        print('loading BAG project')
        bprj = local_dict['bprj']

    run_main(bprj)
