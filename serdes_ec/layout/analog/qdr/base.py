# -*- coding: utf-8 -*-

"""This module defines HybridQDRBaseInfo and HybridQDRBase, which draws hybrid QDR serdes blocks."""

from typing import TYPE_CHECKING, Optional, Dict, Any, Set, Tuple, List, Union

import abc

from bag.layout.routing import TrackManager

from abs_templates_ec.analog_core.base import AnalogBase, AnalogBaseInfo

if TYPE_CHECKING:
    from bag.layout.routing import RoutingGrid, WireArray
    from bag.layout.template import TemplateDB


def _flip_sd(name):
    # type: (str) -> str
    return 'd' if name == 's' else 's'


class HybridQDRBaseInfo(AnalogBaseInfo):
    """A class that calculates information to assist in HybridQDRBase layout.

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

    def __init__(self, grid, lch, guard_ring_nf, top_layer=None, end_mode=15, min_fg_sep=0, fg_tot=None, **kwargs):
        # type: (RoutingGrid, float, int, Optional[int], int, int, Optional[int], **kwargs) -> None
        AnalogBaseInfo.__init__(self, grid, lch, guard_ring_nf, top_layer=top_layer,
                                end_mode=end_mode, min_fg_sep=min_fg_sep, fg_tot=fg_tot, **kwargs)

    def get_integ_amp_info(self, seg_dict):
        # type: (Dict[str, int]) -> Dict[str, Any]
        """Compute placement of transistors in the given integrating amplifier.

        Parameters
        ----------
        seg_dict : Dict[str, int]
            a dictionary containing number of segments per transistor type.

        Returns
        -------
        info_dict : Dict[str, Any]
            the amplifier information dictionary.  Has the following entries:

            seg_tot : int
                total number of segments needed to draw the integrating amplifier.
            col_dict : Dict[str, int]
                a dictionary of left side column indices of each transistor.
            sd_dict : Dict[Tuple[str, str], str]
                a dictionary from net name/transistor tuple to source-drain junction type.
        """
        need_sep = not self.abut_analog_mos
        fg_sep = self.min_fg_sep

        seg_load = seg_dict.get('load', 0)
        seg_enp = seg_dict.get('enp', 0)
        seg_casc = seg_dict.get('casc', 0)
        seg_in = seg_dict['in']
        seg_enn = seg_dict['enn']
        seg_tail = seg_dict['tail']

        # calculate PMOS center transistor number of fingers
        seg_ps = max(seg_enp, seg_load)
        if seg_load == 0:
            seg_pc = 0
        else:
            if need_sep or seg_load > seg_enp:
                seg_pc = seg_ps * 2 + fg_sep
            else:
                seg_pc = seg_ps * 2

        # calculate NMOS center transistor number of fingers
        seg_nc = max(seg_casc, seg_in)
        # calculate number of center fingers and total size
        seg_center = max(seg_nc, seg_pc)
        seg_single = max(seg_center, seg_enn, seg_tail)
        seg_tot = 2 * seg_single + fg_sep

        # compute column index of each transistor
        col_dict = {}
        center_off = (seg_single - seg_center) // 2
        if seg_load > 0:
            pc_off = center_off + (seg_center - seg_pc) // 2
            load_off = (seg_ps - seg_load) // 2
            enp_off = (seg_ps - seg_enp) // 2
            col_dict['load0'] = pc_off + load_off
            col_dict['load1'] = pc_off + seg_pc - load_off - seg_load
            col_dict['enp0'] = pc_off + enp_off
            col_dict['enp1'] = pc_off + seg_pc - enp_off - seg_enp

        nc_off = center_off + (seg_center - seg_nc) // 2
        if seg_casc > 0:
            col_dict['casc'] = nc_off + (seg_nc - seg_casc) // 2
        col_dict['in'] = nc_off + (seg_nc - seg_in) // 2
        col_dict['enn'] = min(seg_single - seg_enn, col_dict['in'])
        col_dict['tail'] = min(seg_single - seg_tail, col_dict['enn'])

        # compute source-drain junction type for each net
        sd_dict = {('VDD', 'load0'): 's', ('VDD', 'load1'): 's',
                   ('mp0', 'load0'): 'd', ('mp1', 'load1'): 'd'}
        sd_name = 'd' if (col_dict['enp0'] - col_dict['load0']) % 2 == 0 else 's'
        sd_dict[('mp0', 'enp0')] = sd_dict[('mp1', 'enp1')] = sd_name
        sd_name = 'd' if sd_name == 's' else 's'
        sd_dict[('out', 'enp0')] = sd_dict[('out', 'enp1')] = sd_name
        if seg_casc > 0:
            if (col_dict['casc'] - col_dict['enp0']) % 2 == 1:
                sd_name = 'd' if sd_name == 's' else 's'
            sd_dict[('out', 'casc')] = sd_name
            sd_name = 'd' if sd_name == 's' else 's'
            sd_dict[('cn', 'casc')] = sd_name
            if (col_dict['in'] - col_dict['casc']) % 2 == 1:
                sd_name = 'd' if sd_name == 's' else 's'
            sd_dict[('cn', 'in')] = sd_name
            sd_name = 'd' if sd_name == 's' else 's'
            sd_dict[('tail', 'in')] = sd_name
        else:
            if (col_dict['in'] - col_dict['enp0']) % 2 == 1:
                sd_name = 'd' if sd_name == 's' else 's'
            sd_dict[('out', 'in')] = sd_name
            sd_name = 'd' if sd_name == 's' else 's'
            sd_dict[('tail', 'in')] = sd_name
        if (col_dict['enn'] - col_dict['in']) % 2 == 1:
            sd_name = 'd' if sd_name == 's' else 's'
        sd_dict[('tail', 'enn')] = sd_name
        sd_name = 'd' if sd_name == 's' else 's'
        sd_dict[('foot', 'enn')] = sd_name
        if (col_dict['tail'] - col_dict['enn']) % 2 == 1:
            sd_name = 'd' if sd_name == 's' else 's'
        sd_dict[('foot', 'tail')] = sd_name
        sd_name = 'd' if sd_name == 's' else 's'
        sd_dict[('VSS', 'tail')] = sd_name

        return dict(
            seg_tot=seg_tot,
            col_dict=col_dict,
            sd_dict=sd_dict,
        )


class HybridQDRBase(AnalogBase, metaclass=abc.ABCMeta):
    """Subclass of AnalogBase that draws QDR serdes blocks.

    Parameters
    ----------
    temp_db : TemplateDB
        the template database.
    lib_name : str
        the layout library name.
    params : Dict[str, Any]
        the parameter values.
    used_names : Set[str]
        a set of already used cell names.
    **kwargs
        optional parameters.
    """

    n_name_list = ['tail', 'enn', 'in', 'casc']
    p_name_list = ['enp', 'load']

    def __init__(self, temp_db, lib_name, params, used_names, **kwargs):
        # type: (TemplateDB, str, Dict[str, Any], Set[str], **kwargs) -> None
        AnalogBase.__init__(self, temp_db, lib_name, params, used_names, **kwargs)
        self._row_lookup = {key: ('nch', idx) for idx, key in enumerate(self.n_name_list)}
        for idx, key in enumerate(self.p_name_list):
            self._row_lookup[key] = ('pch', idx)

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
        if name not in self._row_lookup:
            raise ValueError('row %s not found.' % name)
        return self._row_lookup[name]

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

    def draw_rows(self,
                  lch,  # type: float
                  fg_tot,  # type: int
                  ptap_w,  # type: Union[float, int]
                  ntap_w,  # type: Union[float, int]
                  w_dict,  # type: Dict[str, Union[float, int]]
                  th_dict,  # type: Dict[str, str]
                  tr_widths,  # type: Dict[str, Dict[int, int]]
                  tr_spaces,  # type: Dict[Union[str, Tuple[str, str]], Dict[int, int]]
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
            dictionary from transistor type to row width.
        th_dict : Dict[str, str]
            dictionary from transistor type to threshold flavor.
        tr_widths : Dict[str, Dict[int, int]]
            the track width dictionary.
        tr_spaces : Dict[Union[str, Tuple[str, str]], Dict[int, int]]
            the track space dictionary.
        **kwargs
            any addtional parameters for AnalogBase's draw_base() method.
        """
        # make layout information object
        guard_ring_nf = kwargs.pop('guard_ring_nf', 0)
        self.set_layout_info(HybridQDRBaseInfo(self.grid, lch, guard_ring_nf, fg_tot=fg_tot, **kwargs))

        nw_list, nth_list = [], []
        for name in self.n_name_list:
            nw_list.append(w_dict[name])
            nth_list.append(th_dict[name])
        pw_list, pth_list = [], []
        for name in self.p_name_list:
            pw_list.append(w_dict[name])
            pth_list.append(th_dict[name])

        # calculate number of horizontal tracks needed.
        tr_manager = TrackManager(self._serdes_info.grid, tr_widths, tr_spaces)

        n_orient = ['R0'] * len(nw_list)
        p_orient = ['MX'] * len(pw_list)

        # draw base
        self.draw_base(lch, fg_tot, ptap_w, ntap_w, nw_list, nth_list, pw_list, pth_list,
                       ng_tracks=ng_tracks, nds_tracks=nds_tracks, pg_tracks=pg_tracks, pds_tracks=pds_tracks,
                       n_orientations=n_orient, p_orientations=p_orient, guard_ring_nf=guard_ring_nf, **kwargs)
