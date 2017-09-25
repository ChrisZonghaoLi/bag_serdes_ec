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
from typing import Dict, Union, List, Tuple, Any

from bag.design import Module


yaml_file = pkg_resources.resource_filename(__name__, os.path.join('netlist_info', 'diffamp.yaml'))


# noinspection PyPep8Naming
class bag_serdes_ec__diffamp(Module):
    """Module for library bag_serdes_ec cell diffamp.

    A differential amplifier cell with many options used mainly for SERDES circuits
    """

    param_list = ['lch', 'w_dict', 'th_dict', 'seg_dict', 'dum_info']

    def __init__(self, bag_config, parent=None, prj=None, **kwargs):
        Module.__init__(self, bag_config, yaml_file, parent=parent, prj=prj, **kwargs)
        for par in self.param_list:
            self.parameters[par] = None

    def design(self,
               lch=16e-9,  # type: float
               w_dict=None,  # type: Dict[str, Union[float, int]]
               th_dict=None,  # type: Dict[str, str]
               seg_dict=None,  # type: Dict[str, int]
               dum_info=None,  # type: List[Tuple[Any]]
               ):
        # type: (...) -> None
        """Design this differential amplifier.

        The differential amplifier cell uses at most 6 rows of transistors.  The row types from top to
        bottom are 'load', 'casc', 'in', 'sw', 'en', and 'tail'.

        for seg_dict, see documentation for Gm and load_pmos generator.

        Parameters
        ----------
        lch : float
            channel length, in meters.
        w_dict : Dict[str, Union[float, int]]
            dictionary from row type to transistor width, in fins or meters.
        th_dict : Dict[str, str]
            dictionary from row type to transistor threshold flavor.
        seg_dict : Dict[str, int]
            dictionary from transistor type to single-sided number of fingers.
        dum_info : List[Tuple[Any]]
            the dummy information data structure.
        """
        local_dict = locals()
        for name in self.param_list:
            if name not in local_dict:
                raise ValueError('Parameter %s not specified.' % name)
            self.parameters[name] = local_dict[name]

        # separate dummy information into gm and load
        gm_dum_info, load_dum_info = [], []
        for item in dum_info:
            if item[0][0] == 'nch':
                gm_dum_info.append(item)
            else:
                load_dum_info.append(item)

        self.instances['XGM'].design(lch=lch, w_dict=w_dict, th_dict=th_dict,
                                     seg_dict=seg_dict, dum_info=gm_dum_info)
        self.instances['XLOAD'].design(lch=lch, w_dict=w_dict, th_dict=th_dict,
                                       seg_dict=seg_dict, dum_info=load_dum_info)

        # remove unused pins
        if seg_dict.get('casc', 0) <= 0:
            self.remove_pin('bias_casc')
        if seg_dict.get('sw', 0) <= 0:
            self.remove_pin('vddn')
            self.remove_pin('clk_sw')
        if seg_dict.get('en', 0) <= 0:
            self.remove_pin('enable')
