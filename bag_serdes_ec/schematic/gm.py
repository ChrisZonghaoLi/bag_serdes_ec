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


yaml_file = pkg_resources.resource_filename(__name__, os.path.join('netlist_info', 'gm.yaml'))


# noinspection PyPep8Naming
class bag_serdes_ec__gm(Module):
    """Module for library bag_serdes_ec cell gm.

    A Gm cell with many options used mainly for SERDES circuits.
    """

    param_list = ['lch', 'w_dict', 'th_dict', 'seg_dict', 'dum_info']

    def __init__(self, bag_config, parent=None, prj=None, **kwargs):
        Module.__init__(self, bag_config, yaml_file, parent=parent, prj=prj, **kwargs)
        for par in self.param_list:
            self.parameters[par] = None

    def design(self, lch=16e-9, w_dict=None, th_dict=None, seg_dict=None, dum_info=None):
        # type: (float, Dict[str, Union[float, int]], Dict[str, str], Dict[str, int], List[Tuple[Any]]) -> None
        """Design this Gm cell.

        The Gm cell uses at most 5 rows of transistors.  The row types from top to
        bottom are 'casc', 'in', 'sw', 'en', and 'tail'.

        The transistor names are 'casc', 'in', 'sw', 'en', 'tail', 'tail_ref', and 'tail_cap'.
        seg_dict maps from transistor name to single-sided number of fingers, except
        for tail_ref and tail_cap, which maps to total number of fingers.

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

        # design each transistor, from top to bottom
        # cascode
        fg = seg_dict.get('casc', 0)
        if fg <= 0:
            in_dname = 'out'
            self.delete_instance('XCASP')
            self.delete_instance('XCASN')
            self.remove_pin('bias_casc')
        else:
            in_dname = 'mid'
            w = w_dict['casc']
            th = th_dict['casc']
            self.instances['XCASP'].design(w=w, l=lch, nf=fg, intent=th)
            self.instances['XCASN'].design(w=w, l=lch, nf=fg, intent=th)

        # input
        fg = seg_dict['in']
        w = w_dict['in']
        th = th_dict['in']
        self.instances['XINP'].design(w=w, l=lch, nf=fg, intent=th)
        self.instances['XINN'].design(w=w, l=lch, nf=fg, intent=th)
        self.reconnect_instance_terminal('XINP', 'D', '%sn' % in_dname)
        self.reconnect_instance_terminal('XINN', 'D', '%sp' % in_dname)

        # tail switch
        fg = seg_dict.get('sw', 0)
        if fg <= 0:
            self.delete_instance('XSWP')
            self.delete_instance('XSWN')
            self.remove_pin('clk_sw')
            self.remove_pin('vddn')
        else:
            w = w_dict['sw']
            th = th_dict['sw']
            self.instances['XSWP'].design(w=w, l=lch, nf=fg, intent=th)
            self.instances['XSWN'].design(w=w, l=lch, nf=fg, intent=th)

        # tail enable
        fg = seg_dict.get('en', 0)
        if fg <= 0:
            tail_dname = 'tail'
            self.delete_instance('XENP')
            self.delete_instance('XENN')
            self.remove_pin('enable')
        else:
            tail_dname = 'foot'
            w = w_dict['en']
            th = th_dict['en']
            self.instances['XENP'].design(w=w, l=lch, nf=fg, intent=th)
            self.instances['XENN'].design(w=w, l=lch, nf=fg, intent=th)

        # tail
        fg = seg_dict['tail']
        w = w_dict['tail']
        th = th_dict['tail']
        self.instances['XTAILP'].design(w=w, l=lch, nf=fg, intent=th)
        self.instances['XTAILN'].design(w=w, l=lch, nf=fg, intent=th)
        self.reconnect_instance_terminal('XTAILP', 'D', tail_dname)
        self.reconnect_instance_terminal('XTAILN', 'D', tail_dname)

        # reference
        fg = seg_dict.get('tail_ref', 0)
        if fg <= 0:
            self.delete_instance('XREF')
        else:
            self.instances['XREF'].design(w=w, l=lch, nf=fg, intent=th)

        # tail decap
        fg = seg_dict.get('tail_cap', 0)
        if fg <= 0:
            self.delete_instance('XCAP')
        else:
            self.instances['XCAP'].design(w=w, l=lch, nf=fg, intent=th)

        # handle dummy transistors
        self.design_dummy_transistors(dum_info, 'XDUM', 'VDD', 'VSS')
