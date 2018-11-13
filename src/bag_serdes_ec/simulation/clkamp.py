# -*- coding: utf-8 -*-
########################################################################################################################
#
# Copyright (c) 2014, Regents of the University of California
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without modification, are permitted provided that the
# following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this list of conditions and the following
#   disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the
#    following disclaimer in the documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES,
# INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY,
# WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
########################################################################################################################


from typing import TYPE_CHECKING, Optional, Tuple, Any, Dict, List
import os
from copy import deepcopy

import numpy as np
import scipy.linalg as linalg

from bag.io import open_file
from bag.data.digital import de_bruijn, dig_to_pwl
from bag.simulation.core import SimulationManager

if TYPE_CHECKING:
    from bag.core import BagProject, Testbench


class ClkAmpChar(SimulationManager):
    def __init__(self, prj, spec_file):
        # type: (Optional[BagProject], str) -> None
        super(ClkAmpChar, self).__init__(prj, spec_file)

    @classmethod
    def _setup_pwl_input(cls, values, tper, tr, tran_fname):
        # type: (List[float], float) -> None

        tvec, yvec = dig_to_pwl(values, tper, tr, td=0.0)

        tran_fname = os.path.abspath(tran_fname)
        stimuli_dir = os.path.dirname(tran_fname)
        os.makedirs(stimuli_dir, exist_ok=True)
        with open_file(tran_fname, 'w') as f:
            for t, y in zip(tvec, yvec):
                f.write('%.8f %.8f\n' % (t,  y))

    def setup_linearity(self):
        tb_specs = self.specs['tb_pss_dc']
        tper = tb_specs['tb_params']['tper']
        tran_fname = tb_specs['sch_params']['tran_fname']

        values = [1.0]
        tr = 0.2 * tper
        self._setup_pwl_input(values, tper, tr, tran_fname)

    def setup_tran_binary(self):
        tb_specs = self.specs['tb_pss_tran']
        input_tr = tb_specs['input_tr']
        input_n = tb_specs['input_n']
        tper = tb_specs['tb_params']['tper']
        tran_fname = tb_specs['sch_params']['tran_fname']

        values = de_bruijn(input_n, symbols=[-1.0, 1.0])
        tb_specs['tb_params']['tper_pss'] = tper * len(values)

        self._setup_pwl_input(values, tper, input_tr, tran_fname)

    def get_layout_params(self, val_list):
        # type: (Tuple[Any, ...]) -> Dict[str, Any]
        """Returns the layout dictionary from the given sweep parameter values.

        This method is over-ridden so user can set width/threshold/segment too.
        """
        lay_params = deepcopy(self.specs['layout_params'])
        for var, val in zip(self.swp_var_list, val_list):
            # handle width/threshold/segment settings
            special_var = False
            for prefix in ('w_', 'th_', 'seg_'):
                if var.startswith(prefix):
                    special_var = True
                    var_actual = var[len(prefix):]
                    table = lay_params[prefix + 'dict']
                    if var_actual not in table:
                        raise ValueError('Unknown parameter: %s' % var)
                    table[var_actual] = val
                    break

            # handle other settings
            if not special_var:
                if var not in lay_params:
                    raise ValueError('Unknown parameter: %s' % var)
                lay_params[var] = val

        return lay_params

    def configure_tb(self, tb_type, tb, val_list):
        # type: (str, Testbench, Tuple[Any, ...]) -> None
        tb_specs = self.specs[tb_type]
        sim_envs = self.specs['sim_envs']
        view_name = self.specs['view_name']
        impl_lib = self.specs['impl_lib']
        dsn_name_base = self.specs['dsn_name_base']

        tb_params = tb_specs['tb_params']
        dsn_name = self.get_instance_name(dsn_name_base, val_list)

        tb.set_simulation_environments(sim_envs)
        tb.set_simulation_view(impl_lib, dsn_name, view_name)

        for key, val in tb_params.items():
            if isinstance(val, list):
                tb.set_sweep_parameter(key, values=val)
            else:
                tb.set_parameter(key, val)

        # add outputs
        tb.add_output('vod', """getData("/vout" ?result "pss_td")""")
        tb.add_output('voc', """getData("/voutcm" ?result "pss_td")""")
        tb.add_output('clk', """getData("/clkp_tail" ?result "pss_td")""")

    @classmethod
    def compute_linearity(cls, results, time_idx):
        # type: (Dict[str, Any], int) -> Tuple[np.array, np.array, np.array, List[str]]
        """Given a PSS simulation with DC input, compute linearity spec.

        This function samples the transient waveform at the given index, then
        performs a least-square fit to a straight line.

        Parameters
        ----------
        results : Dict[str, Any]
            the simulation result dictionary.
        time_idx : int
            the index at which to sample the output waveform.

        Returns
        -------
        gain : np.array
            A (N1, N2, ...) numpy array representing the linear gain across
            swept parameters.
        offset : np.array
            A (N1, N2, ...) numpy array representing the differential output
            offset across swept parameters.
        err : np.array
            A (N1, N2, ...) numpy array of least-square fit residues
            (squared 2-norm of b - Ax) across swept parameters.  This is a
            measurement of non-linearity.
        swp_var_list : List[str]
            list of swept parameter names of each dimension of the return result.
        """
        swp_var_list = list(results['sweep_params']['vod'])
        vod = results['vod']

        # error checking
        if 'gain' not in swp_var_list:
            raise ValueError('gain must be swept to measure linearity.')
        if 'time' not in swp_var_list:
            raise ValueError('time is not swept, something is wrong.')

        # remove time
        num_dim = len(swp_var_list)
        ax_idx = swp_var_list.index('time')
        if ax_idx != num_dim - 1:
            vod = np.swapaxes(vod, ax_idx, num_dim - 1)
            swp_var_list[ax_idx] = swp_var_list[num_dim - 1]
        vod = vod[..., time_idx]
        swp_var_list = swp_var_list[:-1]

        # move gain to first dimension
        ax_idx = swp_var_list.index('gain')
        if ax_idx != 0:
            vod = np.swapaxes(vod, 0, ax_idx)
            swp_var_list[ax_idx] = swp_var_list[0]
        swp_var_list = swp_var_list[1:]

        # perform least square linear fit
        vin = results['gain']
        num_in = vin.size
        swp_shape = vod.shape[1:]
        b = vod.reshape((num_in, -1))
        a = np.ones((num_in, 2), dtype=float)
        a[:, 0] = vin
        x, err, _, _ = linalg.lstsq(a, b)
        # reshape answer to match sweep parameters
        x = x.reshape((2, ) + swp_shape)
        err = err.reshape(swp_shape)

        return x[0, ...], x[1, ...], err, swp_var_list
