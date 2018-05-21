# -*- coding: utf-8 -*-

from typing import List

import numpy as np
import scipy.interpolate as interp
import scipy.integrate as integ

import matplotlib.pyplot as plt
# noinspection PyUnresolvedReferences
from mpl_toolkits.mplot3d import Axes3D
from matplotlib import cm
from matplotlib import ticker

from bag.core import BagProject
from bag.util.search import FloatBinaryIterator
from bag.io.sim_data import load_sim_results, save_sim_results, load_sim_file


def plot_vstar(result, tper, vdd, cload, bias_vec, ck_amp, rel_err, dc_params, vstar_params):
    npts = bias_vec.size
    vstar_vec = np.empty(npts)
    gain_vec = np.empty(npts)
    offset_vec = np.empty(npts)
    voutcm_vec = np.empty(npts)
    for idx, ck_bias in enumerate(bias_vec):
        in_vec, out_vec, cm_vec = get_dc_tf(result, tper, ck_amp, ck_bias, **dc_params)
        vstar, err, gain, offset = get_vstar(in_vec, out_vec, rel_err, **vstar_params)
        voutcm_vec[idx] = vdd - (cm_vec[cm_vec.size // 2] / cload)
        vstar_vec[idx] = vstar
        gain_vec[idx] = gain / cload
        offset_vec[idx] = offset / cload

    bias_vec *= 1e3
    vstar_vec *= 1e3
    offset_vec *= 1e3
    voutcm_vec *= 1e3

    plt.figure(1)
    ax = plt.subplot(411)
    ax.plot(bias_vec, vstar_vec, 'b')
    ax.set_ylabel('V* (mV)')
    ax = plt.subplot(412, sharex=ax)
    ax.plot(bias_vec, voutcm_vec, 'g')
    ax.set_ylabel('Voutcm (mV)')
    ax = plt.subplot(413, sharex=ax)
    ax.plot(bias_vec, gain_vec, 'm')
    ax.set_ylabel('Gain (V/V)')
    ax = plt.subplot(414, sharex=ax)
    ax.plot(bias_vec, vstar_vec * gain_vec, 'r')
    ax.set_ylabel('Gain * V* (mV)')
    ax.set_xlabel('Vbias (mV)')
    plt.show()


def get_vstar(in_vec, out_vec, rel_err, tol=1e-3, num=21, method='cubic'):
    fun = interp.interp1d(in_vec, out_vec, kind=method, copy=False, fill_value='extrapolate',
                          assume_sorted=True)
    mid_idx = in_vec.size // 2
    vmin = in_vec[mid_idx + 1]
    vmax = in_vec[-1]

    bin_iter = FloatBinaryIterator(vmin, vmax, tol=tol)
    while bin_iter.has_next():
        vtest = bin_iter.get_next()

        x_vec = np.linspace(-vtest, vtest, num, endpoint=True)
        b_vec = fun(x_vec)
        a_mat = np.column_stack((x_vec, np.ones(num)))
        x, _, _, _ = np.linalg.lstsq(a_mat, b_vec)
        rel_err_cur = np.amax(np.abs(np.dot(a_mat, x) - b_vec)) / (x[0] * vtest)

        if rel_err_cur <= rel_err:
            bin_iter.save_info((vtest, rel_err_cur, x[0], x[1]))
            bin_iter.up()
        else:
            bin_iter.down()

    return bin_iter.get_last_save_info()


def get_dc_tf(result, tper, ck_amp, ck_bias, num_k=7, sim_env='tt', method='linear', plot=False):
    indm_vec = result['indm']

    n = indm_vec.size
    dm_vec = np.empty(n)
    cm_vec = np.empty(n)
    for idx, indm in enumerate(indm_vec):
        ip_wv, in_wv, tstep = get_transient(result, idx, tper, ck_amp, ck_bias, num_k=num_k,
                                            sim_env=sim_env, method=method, plot=False)
        p_charge = integ.romb(ip_wv, dx=tstep)
        n_charge = integ.romb(in_wv, dx=tstep)
        dm_vec[idx] = n_charge - p_charge
        cm_vec[idx] = (n_charge + p_charge) / 2

    if plot:
        vstar, _, gain, offset = get_vstar(indm_vec, dm_vec, 0.05)
        x_vec = np.linspace(-vstar, vstar, 21, endpoint=True)
        y_vec = gain * x_vec + offset

        plt.figure(1)
        ax = plt.subplot(211)
        ax.plot(indm_vec, dm_vec, 'b')
        ax.plot(x_vec, y_vec, 'g')
        ax.set_ylabel('Qdm (Coulomb)')
        ax = plt.subplot(212, sharex=ax)
        ax.plot(indm_vec, cm_vec, 'g')
        ax.set_ylabel('Qcm (Coulomb)')
        ax.set_xlabel('Vindm (V)')
        plt.show()

    return indm_vec, dm_vec, cm_vec


def get_transient(result, in_idx, tper, ck_amp, ck_bias, num_k=7, sim_env='tt', method='linear',
                  plot=False):
    ioutp = result['ioutp']  # type: np.ndarray
    ioutn = result['ioutn']  # type: np.ndarray
    swp_pars = result['sweep_params']['ioutp']  # type: List

    if 'corner' in result:
        corners = result['corner']
        corner_idx = swp_pars.index('corner')
        env_idx = np.argwhere(corners == sim_env)[0][0]
        var0 = swp_pars[1] if corner_idx == 0 else swp_pars[0]
        ioutp = np.take(ioutp, env_idx, axis=corner_idx)
        ioutn = np.take(ioutn, env_idx, axis=corner_idx)
    else:
        var0 = swp_pars[0]

    if var0 != 'indm':
        ioutp = ioutp.transpose()
        ioutn = ioutn.transpose()

    bias = result['bias']
    ioutp = ioutp[in_idx, :]
    ioutn = ioutn[in_idx, :]
    vmin = ck_bias - ck_amp
    vmax = ck_bias + ck_amp
    if vmin < bias[0] or vmax > bias[-1]:
        print('WARNING: clock waveform exceed simulation range.')

    fun_ip = interp.interp1d(bias, ioutp, kind=method, copy=False, fill_value='extrapolate',
                             assume_sorted=True)
    fun_in = interp.interp1d(bias, ioutn, kind=method, copy=False, fill_value='extrapolate',
                             assume_sorted=True)

    num = 2 ** num_k + 1
    tvec, tstep = np.linspace(0, tper, num, endpoint=False, retstep=True)
    tail_wv = np.maximum(bias[0], ck_bias - ck_amp * np.cos(tvec * (2 * np.pi / tper)))
    ip_wv = fun_ip(tail_wv)
    in_wv = fun_in(tail_wv)

    if plot:
        plt.figure(1)
        tplt = tvec * 1e12
        plt.plot(tplt, ip_wv * 1e6, 'b', label='ioutp')
        plt.plot(tplt, in_wv * 1e6, 'g', label='ioutn')
        plt.legend()
        plt.xlabel('Time (ps)')
        plt.ylabel('Iout (uA)')
        plt.show()

    return ip_wv, in_wv, tstep


def plot_data_2d(result, name, sim_env=None):
    """Get interpolation function and plot/query."""

    swp_pars = result['sweep_params'][name]
    data = result[name]

    if sim_env is not None:
        corners = result['corner']
        corner_idx = swp_pars.index('corner')
        env_idx = np.argwhere(corners == sim_env)[0][0]
        data = np.take(data, env_idx, axis=corner_idx)
        swp_pars = swp_pars[:]
        del swp_pars[corner_idx]

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


def simulate(prj, save_fname, tb_lib, tb_cell, dut_lib, dut_cell, impl_lib, impl_cell, env_list,
             sim_view):
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


def run_main(prj):
    # save_fname = 'blocks_ec_tsmcN16/data/gm_char_dc/linearity_stack.hdf5'
    save_fname = 'blocks_ec_tsmcN16/data/gm_char_dc/linearity_stack.hdf5'

    sim_env = 'tt'
    vdd = 0.9
    voutcm = 0.7
    tper = 70e-12
    ck_amp = 0.3
    ck_bias = 0.05
    rel_err = 0.05
    cload = 5e-15
    bias_vec = np.linspace(0, 0.15, 16, endpoint=True)
    dc_params = dict(
        num_k=7,
        sim_env=sim_env,
        method='linear',
    )
    vstar_params = dict(
        tol=1e-3,
        num=21,
        method='cubic',
    )

    sim_params = dict(
        dut_lib='CHAR_INTEG_AMP_STACK_TSW',
        impl_lib='CHAR_INTEG_AMP_STACK_TSW_TB',
        impl_cell='gm_char_dc',
        save_fname=save_fname,
        tb_lib='bag_serdes_testbenches_ec',
        tb_cell='gm_char_dc',
        dut_cell='INTEG_AMP',
        env_list=['tt', 'ff_hot', 'ss_cold'],
        sim_view='av_extracted',
    )

    # simulate(prj, **sim_params)

    result = load_sim_file(save_fname)
    # plot_data_2d(result, 'ioutp', sim_env='tt')
    # get_transient(result, 15, tper, ck_amp, ck_bias, **kwargs)
    # get_dc_tf(result, tper, ck_amp, ck_bias, plot=True, **dc_params)
    plot_vstar(result, tper, vdd, cload, bias_vec, ck_amp, rel_err, dc_params, vstar_params)


if __name__ == '__main__':
    local_dict = locals()
    if 'bprj' not in local_dict:
        print('creating BAG project')
        bprj = BagProject()

    else:
        print('loading BAG project')
        bprj = local_dict['bprj']

    run_main(bprj)
