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

from __future__ import (absolute_import, division,
                        print_function, unicode_literals)
# noinspection PyUnresolvedReferences,PyCompatibility
from builtins import *

import os
import pkg_resources

from bag import float_to_si_string
from bag.design import Module


yaml_file = pkg_resources.resource_filename(__name__, os.path.join('netlist_info', 'clkamp_tb_pss.yaml'))


# noinspection PyPep8Naming
class bag_serdes_ec__clkamp_tb_pss(Module):
    """Module for library bag_serdes_ec cell clkamp_tb_pss.

    Fill in high level description here.
    """

    param_list = ['dut_lib', 'dut_cell', 'dut_conns', 'vbias_dict', 'ibias_dict',
                  'tran_fname', 'clk_params_list', 'no_cload']

    def __init__(self, bag_config, parent=None, prj=None, **kwargs):
        Module.__init__(self, bag_config, yaml_file, parent=parent, prj=prj, **kwargs)
        for par in self.param_list:
            self.parameters[par] = None

    def design(self, dut_lib='', dut_cell='', dut_conns=None, vbias_dict=None, ibias_dict=None,
               tran_fname='', clk_params_list=None, no_cload=False):
        """To be overridden by subclasses to design this module.

        This method should fill in values for all parameters in
        self.parameters.  To design instances of this module, you can
        call their design() method or any other ways you coded.

        To modify schematic structure, call:

        rename_pin()
        delete_instance()
        replace_instance_master()
        reconnect_instance_terminal()
        restore_instance()
        array_instance()
        """
        # initialization and error checking
        if vbias_dict is None:
            vbias_dict = {}
        if ibias_dict is None:
            ibias_dict = {}
        if dut_conns is None:
            dut_conns = {}
        if not clk_params_list:
            raise ValueError('clk parameters not specified.')

        local_dict = locals()
        for name in self.param_list:
            if name not in local_dict:
                raise ValueError('Parameter %s not specified.' % name)
            self.parameters[name] = local_dict[name]

        # setup bias sources
        self.design_dc_bias_sources(vbias_dict, ibias_dict, 'VSUP', 'IBIAS', define_vdd=True)

        # setup pwl source
        self.instances['VIN'].parameters['fileName'] = tran_fname

        # delete load cap if needed
        if no_cload:
            self.delete_instance('CLOAD')

        # setup DUT
        self.replace_instance_master('XDUT', dut_lib, dut_cell, static=True)
        for term_name, net_name in dut_conns.items():
            self.reconnect_instance_terminal('XDUT', term_name, net_name)

        # setup clocks
        ck_inst = 'VCK'
        num_clk = len(clk_params_list)
        name_list = [clk_params['name'] for clk_params in clk_params_list]
        self.array_instance(ck_inst, name_list)
        for idx, clk_params in enumerate(clk_params_list):
            if 'master' in clk_params:
                vck_lib, vck_cell = clk_params['master']
                self.replace_instance_master(ck_inst, vck_lib, vck_cell, static=True, index=idx)
            for key, val in clk_params['params'].items():
                if isinstance(val, str):
                    pass
                elif isinstance(val, int) or isinstance(val, float):
                    val = float_to_si_string(val)
                else:
                    raise ValueError('value %s of type %s not supported' % (val, type(val)))
                self.instances[ck_inst][idx].parameters[key] = val
