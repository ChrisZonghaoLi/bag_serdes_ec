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

from bag.io import open_file
from bag.data.digital import de_bruijn, dig_to_pwl
from bag.tech.core import SimulationManager

if TYPE_CHECKING:
    from bag.core import BagProject, Testbench


class ClkAmpChar(SimulationManager):
    def __init__(self, prj, spec_file):
        # type: (Optional[BagProject], str) -> None
        super(ClkAmpChar, self).__init__(prj, spec_file)

    def setup_pwl_input(self, values, tr):
        # type: (List[float], float) -> None
        tb_specs = self.specs['tb_pss']
        tper = tb_specs['tb_params']['tper']

        tvec, yvec = dig_to_pwl(values, tper, tr, td=0.0)

        tran_fname = tb_specs['sch_params']['tran_fname']
        tran_fname = os.path.abspath(tran_fname)
        stimuli_dir = os.path.dirname(tran_fname)
        os.makedirs(stimuli_dir, exist_ok=True)
        with open_file(tran_fname, 'w') as f:
            for t, y in zip(tvec, yvec):
                f.write('%.8f %.8f\n' % (t,  y))

    def setup_linearity(self, vin_amp):
        tb_specs = self.specs['tb_pss']
        tper = tb_specs['tb_params']['tper']

        values = [1.0]
        tb_specs['tb_params']['tper_pss'] = tper
        tr = 0.2 * tper

        self.setup_pwl_input(values, tr)
        tb_specs['tb_params']['gain'] = vin_amp

    def setup_tran_binary(self, vin_amp, n, tr):
        tb_specs = self.specs['tb_pss']
        tper = tb_specs['tb_params']['tper']

        values = de_bruijn(n, symbols=[-1.0, 1.0])
        tb_specs['tb_params']['tper_pss'] = tper * len(values)

        self.setup_pwl_input(values, tr)
        tb_specs['tb_params']['gain'] = vin_amp

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
        tb.add_output('voutdm', """getData("/vout" ?result "pss_td")""")
        tb.add_output('voutcm', """getData("/voutcm" ?result "pss_td")""")
