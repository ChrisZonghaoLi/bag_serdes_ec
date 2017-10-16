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

    This is the schematic for a testbench that runs a PSS simulation on a clocked circuit.
    """

    param_list = ['dut_lib', 'dut_cell', 'dut_conns', 'vbias_dict', 'ibias_dict',
                  'tran_fname', 'clk_params_list', 'no_cload']

    def __init__(self, bag_config, parent=None, prj=None, **kwargs):
        Module.__init__(self, bag_config, yaml_file, parent=parent, prj=prj, **kwargs)
        for par in self.param_list:
            self.parameters[par] = None

    def design(self, dut_lib='', dut_cell='', dut_conns=None, vbias_dict=None, ibias_dict=None,
               tran_fname='', clk_params_list=None, no_cload=False):
        """Design the testbench schematic.

        The testbench contains a periodic PWL voltage source, variable number of DC voltage/current
        biases, variable number of ideal clock sources, and a optional output capacitor load.
        the input PWL voltage net is 'vin' and the output capacitor net is 'vout'.

        The necessary simulation parameters are:

        cload : the load capacitance.
        vdd : the supply voltage.
        gain : the PWL voltage source will be scaled by this amount.
        vindc : the input DC voltage offset.  Final input value is gain * PWL + vindc.
        nharm : number of PSS output harmonics.
        tper_pss : the PSS simulation period.

        Parameters
        ----------
        dut_lib : str
            the DUT library name.
        dut_cell : str
            the DUT cell name.
        dut_conns: Dict[str, str]
            a dictionary from DUT pin name to net name.  Used to connect DUT to the testbench.
        vbias_dict : Dict[str, Tuple[str, str, Union[str, float]]]
            the DC voltage bias dictionary.  key is the bias source name, value is a tuple of
            positive net name, negative net name, and bias value (as a number or as a variable
            name).
        ibias_dict : Dict[str, Tuple[str, str, Union[str, float]]]
            the DC current bias dictionary.  Same format as vbias_dict.
        tran_fname : str
            the PWL signal file name.
        clk_params_list : List[Dict[str, Any]]
            A list of dictionaries of all clock sources needed.  Each dictionary should have the
            following entries;

            name : str
                name of this clock source.
            master : Tuple[str, str]
                the clock master library/cell name.  This is used to switch from pulse sources to PWL or
                sinusoidal sources.  If not specified, defaults to pulse sources.
            conns : Dict[str, str]
                a dictionary from clock source pin name to net name.
            params : Dict[str, Any]
                the parameter dictionary for the clock source.  All parameters should be specified.
        no_cload : bool
            True to remove the capacitive output load.
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

        # convert tran_fname to absolute path
        tran_fname = os.path.abspath(tran_fname)

        local_dict = locals()
        for name in self.param_list:
            if name not in local_dict:
                raise ValueError('Parameter %s not specified.' % name)
            self.parameters[name] = local_dict[name]

        # setup bias sources
        self.design_dc_bias_sources(vbias_dict, ibias_dict, 'VSUP', 'IBIAS', define_vdd=True)

        # setup pwl source
        if not os.path.isfile(tran_fname):
            raise ValueError('%s is not a file.' % tran_fname)
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
        name_list = ['V' + clk_params['name'] for clk_params in clk_params_list]
        self.array_instance(ck_inst, name_list)
        for idx, clk_params in enumerate(clk_params_list):
            if 'master' in clk_params:
                vck_lib, vck_cell = clk_params['master']
                self.replace_instance_master(ck_inst, vck_lib, vck_cell, static=True, index=idx)

            for term, net in clk_params['conns'].items():
                self.reconnect_instance_terminal(ck_inst, term, net, index=idx)

            for key, val in clk_params['params'].items():
                if isinstance(val, str):
                    pass
                elif isinstance(val, int) or isinstance(val, float):
                    val = float_to_si_string(val)
                else:
                    raise ValueError('value %s of type %s not supported' % (val, type(val)))
                self.instances[ck_inst][idx].parameters[key] = val
