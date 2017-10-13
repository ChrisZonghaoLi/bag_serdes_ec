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


from typing import TYPE_CHECKING, Optional, Tuple, Any, Dict

from bag.tech.core import SimulationManager

if TYPE_CHECKING:
    from bag.core import BagProject, Testbench


class ClkAmpChar(SimulationManager):
    def __init__(self, prj, spec_file):
        # type: (Optional[BagProject], str) -> None
        super(ClkAmpChar, self).__init__(prj, spec_file)
        combo_list = list(self.get_combinations_iter())

        if len(combo_list) != 1:
            raise ValueError('This characterization class does not support sweeping design parameters.')

        self._val_list = combo_list[0]

    def get_layout_params(self, val_list):
        # type: (Tuple[Any, ...]) -> Dict[str, Any]
        lay_params = self.specs['layout_params'].copy()
        for var, val in zip(self.swp_var_list, val_list):
            lay_params[var] = val

        return lay_params

    def get_tb_sch_params(self, tb_type, val_list):
        # type: (str, Tuple[Any, ...]) -> Dict[str, Any]
        return self.specs[tb_type]['sch_params']

    def configure_tb(self, tb_type, tb, val_list):
        # type: (str, Testbench, Tuple[Any, ...]) -> None
        tb_specs = self.specs[tb_type]
        sim_envs = self.specs['sim_envs']
        view_name = self.specs['view_name']
        impl_lib = self.specs['impl_lib']
        dsn_name_base = self.specs['dsn_name_base']
        tb_params_real = self.specs['feedback_params'].copy()

        tb_params = tb_specs['tb_params']
        dsn_name = self.get_instance_name(dsn_name_base, val_list)

        tb.set_simulation_environments(sim_envs)
        tb.set_simulation_view(impl_lib, dsn_name, view_name)

        tb_params_real.update(tb_params)
        for key, val in tb_params_real.items():
            if isinstance(val, list):
                tb.set_sweep_parameter(key, values=val)
            else:
                tb.set_parameter(key, val)
