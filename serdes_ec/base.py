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


def _flip_sd(name):
    # type: (str) -> str
    return 'd' if name == 's' else 's'


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

    def _get_gm_tran_info(self, seg_dict, fg_center, out_on_source):
        # type: (Dict[str, int], int, bool) -> Tuple[Dict[str, Tuple[Union[int, str]]], bool]
        tran_types = ['casc', 'in', 'sw', 'en', 'tail']
        dn_names = ['mid', 'tail', 'tail', 'foot', 'VSS']
        centers = [True, True, False, False, False]

        # we need separation if we use cascode transistor or if technology cannot abut transistors
        fg_cas = seg_dict.get('fg_cas', 0)
        need_sep = fg_cas > 0 or not self.abut_analog_mos

        tran_info = {}
        up_name = 'out'
        up_type = 's' if out_on_source else 'd'
        fg_prev = fg_diff = 0
        for tran_type, dn_name, center in zip(tran_types, dn_names, centers):
            fg = seg_dict.get(tran_type, 0)
            if fg > 0:
                # first compute fg_diff (# fingers between inner edge and center) and up wire type.
                if center:
                    # we align the center of this transistor
                    fg_diff = (fg_center - fg) // 2
                    # because we align at the center, check if we need to flip source/drain
                    if fg_prev > 0 and (fg - fg_prev) % 4 != 0:
                        up_type = _flip_sd(up_type)
                else:
                    # we align the inner edge of this transistor towards the center,
                    # but at the same time we want to minimize number of vertical wires.

                    # if previous row has same or more fingers than current row,
                    # to minimize vertical wires and horizontal resistance, we align
                    # the inner edges of the two rows.  As the result, fg_diff and
                    # up_type does not change.
                    if fg_prev < fg:
                        # previous row has less fingers than current row.
                        # compute total fingers in previous row
                        fg_prev_tot = fg_prev + fg_diff
                        if up_type == 'd':
                            fg_prev_tot -= 1

                        if fg_prev_tot >= fg:
                            # current row can fit under previous row.  In this case,
                            # to minimize vertical wires, we align the outer edge,
                            # so up_type has to change.
                            fg_diff = fg_prev_tot - fg
                            up_type = 's'
                        else:
                            # current row extends beyond previous row.  In this case,
                            # we need to recompute what up_type is
                            fg_diff = 0
                            up_type = 's' if (fg_prev_tot - fg) % 2 == 0 else 'd'

                if tran_type == 'sw':
                    # for tail switch transistor it's special; the down wire type is the
                    # same as down wire type of input, and up wire is always VDD.
                    up_name = 'VDD'
                    up_type = _flip_sd(up_type)

                # we need separation if there's unused middle transistors on any row
                if fg_diff > 0:
                    need_sep = True
                # record transistor information
                if up_type == 's':
                    tran_info[tran_type] = (fg_diff, dn_name, up_name, 0, 2)
                else:
                    tran_info[tran_type] = (fg_diff, up_name, dn_name, 2, 0)

                # compute information for next row
                fg_prev = fg
                up_name = dn_name
                up_type = _flip_sd(up_type)

        return tran_info, need_sep

    def get_gm_info(self, seg_dict, fg_min=0, fg_dum=0, fg_load=0, fg_load_sep_min=0, out_on_source=False):
        # type: (Dict[str, int], int, int, int, int, bool) -> Dict[str, int]
        """Return Gm layout information dictionary.

        This method computes layout information about the Gm cell.

        Parameters
        ----------
        seg_dict : Dict[str, int]
            a dictionary containing number of segments per transistor type.
        fg_min : int
            minimum number of total fingers.
        fg_load : int
            number of load fingers this Gm cell connects to.  0 if not known.
        fg_load_sep_min : int
            minimum number of fingers separating the differential load.  0 if not known.
        fg_dum : int
            minimum single-sided number of dummy fingers.
        out_on_source : bool
            True to draw output on source instead of drain.

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
        fg_cap = seg_dict.get('tail_cap', 0)
        if fg_cap % 4 != 0:
            raise ValueError('fg_tail_cap = %d must be multiples of 4.' % fg_cap)
        for even_name in ('casc', 'in', 'tail_ref'):
            seg_cur = seg_dict.get(even_name, 0)
            if seg_cur % 2 != 0:
                raise ValueError('seg_%s = %d must be even.' % (even_name, seg_cur))

        # determine number of center fingers
        fg_casc = seg_dict.get('casc', 0)
        fg_in = seg_dict.get('in', 0)
        fg_center = max(fg_load, fg_casc, fg_in)

        # get source and drain information
        tran_info, need_sep = self._get_gm_tran_info(seg_dict, fg_center, out_on_source)

        # find number of separation fingers
        fg_sep = 0
        # fg_sep from load reference constraint
        fg_diff_load = (fg_center - fg_load) // 2
        fg_sep = max(fg_sep, fg_load_sep_min - 2 * fg_diff_load)
        # fg_sep from tail reference constraint
        fg_ref = seg_dict.get('tail_ref', 0)
        tail_info = tran_info['tail']
        fg_diff_tail = tail_info[0]
        if fg_ref > 0:
            # NOTE: we always need separation between tail reference and tail transistors,
            # otherwise middle dummies in other nmos rows cannot be connected.
            fg_sep = max(fg_sep, fg_ref + 2 * (self.min_fg_sep - fg_diff_tail))
        # fg_sep from need_sep constraint
        if need_sep:
            for info in tran_info.values():
                fg_sep = max(fg_sep, self.min_fg_sep - 2 * info[0])

        # determine number of side fingers
        fg_side = 0
        # get side fingers for sw and en row
        for key in ('sw', 'en'):
            if key in tran_info:
                fg_cur = seg_dict[key]
                fg_side = max(fg_side, tran_info[key][0] + fg_cur)
        # get side fingers for tail row.  Take tail decap into account
        fg_tail = seg_dict['tail']
        fg_cap = seg_dict.get('tail_cap', 0)
        if fg_cap > 0:
            fg_tail_tot = fg_diff_tail + fg_tail + fg_cap
            tail_s_name = tail_info[2]
            if not (tail_s_name == 'VSS' and self.abut_analog_mos):
                # we need to separate tail decap and tail transistor
                fg_tail_tot += self.min_fg_sep
        else:
            fg_tail_tot = fg_diff_tail + fg_tail
        fg_side = max(fg_side, fg_tail_tot)

        # get total number of fingers and number of dummies on each edge.
        fg_tot = max(fg_center, fg_side) * 2 + fg_sep + 2 * fg_dum
        if fg_tot < fg_min:
            # add dummies to get to fg_min
            if (fg_min - fg_tot) % 2 != 0:
                fg_min += 1

            fg_dum = (fg_min - fg_tot) // 2
            fg_tot = fg_min

        # determine output source/drain type.
        results = dict(
            fg_tot=fg_tot,
            fg_center=fg_center,
            fg_side=fg_side,
            fg_sep=fg_sep,
            fg_dum=fg_dum,
            fg_tail_tot=fg_tail_tot,
            tran_info=tran_info,
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

    def _draw_gm_mos(self, col_idx, fg_tot, fg_single, fg_dum, warr_dict, tran_type, fg,
                     up_name, dn_name, g_name, up_type, g_diff, d_diff, s_diff, center):

        if center:
            fg_diff = fg_dum + (fg_single - fg) // 2
        else:
            fg_diff = fg_dum + fg_single - fg

        if up_type == 'd':
            ddir, sdir = 2, 0
            d_name, s_name = up_name, dn_name
        else:
            ddir, sdir = 0, 2
            d_name, s_name = dn_name, up_name

        g_name_p, g_name_n = self._get_diff_names(g_name, g_diff)
        d_name_p, d_name_n = self._get_diff_names(d_name, d_diff, invert=True)
        s_name_p, s_name_n = self._get_diff_names(s_name, s_diff, invert=True)

        row_idx = self.get_nmos_row_index(tran_type)
        p_warrs = self.draw_mos_conn('nch', row_idx, col_idx + fg_diff, fg, sdir, ddir,
                                     s_net=s_name_p, d_net=d_name_p)
        n_warrs = self.draw_mos_conn('nch', row_idx, col_idx + fg_tot - fg_diff, fg, sdir, ddir,
                                     s_net=s_name_n, d_net=d_name_n)
        self._append_to_warr_dict(warr_dict, g_name_p, p_warrs['g'])
        self._append_to_warr_dict(warr_dict, d_name_p, p_warrs['d'])
        self._append_to_warr_dict(warr_dict, s_name_p, p_warrs['s'])
        self._append_to_warr_dict(warr_dict, g_name_n, n_warrs['g'])
        self._append_to_warr_dict(warr_dict, d_name_n, n_warrs['d'])
        self._append_to_warr_dict(warr_dict, s_name_n, n_warrs['s'])

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
        fg_tot = gm_info['fg_tot']
        fg_dum = gm_info['fg_dum']

        # transistor settings
        tran_types = ['casc', 'in', 'sw', 'en', 'tail']
        dn_names = ['mid', 'tail', 'tail', 'foot', 'VSS']
        g_names = ['bias_casc', 'in', 'clk_sw', 'enable', 'bias_tail']
        g_diffs = [False, True, False, False, False]
        d_diffs = [True, True, False, False, False]
        s_diffs = [True, False, False, False, False]
        centers = [True, True, False, False, False]

        # draw main transistors and collect ports
        warr_dict = {}
        up_type = 's' if flip_sd else 'd'
        up_name = 'out'
        tail_up_type = 'd'
        for tran_type, dn_name, g_name, g_diff, d_diff, s_diff, center in \
                zip(tran_types, dn_names, g_names, g_diffs, d_diffs, s_diffs, centers):
            fg = fg_dict.get(tran_type, 0)
            if fg > 0:
                if tran_type == 'sw':
                    # for switch the down net is always equal to the down net of input.
                    up_name = 'VDD'
                    up_type = self._flip_sd(up_type)
                if tran_type == 'tail':
                    tail_up_type = up_type
                self._draw_gm_mos(col_idx, fg_tot, fg_single, fg_dum, warr_dict, tran_type, fg,
                                  up_name, dn_name, g_name, up_type, g_diff, d_diff, s_diff, center)
                up_name = dn_name
                up_type = self._flip_sd(up_type)

        # draw reference transistor
        row_idx = self.get_nmos_row_index('tail')
        fg = fg_dict.get('tail_ref', 0)
        if fg > 0:
            if tail_up_type == 'd':
                sdir, ddir = 0, 2
                s_net, d_net = 'VSS', 'bias_tail'
            else:
                sdir, ddir = 2, 0
                s_net, d_net = 'bias_tail', 'VSS'
            warrs = self.draw_mos_conn('nch', row_idx, col_idx + fg_dum + fg_single + self.min_fg_sep,
                                       fg, sdir, ddir, s_net=s_net, d_net=d_net)
            self._append_to_warr_dict(warr_dict, 'bias_tail', warrs['g'])
            self._append_to_warr_dict(warr_dict, d_net, warrs['d'])
            self._append_to_warr_dict(warr_dict, s_net, warrs['s'])

        # draw decap transistor


        # connect horizontal wires
        pass
