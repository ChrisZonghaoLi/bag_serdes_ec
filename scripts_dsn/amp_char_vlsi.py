# -*- coding: utf-8 -*-

import os

import yaml
import numpy as np
import scipy.interpolate as interp
import scipy.optimize as sciopt
import matplotlib.pyplot as plt
# noinspection PyUnresolvedReferences
from mpl_toolkits.mplot3d import Axes3D
from matplotlib import cm, rc
from matplotlib import ticker

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
        tb = prj.configure_testbench(impl_lib, impl_cell)
        tb.set_simulation_environments(env_list)
        tb.set_simulation_view(impl_lib, dut_cell, sim_view)

        for key, val in params.items():
            tb.set_parameter(key, val)
        tb.set_sweep_parameter('vload', values=vload_list)
        tb.add_output('outac', """getData("/outac", ?result 'ac)""")

        tb.update_testbench()
        print('run simulation')
        save_dir = tb.run_simulation()
        print('load data')
        data = load_sim_results(save_dir)
        print('save_data')
        save_sim_results(data, save_fname)


def compute_gain_and_w3db(f_vec, out_arr):
    out_arr = np.abs(out_arr)
    gain = out_arr[0]

    # convert
    out_log = 20 * np.log10(out_arr)
    gain_log_3db = 20 * np.log10(gain) - 3

    # find first index at which gain goes below gain_log 3db
    diff_arr = out_log - gain_log_3db
    idx_arr = np.argmax(diff_arr < 0)
    freq_log = np.log10(f_vec)
    freq_log_max = freq_log[idx_arr]

    fun = interp.interp1d(freq_log, diff_arr, kind='cubic', copy=False,
                          assume_sorted=True)
    try:
        # noinspection PyTypeChecker
        f3db = 10.0**(sciopt.brentq(fun, freq_log[0], freq_log_max))
    except ValueError:
        f3db = f_vec[-1]

    return gain, f3db


def plot_mat(fig_idx, zlabel, mat, xvec, yvec):

    fun = interp.RectBivariateSpline(xvec, yvec, mat)
    x_mat, y_mat = np.meshgrid(xvec, yvec, indexing='ij', copy=False)

    formatter = ticker.ScalarFormatter(useMathText=True)
    formatter.set_scientific(True)
    formatter.set_powerlimits((-2, 3))

    xvec2 = np.linspace(xvec[0], xvec[-1], len(xvec) * 4)
    yvec2 = np.linspace(yvec[0], yvec[-1], len(yvec) * 4)
    x_fine, y_fine = np.meshgrid(xvec2, yvec2, indexing='ij', copy=False)
    z_fine = fun(xvec2, yvec2, grid=True)

    fig = plt.figure(fig_idx + 1)
    ax = fig.add_subplot(111, projection='3d')
    ax.plot_surface(x_fine, y_fine, z_fine, rstride=1, cstride=1, linewidth=0, cmap=cm.cubehelix)
    ax.scatter(x_mat.reshape(-1), y_mat.reshape(-1), mat.reshape(-1), c='r', marker='o')

    ax.set_xlabel('$N_{load}$', fontsize=18)
    ax.set_ylabel('$V_{load}$ (V)', fontsize=18)
    ax.set_zlabel(zlabel, fontsize=18)
    ax.w_zaxis.set_major_formatter(formatter)


def plot_gain_bw(specs, sim_params, fg_load_list, env):
    vname = 'outac'
    base_name = specs['impl_cell']
    save_root = sim_params['save_root']
    vload_list = sim_params['vload_list']
    gain_mat = np.empty((len(fg_load_list), len(vload_list)))
    bw_mat = np.empty((len(fg_load_list), len(vload_list)))
    for fg_idx, fg_load in enumerate(fg_load_list):
        fname = os.path.join(save_root, '%s_fg%d.hdf5' % (base_name, fg_load))
        results = load_sim_file(fname)

        swp_pars = results['sweep_params'][vname]
        corners = results['corner']
        corner_idx = swp_pars.index('corner')
        env_idx = np.argwhere(corners == env)[0][0]
        data = np.take(results[vname], env_idx, axis=corner_idx)
        vload_idx = swp_pars.index('vload')
        vload_vec = results['vload']
        for idx in range(vload_vec.size):
            outac = np.take(data, idx, axis=vload_idx)
            gain, f3db = compute_gain_and_w3db(results['freq'], outac)
            gain_mat[fg_idx, idx] = gain
            bw_mat[fg_idx, idx] = f3db

    plot_mat(1, '$A_v$ (V/V)', gain_mat, fg_load_list, vload_list)
    plot_mat(2, '$f_{3db}$ (Hz)', bw_mat, fg_load_list, vload_list)
    plt.show()


def run_main(prj):
    fname = 'specs_test/serdes_ec/analog/diffamp.yaml'
    fg_load_list = [6, 8, 10, 12, 14]

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

    # name_list = gen_lay_sch(prj, specs, fg_load_list)
    # simulate(prj, name_list, sim_params)
    plot_gain_bw(specs, sim_params, fg_load_list, 'ss_cold')


if __name__ == '__main__':
    local_dict = locals()
    if 'bprj' not in local_dict:
        print('creating BAG project')
        bprj = BagProject()

    else:
        print('loading BAG project')
        bprj = local_dict['bprj']

    run_main(bprj)
