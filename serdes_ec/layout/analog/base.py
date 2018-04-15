# -*- coding: utf-8 -*-

from typing import TYPE_CHECKING, Optional, Dict, Any, Set, Tuple, List, Union

import abc

from bag.layout.routing import TrackManager

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
        AnalogBaseInfo.__init__(self, grid, lch, guard_ring_nf, top_layer=top_layer,
                                end_mode=end_mode, min_fg_sep=min_fg_sep, fg_tot=fg_tot)

    def _get_diffamp_tran_info(self, seg_dict, fg_center, flip_out_sd):
        # type: (Dict[str, int], int, bool) -> Tuple[Dict[str, Tuple[Union[int, str]]], bool]
        tran_types = ['casc', 'in', 'sw', 'en', 'tail']
        dn_names = ['mid', 'tail', 'tail', 'foot', 'VSS']
        centers = [True, True, False, False, False]

        # we need separation if we use cascode transistor or if technology cannot abut transistors
        fg_cas = seg_dict.get('fg_cas', 0)
        need_sep = fg_cas > 0 or not self.abut_analog_mos

        # get load information
        tran_info = {}
        fg_prev = fg_diff = 0
        fg_load = seg_dict.get('load', 0)
        if fg_load > 0:
            up_name, dn_name = 'VDD', 'out'
            fg_diff = (fg_center - fg_load) // 2
            # get nmos transistor number of fingers that connects to load
            fg_casc = seg_dict.get('casc', 0)
            fg_gm = seg_dict['in'] if fg_casc == 0 else fg_casc

            # choose output source/drain to minimize number of output wires
            up_type = 's' if fg_load >= fg_gm or (fg_load - fg_gm) % 4 == 0 else 'd'
            # flip output source/drain if needed
            if flip_out_sd:
                up_type = _flip_sd(up_type)

            if up_type == 's':
                tran_info['load'] = (fg_diff, dn_name, up_name, 0, 2)
            else:
                tran_info['load'] = (fg_diff, up_name, dn_name, 2, 0)

            fg_prev = fg_load
            up_name = dn_name
            up_type = _flip_sd(up_type)
        else:
            up_name = 'out'
            up_type = 's' if flip_out_sd else 'd'

        # get nmos transistors information
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
                    # same as down wire type of input, and up wire is always vddn.
                    up_name = 'vddn'
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

    def get_diffamp_info(self, seg_dict, fg_min=0, fg_dum=0, flip_out_sd=False):
        # type: (Dict[str, int], int, int, bool) -> Dict[str, Any]
        """Return DiffAmp layout information dictionary.

        This method computes layout information of a differential amplifier.

        Parameters
        ----------
        seg_dict : Dict[str, int]
            a dictionary containing number of segments per transistor type.
        fg_min : int
            minimum number of total fingers.
        fg_dum : int
            minimum single-sided number of dummy fingers.
        flip_out_sd : bool
            True to draw output on source instead of drain.

        Returns
        -------
        info : Dict[str, Any]
            the Gm stage layout information dictionary.  Has the following entries:

            fg_tot : int
                total number of fingers.
            fg_single : int
                number of single-sided fingers.
            fg_center : int
                number of center-aligned fingers.
            fg_side : int
                number of side-aligned fingers.
            fg_sep : int
                number of separation fingers.
            fg_dum : int
                number of single-sided dummy fingers.
            fg_tail_tot : int
                total number of single-sided fingers in tail row.
            fg_load_tot : int
                total number of single-sided fingers in load row.
            tran_info : Dict[str, Any]
                transistor row layout information dictionary.
        """
        # error checking
        for cap_name in ('tail_cap', 'load_cap'):
            seg_cur = seg_dict.get(cap_name, 0)
            if seg_cur % 4 != 0:
                raise ValueError('seg_%s = %d must be multiples of 4.' % (cap_name, seg_cur))
        for even_name in ('load', 'casc', 'in', 'tail_ref', 'load_ref'):
            seg_cur = seg_dict.get(even_name, 0)
            if seg_cur % 2 != 0:
                raise ValueError('seg_%s = %d must be even.' % (even_name, seg_cur))

        # determine number of center fingers
        fg_load = seg_dict.get('load', 0)
        fg_casc = seg_dict.get('casc', 0)
        fg_in = seg_dict['in']
        fg_center = max(fg_load, fg_casc, fg_in)

        # get source and drain information
        tran_info, need_sep = self._get_diffamp_tran_info(seg_dict, fg_center, flip_out_sd)

        # find number of separation fingers
        fg_sep = 0
        # fg_sep from load reference constraint
        fg_load_ref = seg_dict.get('load_ref', 0)
        if fg_load_ref > 0:
            load_info = tran_info['load']
            fg_diff_load, load_s_name = load_info[0], load_info[2]
            if self.abut_analog_mos and load_s_name == 'VDD':
                # we can abut reference to load
                fg_load_sep = fg_load_ref
            else:
                # we need separator between load and reference.
                fg_load_sep = fg_load_ref + 2 * self.min_fg_sep
            fg_sep = max(fg_sep, fg_load_sep - 2 * fg_diff_load)
        # fg_sep from tail reference constraint
        fg_tail_ref = seg_dict.get('tail_ref', 0)
        tail_info = tran_info['tail']
        fg_diff_tail = tail_info[0]
        if fg_tail_ref > 0:
            # NOTE: we always need separation between tail reference and tail transistors,
            # otherwise middle dummies in other nmos rows cannot be connected.
            fg_sep = max(fg_sep, fg_tail_ref + 2 * (self.min_fg_sep - fg_diff_tail))
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
        fg_tail_cap = seg_dict.get('tail_cap', 0)
        if fg_tail_cap > 0:
            fg_tail_tot = fg_diff_tail + fg_tail + fg_tail_cap
            tail_s_name = tail_info[2]
            if not (tail_s_name == 'VSS' and self.abut_analog_mos):
                # we need to separate tail decap and tail transistor
                fg_tail_tot += self.min_fg_sep
        else:
            fg_tail_tot = fg_diff_tail + fg_tail
        fg_side = max(fg_side, fg_tail_tot)
        # get side fingers for load row.  Take load decap into account
        if fg_load > 0:
            load_info = tran_info['load']
            fg_diff_load, load_s_name = load_info[0], load_info[2]
            fg_load_cap = seg_dict.get('load_cap', 0)
            if fg_load_cap > 0:
                fg_load_tot = fg_diff_load + fg_load + fg_load_cap
                if not (load_s_name == 'VDD' and self.abut_analog_mos):
                    # we need to separate load decap and load transistor
                    fg_load_tot += self.min_fg_sep
            else:
                fg_load_tot = fg_diff_load + fg_load
        else:
            fg_load_tot = 0
        fg_side = max(fg_side, fg_load_tot)

        # get total number of fingers and number of dummies on each edge.
        fg_single = max(fg_center, fg_side)
        fg_tot = fg_single * 2 + fg_sep + 2 * fg_dum
        if fg_tot < fg_min:
            # add dummies to get to fg_min
            if (fg_min - fg_tot) % 2 != 0:
                fg_min += 1

            fg_dum = (fg_min - fg_tot) // 2
            fg_tot = fg_min

        # determine output source/drain type.
        results = dict(
            fg_tot=fg_tot,
            fg_single=fg_single,
            fg_center=fg_center,
            fg_side=fg_side,
            fg_sep=fg_sep,
            fg_dum=fg_dum,
            fg_tail_tot=fg_tail_tot,
            fg_load_tot=fg_load_tot,
            tran_info=tran_info,
        )

        return results


class SerdesRXBase(AnalogBase, metaclass=abc.ABCMeta):
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
        AnalogBase.__init__(self, temp_db, lib_name, params, used_names, **kwargs)
        self._nrow_idx = None
        self._prow_idx = None
        self._serdes_info = None  # type: SerdesRXBaseInfo

    @property
    def layout_info(self):
        # type: () -> SerdesRXBaseInfo
        return self._serdes_info

    def get_row_index(self, name):
        # type: (str) -> Tuple[str, int]
        """Returns the row index of the given transistor name.

        Parameters
        ----------
        name : str
            the transistor name.

        Returns
        -------
        mos_type : str
            the transistor type.
        row_idx : int
            the row index.
        """
        if name in self._nrow_idx:
            return 'nch', self._nrow_idx[name]
        if name in self._prow_idx:
            return 'pch', self._prow_idx[name]

        raise ValueError('row %s not found.' % name)

    @staticmethod
    def _get_diff_names(name_base, is_diff, invert=False):
        # type: (str, bool, bool) -> Tuple[str, str]
        if is_diff:
            if invert:
                return name_base + 'n', name_base + 'p'
            else:
                return name_base + 'p', name_base + 'n'
        return name_base, name_base

    @staticmethod
    def _append_to_warr_dict(warr_dict, name, warr):
        # type: (Dict[str, List[WireArray]], str, WireArray) -> None
        if name not in warr_dict:
            warr_dict[name] = []
        warr_dict[name].append(warr)

    def _draw_diffamp_mos(self, col_idx, seg_dict, tran_info, fg_single, fg_dum, fg_sep, net_prefix):
        # type: (int, Dict[str, int], Dict[str, Any], int, int, int, str) -> Dict[str, List[WireArray]]
        tran_types = ['load', 'casc', 'in', 'sw', 'en', 'tail']
        gnames = ['bias_load', 'bias_casc', 'in', 'clk_sw', 'enable', 'bias_tail']
        g_diffs = [False, False, True, False, False, False]
        up_diffs = [False, True, True, False, False, False]
        dn_diffs = [True, True, False, False, False, False]

        col_l = col_idx + fg_dum + fg_single
        col_r = col_l + fg_sep

        warr_dict = {}
        for tran_type, gname, g_diff, up_diff, dn_diff in zip(tran_types, gnames, g_diffs, up_diffs, dn_diffs):
            if tran_type in tran_info:
                fg = seg_dict[tran_type]
                fg_diff, dname, sname, ddir, sdir = tran_info[tran_type]
                if ddir > 0:
                    d_diff, s_diff = up_diff, dn_diff
                else:
                    d_diff, s_diff = dn_diff, up_diff
                gname_p, gname_n = self._get_diff_names(gname, g_diff)
                dname_p, dname_n = self._get_diff_names(dname, d_diff, invert=True)
                sname_p, sname_n = self._get_diff_names(sname, s_diff, invert=True)

                mos_type, row_idx = self.get_row_index(tran_type)
                p_warrs = self.draw_mos_conn(mos_type, row_idx, col_l - fg_diff - fg, fg, sdir, ddir,
                                             s_net=net_prefix + sname_p, d_net=net_prefix + dname_p)
                n_warrs = self.draw_mos_conn(mos_type, row_idx, col_r + fg_diff, fg, sdir, ddir,
                                             s_net=net_prefix + sname_n, d_net=net_prefix + dname_n)

                self._append_to_warr_dict(warr_dict, gname_p, p_warrs['g'])
                self._append_to_warr_dict(warr_dict, dname_p, p_warrs['d'])
                self._append_to_warr_dict(warr_dict, sname_p, p_warrs['s'])
                self._append_to_warr_dict(warr_dict, gname_n, n_warrs['g'])
                self._append_to_warr_dict(warr_dict, dname_n, n_warrs['d'])
                self._append_to_warr_dict(warr_dict, sname_n, n_warrs['s'])

        return warr_dict

    def draw_diffamp(self,  # type: SerdesRXBase
                     col_idx,  # type: int
                     seg_dict,  # type: Dict[str, int]
                     tr_widths=None,  # type: Optional[Dict[str, Dict[int, int]]]
                     tr_spaces=None,  # type: Optional[Dict[Union[str, Tuple[str, str]], Dict[int, int]]]
                     tr_indices=None,  # type: Optional[Dict[str, int]]
                     fg_min=0,  # type: int
                     fg_dum=0,  # type: int
                     flip_out_sd=False,  # type: bool
                     net_prefix='',  # type: str
                     ):
        # type: (...) -> Tuple[Dict[str, WireArray], Dict[str, Any]]
        """Draw a differential amplifier.

        Parameters
        ----------
        col_idx : int
            the left-most transistor index.  0 is the left-most transistor.
        seg_dict : Dict[str, int]
            a dictionary containing number of segments per transistor type.
        tr_widths : Optional[Dict[str, Dict[int, int]]]
            the track width dictionary.
        tr_spaces : Optional[Dict[Union[str, Tuple[str, str]], Dict[int, int]]]
            the track spacing dictionary.
        tr_indices : Optional[Dict[str, int]]
            the track index dictionary.  Maps from net name to relative track index.
        fg_min : int
            minimum number of total fingers.
        fg_dum : int
            minimum single-sided number of dummy fingers.
        flip_out_sd : bool
            True to draw output on source instead of drain.
        net_prefix : str
            this prefit will be added to net names in draw_mos_conn() method and the
            returned port dictionary.

        Returns
        -------
        port_dict : Dict[str, WireArray]
            a dictionary from connection name to WireArrays on horizontal routing layer.
        amp_info : Dict[str, Any]
            the amplifier layout information dictionary
        """
        if tr_widths is None:
            tr_widths = {}
        if tr_spaces is None:
            tr_spaces = {}
        if tr_indices is None:
            tr_indices = {}

        # get layout information
        amp_info = self._serdes_info.get_diffamp_info(seg_dict, fg_min=fg_min, fg_dum=fg_dum, flip_out_sd=flip_out_sd)
        fg_tot = amp_info['fg_tot']
        fg_single = amp_info['fg_single']
        fg_sep = amp_info['fg_sep']
        fg_dum = amp_info['fg_dum']
        tran_info = amp_info['tran_info']

        # draw main transistors and collect ports
        warr_dict = self._draw_diffamp_mos(col_idx, seg_dict, tran_info, fg_single, fg_dum, fg_sep, net_prefix)

        # draw load/tail reference transistor
        for tran_name, mos_type, sup_name in (('tail', 'nch', 'VSS'), ('load', 'pch', 'VDD')):
            fg_name = '%s_ref' % tran_name
            fg_ref = seg_dict.get(fg_name, 0)
            if fg_ref > 0:
                mos_type, row_idx = self.get_row_index(tran_name)
                # error checking
                if (fg_tot - fg_ref) % 2 != 0:
                    raise ValueError('fg_tot = %d and fg_%s = %d has opposite parity.' % (fg_tot, fg_name, fg_ref))
                # get reference column index
                col_ref = col_idx + (fg_tot - fg_ref) // 2

                # get drain/source name/direction
                cur_info = tran_info[tran_name]
                dname, sname, ddir, sdir = cur_info[1:]
                gname = 'bias_%s' % tran_name
                if dname == sup_name:
                    sname = gname
                else:
                    dname = gname

                # draw transistor
                warrs = self.draw_mos_conn(mos_type, row_idx, col_ref, fg_ref, sdir, ddir,
                                           s_net=net_prefix + sname, d_net=net_prefix + dname)
                self._append_to_warr_dict(warr_dict, gname, warrs['g'])
                self._append_to_warr_dict(warr_dict, dname, warrs['d'])
                self._append_to_warr_dict(warr_dict, sname, warrs['s'])

        # draw load/tail decap transistor
        for tran_name, mos_type, sup_name in (('tail', 'nch', 'VSS'), ('load', 'pch', 'VDD')):
            fg_name = '%s_cap' % tran_name
            fg_cap = seg_dict.get(fg_name, 0)
            if fg_cap > 0:
                mos_type, row_idx = self.get_row_index(tran_name)
                # compute decap column index
                fg_row_tot = amp_info['fg_%s_tot' % tran_name]
                col_l = col_idx + fg_dum + fg_single - fg_row_tot
                col_r = col_idx + fg_dum + fg_single + fg_sep + fg_row_tot - fg_cap

                fg_cap_single = fg_cap // 2
                p_warrs = self.draw_mos_decap(mos_type, row_idx, col_l, fg_cap_single, False, export_gate=True)
                n_warrs = self.draw_mos_decap(mos_type, row_idx, col_r, fg_cap_single, False, export_gate=True)
                gname = 'bias_%s' % tran_name
                self._append_to_warr_dict(warr_dict, gname, p_warrs['g'])
                self._append_to_warr_dict(warr_dict, gname, n_warrs['g'])

        # connect to horizontal wires
        # nets relative index parameters
        tr_manager = TrackManager(self.grid, tr_widths, tr_spaces)
        nets = ['outp', 'outn', 'bias_load', 'midp', 'midn', 'bias_casc', 'tail', 'inp', 'inn', 'vddn', 'clk_sw',
                'foot', 'enable', 'bias_tail']
        rows = ['load', 'load', 'load',      'casc', 'casc', 'casc',      'tail', 'in',  'in',  'sw',   'sw',
                'tail', 'en',     'tail']
        trns = ['ds', 'ds',     'g',         'ds',   'ds',   'g',         'ds',   'g',   'g',   'ds',   'g',
                'ds',   'g',      'g']

        tr_type_dict = dict(
            outp='out',
            outn='out',
            bias_load='bias',
            midp='mid',
            midn='mid',
            bias_casc='bias',
            tail='tail',
            inp='in',
            inn='in',
            vddn='vdd',
            clk_sw='bias',
            foot='tail',
            enable='bias',
            bias_tail='bias',
        )

        # tail net should be connected on enable row if it exists
        if 'enable' in warr_dict:
            rows[6] = 'en'

        # compute default inp/inn/outp/outn indices.
        hm_layer = self.mos_conn_layer + 1
        for tran_name, net_type, net_base, order in (('in', 'g', 'in', -1), ('load', 'ds', 'out', 1)):
            pname, nname = '%sp' % net_base, '%sn' % net_base
            if pname not in tr_indices or nname not in tr_indices:
                tr_indices = tr_indices.copy()
                ntr_used, (netp_idx, netn_idx) = tr_manager.place_wires(hm_layer, [net_base, net_base])
                if order < 0:
                    netp_idx, netn_idx = netn_idx, netp_idx
                mos_type, row_idx = self.get_row_index(tran_name)
                ntr_tot = self.get_num_tracks(mos_type, row_idx, net_type)
                if ntr_tot < ntr_used:
                    raise ValueError('Need at least %d tracks to draw %s and %s' % (ntr_used, pname, nname))
                tr_indices[pname] = netp_idx + (ntr_tot - ntr_used)
                tr_indices[nname] = netn_idx + (ntr_tot - ntr_used)

        # connect horizontal wires
        result = {}
        inp_tidx, inn_tidx, outp_tidx, outn_tidx = 0, 0, 0, 0
        for net_name, row_type, tr_type in zip(nets, rows, trns):
            if net_name in warr_dict:
                mos_type, row_idx = self.get_row_index(row_type)
                tr_w = tr_manager.get_width(hm_layer, tr_type_dict[net_name])
                if net_name in tr_indices:
                    # use specified relative index
                    tr_idx = tr_indices[net_name]
                else:
                    # compute default relative index.  Try to use the tracks closest to transistor.
                    ntr_used, (tr_idx, ) = tr_manager.place_wires(hm_layer, [tr_type_dict[net_name]])
                    ntr_tot = self.get_num_tracks(mos_type, row_idx, tr_type)
                    if ntr_tot < ntr_used:
                        raise ValueError('Need at least %d %s tracks to draw %s track' % (ntr_used, tr_type, net_name))
                    if tr_type == 'g':
                        tr_idx += (ntr_tot - ntr_used)

                # get track locations and connect
                if net_name == 'inp':
                    inp_tidx = self.get_track_index(mos_type, row_idx, tr_type, tr_idx)
                elif net_name == 'inn':
                    inn_tidx = self.get_track_index(mos_type, row_idx, tr_type, tr_idx)
                elif net_name == 'outp':
                    outp_tidx = self.get_track_index(mos_type, row_idx, tr_type, tr_idx)
                elif net_name == 'outn':
                    outn_tidx = self.get_track_index(mos_type, row_idx, tr_type, tr_idx)
                else:
                    tid = self.make_track_id(mos_type, row_idx, tr_type, tr_idx, width=tr_w)
                    result[net_prefix + net_name] = self.connect_to_tracks(warr_dict[net_name], tid)

        # connect differential input/output
        inp_warr, inn_warr = self.connect_differential_tracks(warr_dict['inp'], warr_dict['inn'], hm_layer,
                                                              inp_tidx, inn_tidx,
                                                              width=tr_manager.get_width(hm_layer, 'in'))
        outp_warr, outn_warr = self.connect_differential_tracks(warr_dict['outp'], warr_dict['outn'], hm_layer,
                                                                outp_tidx, outn_tidx,
                                                                width=tr_manager.get_width(hm_layer, 'out'))
        result[net_prefix + 'inp'] = inp_warr
        result[net_prefix + 'inn'] = inn_warr
        result[net_prefix + 'outp'] = outp_warr
        result[net_prefix + 'outn'] = outn_warr

        # connect VDD and VSS
        self.connect_to_substrate('ptap', warr_dict['VSS'])
        if 'VDD' in warr_dict:
            self.connect_to_substrate('ntap', warr_dict['VDD'])
        # return result
        return result, amp_info

    @staticmethod
    def _draw_rows_helper(name_list, w_dict, th_dict, g_ntr_dict, ds_ntr_dict):
        row_idx_lookup = {}
        w_list, th_list, g_tracks, ds_tracks = [], [], [], []
        cur_idx = 0
        for name in name_list:
            width = w_dict.get(name, 0)
            if width > 0:
                thres = th_dict[name]
                row_idx_lookup[name] = cur_idx
                w_list.append(width)
                th_list.append(thres)
                g_tracks.append(g_ntr_dict.get(name, 1))
                ds_tracks.append(ds_ntr_dict.get(name, 1))
                cur_idx += 1

        return row_idx_lookup, w_list, th_list, g_tracks, ds_tracks

    def draw_rows(self,
                  lch,  # type: float
                  fg_tot,  # type: int
                  ptap_w,  # type: Union[float, int]
                  ntap_w,  # type: Union[float, int]
                  w_dict,  # type: Dict[str, Union[float, int]]
                  th_dict,  # type: Dict[str, str]
                  g_ntr_dict,  # type: Dict[str, int]
                  ds_ntr_dict,  # type: Dict[str, int]
                  **kwargs  # type: **kwargs
                  ):
        # type: (...) -> None
        """Draw the transistors and substrate rows.

        Parameters
        ----------
        lch : float
            the transistor channel length, in meters
        fg_tot : int
            total number of fingers for each row.
        ptap_w : Union[float, int]
            pwell substrate contact width.
        ntap_w : Union[float, int]
            nwell substrate contact width.
        w_dict : Dict[str, Union[float, int]]
            dictionary from transistor type to row width.  Currently supported type names are
            load, casc, in, sw, en, and tail.
        th_dict : Dict[str, str]
            dictionary from transistor type to threshold flavor.
        g_ntr_dict : Dict[str, int]
            dictionary from transistor type to number of gate tracks.
        ds_ntr_dict : Dict[str, int]
            dictionary from transistor type to number of drain/source tracks.
        **kwargs
            any addtional parameters for AnalogBase's draw_base() method.
        """
        # make SerdesRXBaseInfo
        guard_ring_nf = kwargs.get('guard_ring_nf', 0)
        top_layer = kwargs.get('top_layer', None)
        end_mode = kwargs.get('end_mode', 15)
        min_fg_sep = kwargs.get('min_fg_sep', 0)
        self._serdes_info = SerdesRXBaseInfo(self.grid, lch, guard_ring_nf, top_layer=top_layer, end_mode=end_mode,
                                             min_fg_sep=min_fg_sep, fg_tot=fg_tot)

        # figure out row indices for each nmos row type,
        # and build nw_list/nth_list/ng_tracks/nds_tracks
        tmp_result = self._draw_rows_helper(['tail', 'en', 'sw', 'in', 'casc'], w_dict, th_dict,
                                            g_ntr_dict, ds_ntr_dict)
        self._nrow_idx, nw_list, nth_list, ng_tracks, nds_tracks = tmp_result
        tmp_result = self._draw_rows_helper(['load'], w_dict, th_dict, g_ntr_dict, ds_ntr_dict)
        self._prow_idx, pw_list, pth_list, pg_tracks, pds_tracks = tmp_result

        n_orient = ['R0'] * len(nw_list)
        p_orient = ['MX'] * len(pw_list)

        # draw base
        self.draw_base(lch, fg_tot, ptap_w, ntap_w, nw_list, nth_list, pw_list, pth_list,
                       ng_tracks=ng_tracks, nds_tracks=nds_tracks, pg_tracks=pg_tracks, pds_tracks=pds_tracks,
                       n_orientations=n_orient, p_orientations=p_orient, **kwargs)
