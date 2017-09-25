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


yaml_file = pkg_resources.resource_filename(__name__, os.path.join('netlist_info', 'load_pmos.yaml'))


# noinspection PyPep8Naming
class bag_serdes_ec__load_pmos(Module):
    """Module for library bag_serdes_ec cell load_pmos.

    A pmos load cell with option to add output decaps (for integrator application).
    """

    param_list = ['lch', 'w_dict', 'th_dict', 'seg_dict', 'dum_info']

    def __init__(self, bag_config, parent=None, prj=None, **kwargs):
        Module.__init__(self, bag_config, yaml_file, parent=parent, prj=prj, **kwargs)
        for par in self.param_list:
            self.parameters[par] = None

    def design(self, lch=16e-9, w_dict=None, th_dict=None, seg_dict=None, dum_info=None):
        # type: (float, Dict[str, Union[float, int]], Dict[str, str], Dict[str, int], List[Tuple[Any]]) -> None
        """Design this load cell.

        The load cell uses 1 row of transistors.  The row is named 'load'.

        The transistor names are 'load', 'load_ref', and 'load_cap'.  seg_dict maps
        transistor name to single-sided number of fingers, except for load_ref, which
        maps to total number of fingers.

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

        # load
        fg = seg_dict['load']
        w = w_dict['load']
        th = th_dict['load']
        self.instances['XLOADP'].design(w=w, l=lch, nf=fg, intent=th)
        self.instances['XLOADN'].design(w=w, l=lch, nf=fg, intent=th)

        # load decap
        fg = seg_dict.get('load_cap', 0)
        if fg <= 0:
            self.delete_instance('XCAPP')
            self.delete_instance('XCAPN')
        else:
            self.instances['XCAPP'].design(w=w, l=lch, nf=fg, intent=th)
            self.instances['XCAPN'].design(w=w, l=lch, nf=fg, intent=th)

        # load reference
        fg = seg_dict.get('load_ref', 0)
        if fg <= 0:
            self.delete_instance('XREF')
        else:
            self.instances['XREF'].design(w=w, l=lch, nf=fg, intent=th)

        # handle dummy transistors
        self.design_dummy_transistors(dum_info, 'XDUM', 'VDD', 'VSS')
