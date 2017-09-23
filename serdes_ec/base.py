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
from future.utils import with_metaclass

import abc
from typing import TYPE_CHECKING, Optional, Dict, Any, Set, Tuple, List, Union


from abs_templates_ec.analog_core import AnalogBase, AnalogBaseInfo

if TYPE_CHECKING:
    from bag.layout.routing import RoutingGrid, WireArray
    from bag.layout.template import TemplateDB


class SerdesRXBaseInfo(AnalogBaseInfo):
    """A class that calculates informations to assist in SerdesRXBase layout calculations.

    Parameters
    ----------
    grid : RoutingGrid
        the RoutingGrid object.
    lch : float
        the channel length of AnalogBase, in meters.
    guard_ring_nf : int
        guard ring width in number of fingers.  0 to disable.
    top_layer : Optional[int]
        the AnalogBase top layer ID.
    end_mode : int
        right/left/top/bottom end mode flag.  This is a 4-bit integer.  If bit 0 (LSB) is 1, then
        we assume there are no blocks abutting the bottom.  If bit 1 is 1, we assume there are no
        blocks abutting the top.  bit 2 and bit 3 (MSB) corresponds to left and right, respectively.
        The default value is 15, which means we assume this AnalogBase is surrounded by empty spaces.
    min_fg_sep : int
        minimum number of separation fingers.
    fg_tot : Optional[int]
        number of fingers in a row.
    """

    def __init__(self, grid, lch, guard_ring_nf, top_layer=None, end_mode=15, min_fg_sep=0, fg_tot=None):
        # type: (RoutingGrid, float, int, Optional[int], int, int, Optional[int]) -> None
        super(SerdesRXBaseInfo, self).__init__(grid, lch, guard_ring_nf, top_layer=top_layer,
                                               end_mode=end_mode, min_fg_sep=min_fg_sep, fg_tot=fg_tot)

    def get_gm_info(self, fg_dict):
        # type: (Dict[str, int]) -> Dict[str, int]
        """Return Gm layout information dictionary.

        This method computes how many fingers the Gm cell will occupy, and the number of edge
        dummies needed.

        Parameters
        ----------
        fg_dict : Dict[str, int]
            a dictionary containing number of fingers per transistor type.
            in addition to transistor types, you can specify the following entries:

            min :
                minimum number of total fingers.
            sep_min :
                minimum number of fingers that separates the differential sides.

        Returns
        -------
        info : Dict[str, int]
            the Gm stage layout information dictionary.  Has the following entries:

            fg_single : int
                number of single-sided fingers.
            fg_sep : int
                number of fingers separating the differential sides.
            fg_tot : int
                total number of Gm fingers.
            fg_dum : int
                number of dummy fingers on each edge.
        """
        # error checking
        for fg_name, fg_val in fg_dict.items():
            if fg_val % 2 != 0:
                raise ValueError('fg_%s = %d must be even' % (fg_name, fg_val))
            if fg_name == 'tail_cap' and fg_val % 4 != 0:
                raise ValueError('fg_tail_cap = %d must be multiples of 4.' % fg_val)

        # determine number of separation fingers
        fg_cas = fg_dict.get('casc', 0)
        fg_ref = fg_dict.get('tail_ref', 0)
        fg_sep_min = fg_dict.get('sep_min', 0)
        if fg_cas == 0 and fg_sep_min == 0 and fg_ref == 0 and self.abut_analog_mos:
            # do not need to separate differential sides
            fg_sep = 0
        else:
            # need to separate differential sides
            fg_sep = max(self.min_fg_sep, fg_sep_min)
            if fg_ref > 0:
                fg_sep = max(fg_sep, fg_ref + 2 * self.min_fg_sep)
                # make sure fg_ref has same number of dummies on the left and right.
                if (fg_sep - fg_ref) % 2 != 0:
                    fg_sep += 1

        # determine maximum number of single-sided fingers
        fg_cap = fg_dict.get('tail_cap', 0)
        valid_keys = ['casc', 'in', 'sw', 'en']
        fg_single = max((fg_dict.get(key, 0) for key in valid_keys))
        fg_single = max(fg_single, fg_dict['tail'] + fg_cap)

        # get total number of fingers and number of dummies on each edge.
        fg_tot = fg_single * 2 + fg_sep
        fg_min = fg_dict.get('min', 0)
        if fg_tot < fg_min:
            # add dummies to get to fg_min
            if (fg_min - fg_tot) % 2 != 0:
                raise ValueError('fg_min = %d and fg_tot = %d difference must be even' % (fg_min, fg_tot))

            fg_dum = (fg_min - fg_tot) // 2
            fg_tot = fg_min
        else:
            fg_dum = 0

        # determine output source/drain type.
        results = dict(
            fg_single=fg_single,
            fg_sep=fg_sep,
            fg_tot=fg_tot,
            fg_dum=fg_dum,
        )

        return results


class SerdesRXBase(with_metaclass(abc.ABCMeta, AnalogBase)):
    """Subclass of AmplifierBase that draws serdes circuits.

    To use this class, :py:meth:`draw_rows` must be the first function called,
    which will call :py:meth:`draw_base` for you with the right arguments.

    Parameters
    ----------
    temp_db : :class:`bag.layout.template.TemplateDB`
            the template database.
    lib_name : str
        the layout library name.
    params : dict[str, any]
        the parameter values.
    used_names : set[str]
        a set of already used cell names.
    **kwargs
        optional parameters.  See documentation of
        :class:`bag.layout.template.TemplateBase` for details.
    """

    def __init__(self, temp_db, lib_name, params, used_names, **kwargs):
        # type: (TemplateDB, str, Dict[str, Any], Set[str], **Any) -> None
        super(SerdesRXBase, self).__init__(temp_db, lib_name, params, used_names, **kwargs)
        self._nrow_idx = None
        self._serdes_info = None  # type: SerdesRXBaseInfo

    @property
    def layout_info(self):
        # type: () -> SerdesRXBaseInfo
        return self._serdes_info

    def get_nmos_row_index(self, name):
        # type: (str) -> int
        """Returns the index of the given nmos row type.

        Parameters
        ----------
        name : str
            the nmos row name.

        Returns
        -------
        row_idx : the row index.
        """
        if name not in self._nrow_idx:
            raise ValueError('row %s not found.' % name)
        return self._nrow_idx.get[name]

    @staticmethod
    def _flip_sd(name):
        return 'd' if name == 's' else 's'

    @staticmethod
    def _get_diff_names(name_base, is_diff, invert=False):
        if is_diff:
            if invert:
                return name_base + 'n', name_base + 'p'
            else:
                return name_base + 'p', name_base + 'n'
        return name_base, name_base

    @staticmethod
    def _append_to_warr_dict(warr_dict, name, warr):
        if name not in warr_dict:
            warr_dict[name] = []
        warr_dict[name].append(warr)

    def draw_gm(self,  # type: SerdesRXBase
                col_idx,  # type: int
                fg_dict,  # type: Dict[str, int]
                tr_widths=None,  # type: Optional[Dict[str, Dict[int, int]]]
                tr_spaces=None,  # type: Optional[Dict[Union[str, Tuple[str, str]], Dict[int, int]]]
                tr_indices=None,  # type: Optional[Dict[str, int]]
                flip_sd=False,  # type: bool
                ):
        # type: (...) -> Tuple[int, Dict[str, List[WireArray]]]
        """Draw a differential gm stage.

        a separator is used to separate the positive half and the negative half of the gm stage.
        For tail/switch/enable devices, the g/d/s of both halves are shorted together.

        Parameters
        ----------
        col_idx : int
            the left-most transistor index.  0 is the left-most transistor.
        fg_dict : Dict[str, int]
            a dictionary containing number of fingers per transistor type.
            in addition to transistor types, you can specify the following entries:

            min :
                minimum number of total fingers.
            sep_min :
                minimum number of fingers that separates the differential sides.
        tr_widths : Optional[Dict[str, Dict[int, int]]]
            the track width dictionary.
        tr_spaces : Optional[Dict[Union[str, Tuple[str, str]], Dict[int, int]]]
            the track spacing dictionary.
        tr_indices : Optional[Dict[str, int]]
            the track index dictionary.  Maps from net name to relative track index.
        flip_sd : bool
            True to flip source/drain.  This is to help draw layout where certain configuration
            of number of fingers and source/drain directions may not be possible.

        Returns
        -------
        fg_gm : int
            width of Gm stage in number of fingers.
        port_dict : Dict[str, List[WireArray]]
            a dictionary from connection name to WireArrays.  Outputs are on mos_conn_layer,
            and rests are on the layer above that.
        """
        if tr_widths is None:
            tr_widths = {}
        if tr_spaces is None:
            tr_spaces = {}
        if tr_indices is None:
            tr_indices = {}

        # get layout information
        gm_info = self._serdes_info.get_gm_info(fg_dict)
        fg_single = gm_info['fg_single']
        fg_sep = gm_info['fg_sep']
        fg_tot = gm_info['fg_tot']
        fg_dum = gm_info['fg_dum']

        # draw cascode
        tran_type = 'casc'
        up_type = 's' if flip_sd else 'd'
        up_name = 'out'
        dn_name = 'mid'
        g_name = 'bias_casc'
        g_diff = False
        d_diff = True
        s_diff = True
        warr_dict = {}

        row_idx = self.get_nmos_row_index(tran_type)
        fg = fg_dict.get(tran_type, 0)
        fg_diff = fg_dum + (fg_single - fg) // 2

        if up_type == 'd':
            ddir, sdir = 2, 0
            d_name, s_name = up_name, dn_name
        else:
            ddir, sdir = 0, 2
            d_name, s_name = dn_name, up_name

        g_name_p, g_name_n = self._get_diff_names(g_name, g_diff)
        d_name_p, d_name_n = self._get_diff_names(d_name, d_diff, invert=True)
        s_name_p, s_name_n = self._get_diff_names(s_name, s_diff, invert=True)

        p_warrs = self.draw_mos_conn('nch', row_idx, col_idx + fg_diff, fg, sdir, ddir,
                                     net_left=s_name_p, net_right=s_name_n)
        n_warrs = self.draw_mos_conn('nch', row_idx, col_idx + fg_tot - fg_diff, fg, sdir, ddir,
                                     net_left=s_name_p, net_right=s_name_n)
        self._append_to_warr_dict(warr_dict, g_name_p, p_warrs['g'])
        self._append_to_warr_dict(warr_dict, d_name_p, p_warrs['d'])
        self._append_to_warr_dict(warr_dict, s_name_p, p_warrs['s'])
        self._append_to_warr_dict(warr_dict, g_name_n, n_warrs['g'])
        self._append_to_warr_dict(warr_dict, d_name_n, n_warrs['d'])
        self._append_to_warr_dict(warr_dict, s_name_n, n_warrs['s'])
