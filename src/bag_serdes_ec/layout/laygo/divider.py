# -*- coding: utf-8 -*-

"""This module contains LaygoBase templates used in Hybrid-QDR receiver."""

from typing import TYPE_CHECKING, Dict, Any, Set, Union

from itertools import chain

from bag.layout.routing import TrackManager, TrackID, WireArray
from bag.layout.template import TemplateBase

from abs_templates_ec.laygo.core import LaygoBase

if TYPE_CHECKING:
    from bag.layout.template import TemplateDB


def _draw_substrate(template, col_start, col_stop, num_col):
    top_ridx = template.num_rows - 1

    if col_start > 0:
        template.add_laygo_mos(0, 0, col_start)
        template.add_laygo_mos(top_ridx, 0, col_start)
    sub_stop = col_start + num_col
    nadd = col_stop - sub_stop
    if nadd > 0:
        template.add_laygo_mos(0, sub_stop, nadd)
        template.add_laygo_mos(top_ridx, sub_stop, nadd)

    nsub = template.add_laygo_mos(0, col_start, num_col)
    psub = template.add_laygo_mos(top_ridx, col_start, num_col)
    return nsub['VSS_s'], psub['VDD_s']


def _connect_supply(template, sup_warr, sup_list, sup_intv, tr_manager, round_up=False,
                    inc_set=None, exc_set=None):
    grid = template.grid

    if inc_set is None:
        inc_set = set()
    if exc_set is None:
        exc_set = set()

    # gather list of track indices and wires
    idx_set = set()
    warr_list = []
    min_tid = max_tid = None
    for sup in sup_list:
        if isinstance(sup, WireArray):
            sup = [sup]
        for warr in sup:
            warr_list.append(warr)
            for tid in warr.track_id:
                idx_set.add(tid)
                if min_tid is None:
                    min_tid = max_tid = tid
                else:
                    min_tid = min(tid, min_tid)
                    max_tid = max(tid, max_tid)

    for warr in WireArray.single_warr_iter(sup_warr):
        tid = warr.track_id.base_index
        if min_tid is None:
            min_tid = max_tid = tid
        else:
            min_tid = min(tid, min_tid)
            max_tid = max(tid, max_tid)
        if tid - 1 not in idx_set and tid + 1 not in idx_set:
            warr_list.append(warr)
            idx_set.add(tid)

    vm_layer = template.conn_layer
    hm_layer = vm_layer + 1
    ym_layer = hm_layer + 1
    sup_w = tr_manager.get_width(hm_layer, 'sup')
    sup_idx = grid.get_middle_track(sup_intv[0], sup_intv[1] - 1, round_up=round_up)

    xl = grid.track_to_coord(vm_layer, min_tid, unit_mode=True)
    xr = grid.track_to_coord(vm_layer, max_tid, unit_mode=True)
    tl = grid.coord_to_nearest_track(ym_layer, xl, half_track=True, mode=1, unit_mode=True)
    tr = grid.coord_to_nearest_track(ym_layer, xr, half_track=True, mode=-1, unit_mode=True)

    sup = template.connect_to_tracks(warr_list, TrackID(hm_layer, sup_idx, width=sup_w))
    tl_htr = int(round(tl * 2))
    tr_htr = int(round(tr * 2))
    for htr in range(tl_htr, tr_htr + 1, 2):
        htrl = htr - 2
        htrr = htr + 2
        if (htr not in exc_set and htrl not in inc_set and htrr not in inc_set
                and htrl not in exc_set and htrr not in exc_set):
            inc_set.add(htr)
    warr_list = [template.connect_to_tracks(sup, TrackID(ym_layer, htr / 2))
                 for htr in inc_set]
    return warr_list


class SinClkDivider2(LaygoBase):
    """A Sinusoidal clock divider using LaygoBase.

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
    **kwargs :
        dictionary of optional parameters.  See documentation of
        :class:`bag.layout.template.TemplateBase` for details.
    """

    def __init__(self, temp_db, lib_name, params, used_names, **kwargs):
        # type: (TemplateDB, str, Dict[str, Any], Set[str], **kwargs) -> None
        LaygoBase.__init__(self, temp_db, lib_name, params, used_names, **kwargs)
        self._sch_params = None
        self._fg_tot = None
        self._sa_clk_tidx = None

    @property
    def sch_params(self):
        # type: () -> Dict[str, Any]
        return self._sch_params

    @property
    def fg_tot(self):
        # type: () -> int
        return self._fg_tot

    @property
    def sa_clk_tidx(self):
        return self._sa_clk_tidx

    @classmethod
    def get_col_info(cls, seg_dict, abut_mode):
        # compute number of columns, then draw floorplan
        blk_sp = seg_dict['blk_sp']
        seg_inv = cls._get_gate_inv_info(seg_dict)
        seg_int = cls._get_integ_amp_info(seg_dict)
        seg_sr = cls._get_sr_latch_info(seg_dict)

        if abut_mode & 1 != 0:
            # abut on left
            inc_coll = blk_sp
        else:
            inc_coll = 0
        if abut_mode & 2 != 0:
            # abut on right
            inc_colr = blk_sp
        else:
            inc_colr = 0

        seg_tot = seg_inv + seg_int + seg_sr + 2 * blk_sp + inc_coll + inc_colr
        return seg_tot, blk_sp, seg_inv, seg_int, seg_sr, inc_coll, inc_colr

    @classmethod
    def get_params_info(cls):
        # type: () -> Dict[str, str]
        return dict(
            config='laygo configuration dictionary.',
            row_layout_info='The AnalogBase layout information dictionary.',
            seg_dict='Number of segments dictionary.',
            tr_widths='Track width dictionary.',
            tr_spaces='Track spacing dictionary.',
            en3_htr_idx='Enable3 half-track index.',
            tr_info='output track information dictionary.',
            fg_min='Minimum number of core fingers.',
            end_mode='The LaygoBase end_mode flag.',
            abut_mode='The left/right abut mode flag.',
            div_pos_edge='True to divider off of clkp.',
            show_pins='True to show pins.',
        )

    @classmethod
    def get_default_param_values(cls):
        # type: () -> Dict[str, Any]
        return dict(
            tr_info=None,
            fg_min=0,
            end_mode=None,
            abut_mode=0,
            div_pos_edge=True,
            show_pins=True,
        )

    def draw_layout(self):
        row_layout_info = self.params['row_layout_info']
        seg_dict = self.params['seg_dict'].copy()
        tr_widths = self.params['tr_widths']
        tr_spaces = self.params['tr_spaces']
        en3_htr_idx = self.params['en3_htr_idx']
        tr_info = self.params['tr_info']
        fg_min = self.params['fg_min']
        end_mode = self.params['end_mode']
        abut_mode = self.params['abut_mode']
        div_pos_edge = self.params['div_pos_edge']
        show_pins = self.params['show_pins']

        # compute number of columns
        tmp = self.get_col_info(seg_dict, abut_mode)
        seg_tot, blk_sp, seg_inv, seg_int, seg_sr, col_inv, inc_colr = tmp
        if fg_min > seg_tot:
            deltal = (fg_min - seg_tot) // 4 * 2
            col_inv += deltal
            inc_colr += (fg_min - seg_tot - col_inv)
            seg_tot = fg_min

        self._fg_tot = seg_tot
        self.set_rows_direct(row_layout_info, end_mode=end_mode, num_col=seg_tot)

        # draw individual blocks
        tr_manager = TrackManager(self.grid, tr_widths, tr_spaces, half_space=True)
        vss_w, vdd_w = _draw_substrate(self, col_inv, seg_tot, seg_tot - inc_colr - col_inv)
        col_int = col_inv + seg_inv + blk_sp
        col_sr = col_int + seg_int + blk_sp
        inv_ports, inv_seg = self._draw_gate_inv(col_inv, seg_inv, seg_dict, tr_manager)
        int_ports, int_seg = self._draw_integ_amp(col_int, seg_int, seg_dict, tr_manager)
        sr_ports, xm_locs, sr_params = self._draw_sr_latch(col_sr, seg_sr, seg_dict, tr_manager,
                                                           en3_htr_idx)

        # connect enable
        en = self.connect_to_track_wires([inv_ports['en'], sr_ports['pen']], int_ports['en'])
        en_vm = sr_ports['nen']
        self.add_pin('en_vm', en_vm, label='en', show=False)
        en.append(en_vm)
        # connect inverters to integ amp
        clk = self.connect_to_track_wires(inv_ports['clk'], int_ports['clk'])
        mp = inv_ports['mp']
        mn = inv_ports['mn']
        tr_upper = mp.upper
        tr_w = mp.track_id.width
        mp_tid = mp.track_id.base_index
        mn_tid = mn.track_id.base_index
        self.connect_differential_tracks(int_ports['mp'], int_ports['mn'],
                                         mp.layer_id, mp_tid, mn_tid,
                                         width=tr_w, track_upper=tr_upper)

        # connect integ amp to sr latch
        self.connect_wires([int_ports['sb'], sr_ports['sb']])
        self.connect_wires([int_ports['rb'], sr_ports['rb']])

        # connect sr latch to inverters
        xm_layer = self.conn_layer + 3
        xm_w_q = tr_manager.get_width(xm_layer, 'div')

        # connect supply wires
        vss_list = [inv_ports['VSS'], int_ports['VSS'], sr_ports['VSS']]
        vdd_list = [inv_ports['VDD'], int_ports['VDD'], sr_ports['VDD']]
        vss_intv = self.get_track_interval(0, 'ds')
        vdd_intv = self.get_track_interval(self.num_rows - 1, 'ds')
        vss = _connect_supply(self, vss_w, vss_list, vss_intv, tr_manager, round_up=False,
                              exc_set={en3_htr_idx})
        vdd = _connect_supply(self, vdd_w, vdd_list, vdd_intv, tr_manager, round_up=True)

        # fill space
        self.fill_space()

        # add pins.  Connect to xm_layer if track information are given
        q_warrs = [inv_ports['q'], sr_ports['q']]
        qb_warrs = [inv_ports['qb'], sr_ports['qb']]
        scan_s = sr_ports['scan_s']
        if tr_info is None:
            en_lbl = 'en:'
            q, qb = self.connect_differential_tracks(q_warrs, qb_warrs, xm_layer, xm_locs[1],
                                                     xm_locs[0], width=xm_w_q)
        else:
            en_lbl = 'en'
            q_idx, w_q = tr_info['q']
            qb_idx = tr_info['qb'][0]
            en_idx, w_en = tr_info['en']
            if div_pos_edge:
                clk_idx, w_clk = tr_info['clkp']
                clkb_idx = tr_info['clkn'][0]
            else:
                clk_idx, w_clk = tr_info['clkn']
                clkb_idx = tr_info['clkp'][0]
            vdd_idx, w_vdd = tr_info['VDD']
            vss_idx, w_vss = tr_info['VSS']
            s_idx = tr_manager.get_next_track(xm_layer, en_idx, w_en, 1, up=False)
            self._sa_clk_tidx = tr_manager.get_next_track(xm_layer, s_idx, 1, 'clk', up=False)

            q, qb = self.connect_differential_tracks(q_warrs, qb_warrs, xm_layer, q_idx, qb_idx,
                                                     width=w_q)
            en = self.connect_to_tracks(en, TrackID(xm_layer, en_idx))
            clk = self.connect_to_tracks(clk, TrackID(xm_layer, clk_idx, width=w_clk))
            vdd = self.connect_to_tracks(vdd, TrackID(xm_layer, vdd_idx, width=w_vdd))
            vss = self.connect_to_tracks(vss, TrackID(xm_layer, vss_idx, width=w_vss))
            scan_s = self.connect_to_tracks(scan_s, TrackID(xm_layer, s_idx), min_len_mode=0)
            # add fake port so we can match clock wires
            clkb = self.add_wires(xm_layer, clkb_idx, clk.lower_unit, clk.upper_unit, width=w_clk,
                                  unit_mode=True)
            self.add_pin('clkb', clkb, show=False)

        self.add_pin('q', q, show=show_pins)
        self.add_pin('qb', qb, show=show_pins)
        self.add_pin('en', en, label=en_lbl, show=show_pins)
        self.add_pin('clk', clk, show=show_pins)
        self.add_pin('VDD', vdd, show=show_pins)
        self.add_pin('VSS', vss, show=show_pins)
        self.add_pin('scan_s', scan_s, show=show_pins)

        # compute schematic parameters.
        n0_info = self.get_row_info(1)
        n1_info = self.get_row_info(2)
        n2_info = self.get_row_info(3)
        p0_info = self.get_row_info(4)
        p1_info = self.get_row_info(5)
        inv_seg.update(int_seg)
        self._sch_params = dict(
            lch=self.laygo_info.lch,
            w_dict=dict(
                n0=n0_info['w_max'],
                n1=n1_info['w_max'],
                n2=n2_info['w_max'],
                p0=p0_info['w_max'],
                p1=p1_info['w_max'],
            ),
            th_dict=dict(
                n0=n0_info['threshold'],
                n1=n1_info['threshold'],
                n2=n2_info['threshold'],
                p0=p0_info['threshold'],
                p1=p1_info['threshold'],
            ),
            seg_dict=inv_seg,
            sr_params=sr_params,
        )

    @classmethod
    def _get_gate_inv_info(cls, seg_dict):
        seg_pen = seg_dict['inv_pen']
        seg_inv = seg_dict['inv_inv']

        if seg_inv % 2 != 0:
            raise ValueError('This generator only works for even inv_inv.')
        if seg_pen % 4 != 2:
            raise ValueError('This generator only works for seg_pen = 2 mod 4.')

        return 2 * seg_inv + (seg_pen + 2)

    @classmethod
    def _get_integ_amp_info(cls, seg_dict):
        seg_rst = seg_dict['int_rst']
        seg_pen = seg_dict['int_pen']
        seg_in = seg_dict['int_in']

        if seg_rst % 2 != 0 or seg_pen % 2 != 0 or seg_in % 2 != 0:
            raise ValueError('This generator only works for even sr_inv/sr_drv/sr_sp.')

        return 2 * max(seg_in, seg_rst + seg_pen)

    @classmethod
    def _get_sr_latch_info(cls, seg_dict):
        seg_inv = seg_dict['sr_inv']
        seg_drv = seg_dict['sr_drv']
        seg_set = seg_dict['sr_set']
        seg_sp = seg_dict['sr_sp']
        seg_nand = seg_dict['sr_nand']

        if seg_inv % 2 != 0 or seg_drv % 2 != 0 or seg_sp % 2 != 0:
            raise ValueError('This generator only works for even sr_inv/sr_drv/sr_sp.')
        if seg_sp < 2:
            raise ValueError('sr_sp must be >= 2.')

        seg_nand_set = max(seg_nand * 2, seg_set)
        return (seg_inv + seg_drv + seg_sp + seg_nand_set) * 2

    def _draw_gate_inv(self, start, seg_tot, seg_dict, tr_manager):
        blk_sp = seg_dict['blk_sp']
        seg_pen = seg_dict['inv_pen']
        seg_inv = seg_dict['inv_inv']

        xleft = self.laygo_info.col_to_coord(start, unit_mode=True)
        xright = self.laygo_info.col_to_coord(start + seg_tot, unit_mode=True)

        col_inv = start + (seg_pen + 2) // 2
        ridx = 3
        ninvl = self.add_laygo_mos(ridx, col_inv, seg_inv)
        pinvl = self.add_laygo_mos(ridx + 1, col_inv, seg_inv)
        col_inv += seg_inv
        ninvr = self.add_laygo_mos(ridx, col_inv, seg_inv)
        pinvr = self.add_laygo_mos(ridx + 1, col_inv, seg_inv)
        pgate = self.add_laygo_mos(ridx + 2, start, seg_tot, gate_loc='s')

        # get track indices
        hm_layer = self.conn_layer + 1
        vm_layer = hm_layer + 1
        hm_w_in = tr_manager.get_width(hm_layer, 'in')
        hm_w_out = tr_manager.get_width(hm_layer, 'out')
        vm_w_in = tr_manager.get_width(vm_layer, 'in')
        in_start, in_stop = self.get_track_interval(3, 'g')
        nin_locs = tr_manager.spread_wires(hm_layer, ['in', 'in'], in_stop - in_start,
                                           'in', alignment=1, start_idx=in_start)
        gb_idx0 = self.get_track_index(3, 'gb', 0)
        gb_idx1 = self.get_track_index(4, 'gb', 0)
        ntr = gb_idx1 - gb_idx0 + 1
        out_locs = tr_manager.spread_wires(hm_layer, [1, 'out', 1, 'out', 1], ntr,
                                           'out', alignment=0, start_idx=gb_idx0)
        pin_idx0 = self.get_track_index(4, 'g', -1)
        clk_idx = self.get_track_index(5, 'g', -1)
        en_idx = clk_idx + 1
        tleft = self.grid.coord_to_nearest_track(vm_layer, xleft, unit_mode=True, half_track=True,
                                                 mode=1)
        tright = self.grid.coord_to_nearest_track(vm_layer, xright, unit_mode=True, half_track=True,
                                                  mode=-1)
        ntr = tright - tleft + 1
        vin_locs = tr_manager.align_wires(vm_layer, ['in', 'in'], ntr, alignment=0, start_idx=tleft)
        xleft = self.laygo_info.col_to_coord(col_inv + seg_inv, unit_mode=True)
        xright = self.laygo_info.col_to_coord(start + seg_tot + blk_sp, unit_mode=True)
        tleft = self.grid.coord_to_nearest_track(vm_layer, xleft, unit_mode=True, half_track=True,
                                                 mode=1)
        tright = self.grid.coord_to_nearest_track(vm_layer, xright, unit_mode=True, half_track=True,
                                                  mode=-1)
        ntr = tright - tleft + 1
        vout_locs = tr_manager.align_wires(vm_layer, ['in', 'in'], ntr, alignment=0,
                                           start_idx=tleft)

        # connect pmos tail
        tid = self.make_track_id(5, 'gb', 0)
        self.connect_to_tracks([pinvl['s'], pinvr['s'], pgate['s']], tid)

        # connect outputs
        outp = [ninvr['d'], pinvr['d']]
        outn = [ninvl['d'], pinvl['d']]
        outp, outn = self.connect_differential_tracks(outp, outn, hm_layer, out_locs[3],
                                                      out_locs[1], width=hm_w_out)
        outp, outn = self.connect_differential_tracks(outp, outn, vm_layer, vout_locs[1],
                                                      vout_locs[0], width=vm_w_in)

        # connect inputs
        ninp, ninn = self.connect_differential_tracks(ninvl['g'], ninvr['g'], hm_layer, nin_locs[1],
                                                      nin_locs[0], width=hm_w_in)
        pinp, pinn = self.connect_differential_tracks(pinvl['g'], pinvr['g'], hm_layer, pin_idx0,
                                                      pin_idx0 + 1, width=hm_w_in)
        inp, inn = self.connect_differential_tracks([ninp, pinp], [ninn, pinn], vm_layer,
                                                    vin_locs[0], vin_locs[1], width=vm_w_in)

        # connect enables and clocks
        num_en = (seg_pen + 2) // 4
        pgate_warrs = pgate['g'].to_warr_list()
        en_warrs = pgate_warrs[:num_en] + pgate_warrs[-num_en:]
        en = self.connect_to_tracks(en_warrs, TrackID(hm_layer, en_idx))
        clk_warrs = pgate_warrs[num_en:-num_en]
        clk = self.connect_to_tracks(clk_warrs, TrackID(hm_layer, clk_idx))

        ports = {'VDD': pgate['d'], 'VSS': [ninvl['s'], ninvr['s']],
                 'mp': outp, 'mn': outn,
                 'qb': inp, 'q': inn,
                 'en': en, 'clk': clk}

        inv_seg_dict = dict(
            inv_clk=2 * seg_inv + 2,
            inv_en=seg_pen,
            inv_inv=seg_inv,
        )
        return ports, inv_seg_dict

    def _draw_integ_amp(self, start, seg_tot, seg_dict, tr_manager):
        seg_rst = seg_dict['int_rst']
        seg_pen = seg_dict['int_pen']
        seg_in = seg_dict['int_in']

        xleft = self.laygo_info.col_to_coord(start + 1, unit_mode=True)
        xright = self.laygo_info.col_to_coord(start + seg_tot - 1, unit_mode=True)

        # place instances
        seg_single = seg_tot // 2
        ridx = 1
        nclk = self.add_laygo_mos(ridx, start, seg_tot)
        nen = self.add_laygo_mos(ridx + 1, start, seg_tot, gate_loc='s')
        col_l = start + seg_single - seg_in
        inl = self.add_laygo_mos(ridx + 2, col_l, seg_in)
        inr = self.add_laygo_mos(ridx + 2, col_l + seg_in, seg_in)
        ridx = 4
        col = start + seg_single - seg_rst - seg_pen
        penl = self.add_laygo_mos(ridx, col, seg_pen)
        col += seg_pen
        rstl = self.add_laygo_mos(ridx, col, seg_rst)
        col += seg_rst
        rstr = self.add_laygo_mos(ridx, col, seg_rst)
        col += seg_rst
        penr = self.add_laygo_mos(ridx, col, seg_pen)

        # get track locations
        hm_layer = self.conn_layer + 1
        vm_layer = hm_layer + 1
        hm_w_tail = tr_manager.get_width(hm_layer, 'tail')
        hm_w_in = tr_manager.get_width(hm_layer, 'in')
        hm_w_out = tr_manager.get_width(hm_layer, 'out')
        vm_w_out = tr_manager.get_width(vm_layer, 'out')
        vm_w_clk = tr_manager.get_width(vm_layer, 'clk')
        tail_off = tr_manager.place_wires(hm_layer, ['tail'])[1][0]
        in_start, in_stop = self.get_track_interval(3, 'g')
        in_locs = tr_manager.spread_wires(hm_layer, ['in', 'in'], in_stop - in_start,
                                          'in', alignment=1, start_idx=in_start)
        gb_idx0 = self.get_track_index(3, 'gb', 0)
        gb_idx1 = self.get_track_index(4, 'gb', 0)
        ntr = gb_idx1 - gb_idx0 + 1
        out_locs = tr_manager.spread_wires(hm_layer, [1, 'out', 1, 'out', 1], ntr,
                                           'out', alignment=0, start_idx=gb_idx0)
        pg_start = self.get_track_interval(4, 'g')[0]
        pg_locs = tr_manager.place_wires(hm_layer, [1, 1, 1, 1], start_idx=pg_start)[1]
        tleft = self.grid.coord_to_nearest_track(vm_layer, xleft, unit_mode=True, half_track=True,
                                                 mode=1)
        tright = self.grid.coord_to_nearest_track(vm_layer, xright, unit_mode=True, half_track=True,
                                                  mode=-1)
        ntr = tright - tleft + 1
        vm_locs = tr_manager.spread_wires(vm_layer, [1, 'out', 'clk', 'out', 1], ntr,
                                          'out', alignment=0, start_idx=tleft)

        # connect intermediate wires
        tidx = self.get_track_index(1, 'gb', 0)
        self.connect_to_tracks([nclk['d'], nen['d']],
                               TrackID(hm_layer, tidx + tail_off, width=hm_w_tail))
        tidx = self.get_track_index(2, 'gb', 0)
        self.connect_to_tracks([nen['s'], inl['s'], inr['s']],
                               TrackID(hm_layer, tidx + tail_off, width=hm_w_tail))

        # connect gate wires
        inp, inn = self.connect_differential_tracks(inl['g'], inr['g'], hm_layer, in_locs[1],
                                                    in_locs[0], width=hm_w_in)

        # connect enables
        en = self.connect_to_tracks(nen['g'], self.make_track_id(2, 'g', -1))
        enl = self.connect_to_tracks(penl['g'], TrackID(hm_layer, pg_locs[1]), min_len_mode=0)
        enr = self.connect_to_tracks(penr['g'], TrackID(hm_layer, pg_locs[1]), min_len_mode=0)
        enl = self.connect_to_tracks([en, enl], TrackID(vm_layer, vm_locs[0]))
        enr = self.connect_to_tracks([en, enr], TrackID(vm_layer, vm_locs[-1]))

        # connect clocks
        clk1 = self.connect_to_tracks(nclk['g'], self.make_track_id(1, 'g', -1))
        clk2 = self.connect_to_tracks([rstl['g'], rstr['g']], TrackID(hm_layer, pg_locs[0]))
        clk = self.connect_to_tracks([clk1, clk2], TrackID(vm_layer, vm_locs[2], width=vm_w_clk))

        # connect outputs
        outp = [inr['d'], rstr['d'], penr['d']]
        outn = [inl['d'], rstl['d'], penl['d']]
        outp, outn = self.connect_differential_tracks(outp, outn, hm_layer, out_locs[3],
                                                      out_locs[1], width=hm_w_out)
        outp, outn = self.connect_differential_tracks(outp, outn, vm_layer, vm_locs[1], vm_locs[3],
                                                      width=vm_w_out)
        outp, outn = self.connect_differential_tracks(outp, outn, hm_layer, pg_locs[3],
                                                      pg_locs[2], width=1)

        ports = {'VSS': nclk['s'], 'VDD': [penl['s'], rstl['s'], rstr['s'], penr['s']],
                 'mp': inp, 'mn': inn,
                 'sb': outn, 'rb': outp,
                 'en': [enl, enr], 'clk': clk}

        int_seg_dict = dict(
            int_clk=seg_tot,
            int_en=seg_tot,
            int_in=seg_in,
            int_pen=seg_pen,
            int_rst=seg_rst,
        )
        return ports, int_seg_dict

    def _draw_sr_latch(self, start, seg_tot, seg_dict, tr_manager, en_htr_idx):
        seg_nand = seg_dict['sr_nand']
        seg_set = seg_dict['sr_set']
        seg_sp = seg_dict['sr_sp']
        seg_inv = seg_dict['sr_inv']
        seg_drv = seg_dict['sr_drv']
        seg_pnor = seg_dict.get('sr_pnor', 1)
        seg_nnor = seg_dict.get('sr_nnor', 2)
        seg_sinv = seg_dict.get('sr_sinv', 2)
        fg_nand = seg_nand * 2

        if seg_set > seg_drv:
            raise ValueError('Must have sr_set <= sr_drv')
        if seg_pnor > seg_nand:
            raise ValueError('Must have sr_pnor <= sr_nand.')
        if seg_nnor % 2 == 1 or seg_sinv % 2 == 1:
            raise ValueError('sr_nnor and sr_sinv must be even.')

        # place instances
        stop = start + seg_tot
        ridx = 3
        cidx = start
        col_spl = cidx + seg_nand * 2 + 1
        col_norl = cidx
        nnandl = self.add_laygo_mos(ridx, cidx, seg_nand, gate_loc='s', stack=True)
        pnandl = self.add_laygo_mos(ridx + 1, cidx, seg_nand, gate_loc='s', stack=True)
        pnorl = self.add_laygo_mos(ridx + 2, cidx, seg_pnor, gate_loc='s', stack=True, flip=True)
        nnor1l = self.add_laygo_mos(ridx - 1, cidx, seg_nnor)
        nnor2l = self.add_laygo_mos(ridx - 1, cidx + seg_nnor, seg_nnor)
        cidx = stop - fg_nand
        col_spr = cidx - 1
        col_norr = cidx + seg_pnor
        nnandr = self.add_laygo_mos(ridx, cidx, seg_nand, gate_loc='s', stack=True, flip=True)
        pnandr = self.add_laygo_mos(ridx + 1, cidx, seg_nand, gate_loc='s', stack=True, flip=True)
        pnorr = self.add_laygo_mos(ridx + 2, cidx, seg_pnor, gate_loc='s', stack=True)
        nnor1r = self.add_laygo_mos(ridx - 1, cidx + fg_nand - seg_nnor, seg_nnor)
        nnor2r = self.add_laygo_mos(ridx - 1, cidx + fg_nand - 2 * seg_nnor, seg_nnor)
        psinv = self.add_laygo_mos(ridx + 2, cidx - 1, 1)
        start += fg_nand + seg_sp
        stop -= fg_nand + seg_sp

        ndrvl = self.add_laygo_mos(ridx, start, seg_drv)
        setl = self.add_laygo_mos(ridx - 1, start, seg_set)
        pdrvl = self.add_laygo_mos(ridx + 1, start, seg_drv)
        cidx = stop - seg_drv
        ndrvr = self.add_laygo_mos(ridx, cidx, seg_drv)
        setr = self.add_laygo_mos(ridx - 1, cidx + seg_drv - seg_set, seg_set)
        pdrvr = self.add_laygo_mos(ridx + 1, cidx, seg_drv)
        start += seg_drv
        stop -= seg_drv

        ninvl = self.add_laygo_mos(ridx, start, seg_inv)
        pinvl = self.add_laygo_mos(ridx + 1, start, seg_inv)
        cidx = stop - seg_inv
        ninvr = self.add_laygo_mos(ridx, cidx, seg_inv)
        pinvr = self.add_laygo_mos(ridx + 1, cidx, seg_inv)
        if seg_sinv % 4 == 0:
            start += seg_inv - seg_sinv // 2
        else:
            start += seg_inv - (seg_sinv + 2) // 2
        nsinv = self.add_laygo_mos(ridx - 1, start, seg_sinv)

        # compute track locations
        hm_layer = self.conn_layer + 1
        vm_layer = hm_layer + 1
        xm_layer = vm_layer + 1
        hm_w_in = tr_manager.get_width(hm_layer, 'in')
        hm_w_out = tr_manager.get_width(hm_layer, 'div')
        vm_w_out = tr_manager.get_width(vm_layer, 'div')
        gb_idx0 = self.get_track_index(3, 'gb', 0)
        gb_idx1 = self.get_track_index(4, 'gb', 0)
        ntr = gb_idx1 - gb_idx0 + 1
        gb_locs = tr_manager.spread_wires(hm_layer, [1, 'div', 1, 'div', 1], ntr, 'div',
                                          alignment=0, start_idx=gb_idx0)
        ng_ntr, ng_locs = tr_manager.place_wires(hm_layer, ['in', 'in', 1, 1])
        ng_stop = self.get_track_interval(3, 'g')[1]
        ng_locs = [idx + ng_stop - ng_ntr for idx in ng_locs]
        pg_start = self.get_track_interval(4, 'g')[0]
        pg_locs = tr_manager.place_wires(hm_layer, [1, 1, 1, 1], start_idx=pg_start)[1]
        ng0_tid = TrackID(hm_layer, ng_locs[3])
        ng1_tid = TrackID(hm_layer, ng_locs[2])
        pg0_tid = TrackID(hm_layer, pg_locs[0])
        pg1_tid = TrackID(hm_layer, pg_locs[1])
        setd_tid = self.make_track_id(2, 'gb', 1)
        psg_tid = self.make_track_id(5, 'g', -1)
        pen_tid = TrackID(hm_layer, psg_tid.base_index + 1)
        pvdd_tid = self.make_track_id(5, 'gb', 0)
        psetg_tid = self.make_track_id(5, 'gb', 1)
        psetg_tid2 = self.make_track_id(5, 'gb', 2)

        xl = ndrvl['d'].get_bbox_array(self.grid).xc_unit
        xr = ndrvr['d'].get_bbox_array(self.grid).xc_unit
        vm_qb_idx = self.grid.coord_to_nearest_track(vm_layer, xl, half_track=True, mode=-1,
                                                     unit_mode=True)
        vm_q_idx = self.grid.coord_to_nearest_track(vm_layer, xr, half_track=True, mode=1,
                                                    unit_mode=True)
        vm_xc_idx = self.grid.get_middle_track(vm_q_idx, vm_qb_idx)
        vm_q_tid = TrackID(vm_layer, vm_q_idx, width=vm_w_out)
        vm_qb_tid = TrackID(vm_layer, vm_qb_idx, width=vm_w_out)
        xl = self.laygo_info.col_to_coord(col_spl, unit_mode=True)
        xr = self.laygo_info.col_to_coord(col_spr, unit_mode=True)
        vm_r_idx = self.grid.coord_to_nearest_track(vm_layer, xl, half_track=True, mode=-1,
                                                    unit_mode=True)
        vm_s_idx = self.grid.coord_to_nearest_track(vm_layer, xr, half_track=True, mode=1,
                                                    unit_mode=True)
        xl = self.laygo_info.col_to_coord(col_norl, unit_mode=True)
        xr = self.laygo_info.col_to_coord(col_norr, unit_mode=True)
        vm_ssb_idx = self.grid.coord_to_nearest_track(vm_layer, xl, half_track=True, mode=-1,
                                                      unit_mode=True)
        vm_ss_idx = self.grid.coord_to_nearest_track(vm_layer, xr, half_track=True, mode=1,
                                                     unit_mode=True)
        vm_r_tid = TrackID(vm_layer, vm_r_idx)
        vm_s_tid = TrackID(vm_layer, vm_s_idx)
        xl = ninvl['d'].get_bbox_array(self.grid).xc_unit
        xr = ninvr['d'].get_bbox_array(self.grid).xc_unit
        vm_sb_idx = self.grid.coord_to_nearest_track(vm_layer, xl, half_track=True, mode=-1,
                                                     unit_mode=True)
        vm_rb_idx = self.grid.coord_to_nearest_track(vm_layer, xr, half_track=True, mode=1,
                                                     unit_mode=True)

        ymid = self.grid.track_to_coord(hm_layer, gb_locs[2], unit_mode=True)
        xm_mid = self.grid.coord_to_nearest_track(xm_layer, ymid, half_track=True, mode=0,
                                                  unit_mode=True)
        xm_locs = tr_manager.place_wires(xm_layer, ['div', 'div'])[1]
        mid = self.grid.get_middle_track(xm_locs[0], xm_locs[1])
        xm_locs = [val + xm_mid - mid for val in xm_locs]

        # gather wires
        vss_list = [inst['s'] for inst in (ndrvl, ndrvr, ninvl, ninvr)]
        vdd_list = [inst['s'] for inst in (pdrvl, pdrvr, pinvl, pinvr)]
        q_list = self.connect_wires([inst['d'] for inst in (nnandl, pnandl, ndrvl, pdrvl)])
        qb_list = self.connect_wires([inst['d'] for inst in (nnandr, pnandr, ndrvr, pdrvr)])
        s_list = self.connect_wires([ninvr['d'], pinvr['d']])
        r_list = self.connect_wires([ninvl['d'], pinvl['d']])
        nor_vss_list = [nnor1l['s'], nnor2l['s'], nnor1r['s'], nnor2r['s']]
        nor_vss_list.extend(vss_list)
        nand_vss_list = [nnandl['s'], nnandr['s']]
        nand_vdd_list = [pnandl['s'], pnandr['s']]
        nand_vss_list.extend(vss_list)
        nand_vdd_list.extend(vdd_list)

        ports = {}
        # connect middle wires
        q_warr, qb_warr = self.connect_differential_tracks(q_list, qb_list, hm_layer, gb_locs[3],
                                                           gb_locs[1], width=hm_w_out)
        self.connect_to_tracks(nand_vss_list, TrackID(hm_layer, gb_locs[0]))
        self.connect_to_tracks(nand_vdd_list, TrackID(hm_layer, gb_locs[-1]))
        sr_tid = TrackID(hm_layer, gb_locs[2])
        s_warr = self.connect_to_tracks(s_list, sr_tid)
        r_warr = self.connect_to_tracks(r_list, sr_tid)

        # export vss/vdd
        ports['VSS'] = nor_vss_list
        ports['VDD'] = vdd_list

        # connect q/qb
        for name, vtid, ninst, pinst, sinst, warr in \
                [('q', vm_q_tid, nnandr, pnandr, setr, q_warr),
                 ('qb', vm_qb_tid, nnandl, pnandl, setl, qb_warr)]:
            ng = self.connect_to_tracks(ninst['g1'], ng1_tid)
            pg = self.connect_to_tracks(pinst['g1'], pg1_tid)
            sd = self.connect_to_tracks(sinst['d'], setd_tid)
            vm_warr = self.connect_to_tracks([warr, ng, pg, sd], vtid)
            ports[name] = vm_warr

        # connect s/r
        for vtid, ninst, pinst, warr in [(vm_r_tid, ndrvl, pnandl, r_warr),
                                         (vm_s_tid, ndrvr, pnandr, s_warr)]:
            ng = self.connect_to_tracks(ninst['g'], ng0_tid)
            pg = self.connect_to_tracks(pinst['g0'], pg0_tid)
            self.connect_to_tracks([warr, pg, ng], vtid)

        # connect sb/rb
        sbb, rbb = self.connect_differential_tracks([nnandl['g0'], ninvr['g']],
                                                    [nnandr['g0'], ninvl['g']], hm_layer,
                                                    ng_locs[0], ng_locs[1], width=hm_w_in)
        sbt, rbt = self.connect_differential_tracks([pdrvl['g'], pinvr['g']],
                                                    [pdrvr['g'], pinvl['g']], hm_layer,
                                                    pg_locs[2], pg_locs[3], width=1)
        self.connect_differential_tracks([sbb, sbt], [rbb, rbt], vm_layer,
                                         vm_sb_idx, vm_rb_idx)
        ports['sb'] = sbt
        ports['rb'] = rbt

        # connect bottom NMOS logic nets
        nnord_tid = nsinvd_tid = self.make_track_id(2, 'gb', 0)
        nsetg_tid = self.make_track_id(2, 'g', -1)
        nen_tid = TrackID(hm_layer, nsetg_tid.base_index - 1)
        nsgr_tid = TrackID(hm_layer, nen_tid.base_index - 1)
        nsgl_tid = TrackID(hm_layer, nsgr_tid.base_index - 1)

        scan_ns = self.connect_to_tracks([nsinv['g'], nnor1r['g']], nsgr_tid, min_len_mode=0)
        scan_sb_ng = self.connect_to_tracks(nnor1l['g'], nsgl_tid, min_len_mode=0)
        scan_sb_nd = self.connect_to_tracks(nsinv['d'], nsinvd_tid, min_len_mode=0)
        nen = self.connect_to_tracks([nnor2l['g'], nnor2r['g']], nen_tid)
        nen_tid = TrackID(vm_layer, en_htr_idx / 2)
        nen = self.connect_to_tracks(nen, nen_tid, min_len_mode=1)
        ports['nen'] = nen
        # connect top PMOS logic nets
        scan_ps = self.connect_to_tracks([psinv['g'], pnorr['g0']], psg_tid, min_len_mode=0)
        scan_sb_pg = self.connect_to_tracks(pnorl['g0'], psg_tid, min_len_mode=0)
        scan_sb_pd = self.connect_to_tracks(psinv['s'], psetg_tid, min_len_mode=-1)
        pvdd_list = [pnorl['s'], pnorr['s']]
        pvdd_list.extend(vdd_list)
        self.connect_to_tracks(pvdd_list, pvdd_tid)
        pen = self.connect_to_tracks([pnorl['g1'], pnorr['g1']], pen_tid)
        ports['pen'] = pen
        # connect logic nets to vm layer
        vm_mid_idx = self.grid.coord_to_nearest_track(vm_layer, scan_sb_nd.middle_unit,
                                                      half_track=True, mode=0, unit_mode=True)
        self.connect_to_tracks([scan_sb_ng, scan_sb_nd], TrackID(vm_layer, vm_mid_idx))
        self.connect_to_tracks([scan_sb_pg, scan_sb_ng], TrackID(vm_layer, vm_ssb_idx))
        self.connect_to_tracks([scan_sb_pg, scan_sb_pd], TrackID(vm_layer, vm_xc_idx))
        scan_s = self.connect_to_tracks([scan_ps, scan_ns], TrackID(vm_layer, vm_ss_idx))
        ports['scan_s'] = scan_s

        # connect override transistor gate
        nnordr = self.connect_to_tracks([nnor1r['d'], nnor2r['d']], nnord_tid, min_len_mode=-1)
        nnordl = self.connect_to_tracks([nnor1l['d'], nnor2l['d']], nnord_tid, min_len_mode=1)
        nsetgl = self.connect_to_tracks(setl['g'], nsetg_tid, min_len_mode=-1)
        nsetgr = self.connect_to_tracks(setr['g'], nsetg_tid, min_len_mode=1)
        psetgr = self.connect_to_tracks(pnorr['d'], psetg_tid2, min_len_mode=-1)
        psetgl = self.connect_to_tracks(pnorl['d'], psetg_tid, min_len_mode=1)
        self.connect_to_tracks([nnordl, nsetgl, psetgl], TrackID(vm_layer, vm_ssb_idx + 1))
        self.connect_to_tracks([nnordr, nsetgr, psetgr], TrackID(vm_layer, vm_ss_idx - 1))

        nlrow_info = self.get_row_info(1)
        srow_info = self.get_row_info(2)
        nrow_info = self.get_row_info(3)
        prow_info = self.get_row_info(4)
        plrow_info = self.get_row_info(5)

        sr_sch_params = dict(
            lch=self.laygo_info.lch,
            w_dict=dict(
                n=nrow_info['w_max'],
                nl=nlrow_info['w_max'],
                s=srow_info['w_max'],
                p=prow_info['w_max'],
                pl=plrow_info['w_max'],
            ),
            th_dict=dict(
                n=nrow_info['threshold'],
                nl=nlrow_info['threshold'],
                s=srow_info['threshold'],
                p=prow_info['threshold'],
                pl=plrow_info['threshold'],
            ),
            seg_dict=dict(
                nand=seg_nand,
                inv=seg_inv,
                drv=seg_drv,
                set=seg_set,
                pnor=seg_pnor,
                nnor=seg_nnor,
                nsinv=seg_sinv,
                psinv=1,
            )
        )

        return ports, xm_locs, sr_sch_params


class EnableRetimer(LaygoBase):
    """A retimer circuit for divider's enable signal.

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
    **kwargs :
        dictionary of optional parameters.  See documentation of
        :class:`bag.layout.template.TemplateBase` for details.
    """

    def __init__(self, temp_db, lib_name, params, used_names, **kwargs):
        # type: (TemplateDB, str, Dict[str, Any], Set[str], **kwargs) -> None
        LaygoBase.__init__(self, temp_db, lib_name, params, used_names, **kwargs)
        self._sch_params = None
        self._fg_tot = None
        self._en3_htr_tidx = None

    @property
    def sch_params(self):
        # type: () -> Dict[str, Any]
        return self._sch_params

    @property
    def fg_tot(self):
        # type: () -> int
        return self._fg_tot

    @property
    def en3_htr_tidx(self):
        # type: () -> Union[float, int]
        return self._en3_htr_tidx

    @classmethod
    def get_col_info(cls, seg_dict, abut_mode):
        blk_sp = 2

        # compute number of columns, then draw floorplan
        seg_in = seg_dict['re_in']
        seg_fb = seg_dict['re_fb']
        seg_out = seg_dict['re_out']
        seg_buf = seg_dict['re_buf']

        if abut_mode & 1 != 0:
            # abut on left
            inc_coll = blk_sp
        else:
            inc_coll = 0
        if abut_mode & 2 != 0:
            # abut on right
            inc_colr = blk_sp
        else:
            inc_colr = 0

        ncol_lat0 = seg_in + seg_fb + seg_out + 2 * blk_sp
        ncol_lat1 = seg_in + seg_fb + seg_buf + 2 * blk_sp

        ncol_ff0 = 2 * ncol_lat0 + blk_sp
        ncol_ff1 = ncol_lat0 + ncol_lat1 + blk_sp
        num_col = (ncol_ff0 + ncol_ff1 + 2 * blk_sp) + ncol_lat1 + inc_coll + inc_colr
        return (num_col, ncol_ff0, ncol_ff1, ncol_lat0,
                seg_in, seg_fb, seg_out, seg_buf, blk_sp, inc_coll, inc_colr)

    @classmethod
    def get_params_info(cls):
        # type: () -> Dict[str, str]
        return dict(
            config='laygo configuration dictionary.',
            row_layout_info='The AnalogBase layout information dictionary.',
            seg_dict='Number of segments dictionary.',
            tr_widths='Track width dictionary.',
            tr_spaces='Track spacing dictionary.',
            tr_info='output track information dictionary.',
            fg_min='Minimum number of core fingers.',
            end_mode='The LaygoBase end_mode flag.',
            abut_mode='The left/right abut mode flag.',
            show_pins='True to show pins.',
        )

    @classmethod
    def get_default_param_values(cls):
        # type: () -> Dict[str, Any]
        return dict(
            tr_info=None,
            fg_min=0,
            end_mode=None,
            abut_mode=0,
            show_pins=True,
        )

    def draw_layout(self):
        row_layout_info = self.params['row_layout_info']
        seg_dict = self.params['seg_dict'].copy()
        tr_widths = self.params['tr_widths']
        tr_spaces = self.params['tr_spaces']
        tr_info = self.params['tr_info']
        fg_min = self.params['fg_min']
        end_mode = self.params['end_mode']
        abut_mode = self.params['abut_mode']
        show_pins = self.params['show_pins']

        tmp = self.get_col_info(seg_dict, abut_mode)
        (num_col, ncol_ff0, ncol_ff1, ncol_lat0,
         seg_in, seg_fb, seg_out, seg_buf, blk_sp, col_ff0, inc_colr) = tmp

        if fg_min > num_col:
            deltal = (fg_min - num_col) // 4 * 2
            col_ff0 += deltal
            inc_colr += (fg_min - num_col - deltal)
            num_col = fg_min
        self._fg_tot = num_col
        self.set_rows_direct(row_layout_info, end_mode=end_mode, num_col=num_col)

        # draw individual blocks
        tr_manager = TrackManager(self.grid, tr_widths, tr_spaces, half_space=True)
        col_ff1 = col_ff0 + ncol_ff0 + blk_sp
        col_lat = col_ff1 + ncol_ff1 + blk_sp
        vss_w, vdd_w = _draw_substrate(self, col_ff0, num_col, num_col - inc_colr - col_ff0)
        ff0_ports = self._draw_ff(col_ff0, ncol_lat0, seg_in, seg_fb, seg_out, seg_out, blk_sp,
                                  draw_vm_in=True)
        ff1_ports = self._draw_ff(col_ff1, ncol_lat0, seg_in, seg_fb, seg_out, seg_buf, blk_sp,
                                  draw_vm_in=False)
        lat_ports = self._draw_lat(col_lat, seg_in, seg_fb, seg_buf, blk_sp,
                                   draw_vm_in=False)

        # fill space
        self.fill_space()

        # export IO pins
        in_pin = ff0_ports['in']
        en3_pin = ff1_ports['out']
        self.add_pin('in', in_pin, show=show_pins)
        self.add_pin('en3', en3_pin, show=show_pins)
        self.add_pin('en2', lat_ports['out'], show=show_pins)

        # connect intermediate wires
        mid_hm = ff0_ports['out_hm']
        mid_hm.extend(ff1_ports['in'])
        self.connect_wires(mid_hm)
        mid_hm = ff1_ports['out_hm']
        mid_hm.extend(lat_ports['in'])
        self.connect_wires(mid_hm)

        clkp = ff0_ports['clk']
        clkp.extend(ff1_ports['clk'])
        clkp.append(lat_ports['clkb'])
        clkn = ff0_ports['clkb']
        clkn.extend(ff1_ports['clkb'])
        clkn.append(lat_ports['clk'])

        en3_htr_idx = int(round(en3_pin.track_id.base_index * 2))
        # TODO: HACK.  Figure out what's wrong
        self._en3_htr_tidx = en3_htr_idx if abut_mode & 1 != 0 else en3_htr_idx + 16
        vss_inc_set = set((int(round(warr.track_id.base_index * 2)) for warr in clkp))
        vss_inc_set.add(int(round(in_pin.track_id.base_index * 2)))
        vdd_inc_set = set((int(round(warr.track_id.base_index * 2)) for warr in clkn))
        vss_exc_set = {en3_htr_idx}

        # connect supply wires
        vss_list = [ff0_ports['VSS'], ff1_ports['VSS'], lat_ports['VSS']]
        vdd_list = [ff0_ports['VDD'], ff1_ports['VDD'], lat_ports['VDD']]
        vss_intv = self.get_track_interval(0, 'ds')
        vdd_intv = self.get_track_interval(self.num_rows - 1, 'ds')
        vss = _connect_supply(self, vss_w, vss_list, vss_intv, tr_manager, round_up=False,
                              inc_set=vss_inc_set, exc_set=vss_exc_set)
        vdd = _connect_supply(self, vdd_w, vdd_list, vdd_intv, tr_manager, round_up=True,
                              inc_set=vdd_inc_set)

        self.add_pin('VSS_vm', vss, show=show_pins)
        self.add_pin('VDD_vm', vdd, show=show_pins)
        self.add_pin('clkp_vm', clkp, show=show_pins)
        self.add_pin('clkn_vm', clkn, show=show_pins)

        if tr_info is not None:
            xm_layer = self.conn_layer + 3
            vdd_idx, w_vdd = tr_info['VDD']
            vss_idx, w_vss = tr_info['VSS']
            vdd = self.connect_to_tracks(vdd, TrackID(xm_layer, vdd_idx, width=w_vdd))
            vss = self.connect_to_tracks(vss, TrackID(xm_layer, vss_idx, width=w_vss))

        self.add_pin('clkp', clkp, show=show_pins)
        self.add_pin('clkn', clkn, show=show_pins)
        self.add_pin('VDD', vdd, show=show_pins)
        self.add_pin('VSS', vss, show=show_pins)

        nin_info = self.get_row_info(2)
        nen_info = self.get_row_info(3)
        pen_info = self.get_row_info(4)
        pin_info = self.get_row_info(5)
        self._sch_params = dict(
            lch=self.laygo_info.lch,
            w_dict=dict(nin=nin_info['w_max'], nen=nen_info['w_max'],
                        pin=pin_info['w_max'], pen=pen_info['w_max']),
            th_dict=dict(nin=nin_info['threshold'], nen=nen_info['threshold'],
                         pin=pin_info['threshold'], pen=pen_info['threshold']),
            seg_dict=dict(
                pt0=seg_in, nt0=seg_in,
                pt1=seg_fb, nt1=seg_fb,
                pinv=seg_out, ninv=seg_out,
            ),
            seg_buf=seg_buf,
        )

    def _draw_lat(self, col_in, seg_in, seg_fb, seg_out, blk_sp, draw_vm_in=True):
        grid = self.grid
        laygo_info = self.laygo_info

        row_nin = 2
        row_nen = row_nin + 1
        row_pen = row_nen + 1
        row_pin = row_pen + 1

        # draw transistors
        in_n = self.add_laygo_mos(row_nin, col_in, seg_in, gate_loc='s')
        in_nen = self.add_laygo_mos(row_nen, col_in, seg_in, gate_loc='d')
        in_p = self.add_laygo_mos(row_pin, col_in, seg_in, gate_loc='d')

        col_fb = col_in + seg_in + blk_sp
        fb_n = self.add_laygo_mos(row_nin, col_fb, seg_fb, gate_loc='s')
        fb_nen = self.add_laygo_mos(row_nen, col_fb, seg_fb, gate_loc='d')
        fb_pen = self.add_laygo_mos(row_pen, col_fb, seg_fb, gate_loc='d')
        fb_p = self.add_laygo_mos(row_pin, col_fb, seg_fb, gate_loc='s')

        col_out = col_fb + seg_fb + blk_sp
        out_n = self.add_laygo_mos(row_nen, col_out, seg_out, gate_loc='d')
        out_p = self.add_laygo_mos(row_pen, col_out, seg_out, gate_loc='d')

        # get track IDs
        hm_layer = self.conn_layer + 1
        vm_layer = hm_layer + 1
        nin_g = TrackID(hm_layer, self.get_track_index(row_nin, 'g', -1))
        nen_gp = TrackID(hm_layer, self.get_track_index(row_nen, 'g', -1))
        nen_gn = TrackID(hm_layer, nen_gp.base_index - 2)
        nen_gb = TrackID(hm_layer, self.get_track_index(row_nen, 'gb', -1))
        pen_gb = TrackID(hm_layer, self.get_track_index(row_pen, 'gb', -1))
        pen_g = TrackID(hm_layer, self.get_track_index(row_pen, 'g', -1))
        pin_g = TrackID(hm_layer, self.get_track_index(row_pin, 'g', -1))

        # connect to hm_layer
        # connect input tristate inverter
        self.connect_wires([in_nen['s'], in_n['s']])
        in_ng = self.connect_to_tracks(in_n['g'], nin_g, min_len_mode=-1)
        in_neng = self.connect_to_tracks(in_nen['g'], nen_gp, min_len_mode=1)
        in_pg = self.connect_to_tracks(in_p['g'], pin_g, min_len_mode=-1)

        # connect feedback tristate inverter
        self.connect_wires([fb_nen['s'], fb_n['s']])
        self.connect_wires([fb_pen['s'], fb_p['s']])
        fb_ng = self.connect_to_tracks(fb_n['g'], nin_g, min_len_mode=1)
        fb_neng = self.connect_to_tracks(fb_nen['g'], nen_gn, min_len_mode=-1)
        fb_peng = self.connect_to_tracks(fb_pen['g'], pen_g, min_len_mode=-1)
        fb_pg = self.connect_to_tracks(fb_p['g'], pin_g, min_len_mode=1)
        mid_warr = self.connect_to_tracks([in_p['d'], in_nen['d'], fb_nen['d'], fb_pen['d']],
                                          pen_gb, min_len_mode=1)

        # connect output inverter
        out_ng = self.connect_to_tracks(out_n['g'], nen_gp, min_len_mode=-1)
        out_pg = self.connect_to_tracks(out_p['g'], pen_g, min_len_mode=-1)
        out_warr = self.connect_to_tracks([out_p['d'], out_n['d']], nen_gb, min_len_mode=1)

        # connect to vm_layer
        # input wire
        vm_x = laygo_info.col_to_coord(col_in, unit_mode=True)
        vm_tidx = grid.coord_to_nearest_track(vm_layer, vm_x, half_track=True, mode=-1,
                                              unit_mode=True)
        in_hm = [in_ng, in_pg]
        if draw_vm_in:
            in_warr = self.connect_to_tracks(in_hm, TrackID(vm_layer, vm_tidx))
        else:
            in_warr = in_hm

        # clock wires
        vm_xn = laygo_info.col_to_coord(col_in + seg_in, unit_mode=True)
        vm_nidx = grid.coord_to_nearest_track(vm_layer, vm_xn, half_track=True, mode=-1,
                                              unit_mode=True)
        vm_xp = laygo_info.col_to_coord(col_fb, unit_mode=True)
        vm_pidx = grid.coord_to_nearest_track(vm_layer, vm_xp, half_track=True, mode=1,
                                              unit_mode=True)
        clk, clkb = self.connect_differential_tracks([in_neng, fb_peng], fb_neng, vm_layer,
                                                     vm_pidx, vm_nidx)

        # middle wire
        vm_x = laygo_info.col_to_coord(col_out, unit_mode=True)
        vm_idx = grid.coord_to_nearest_track(vm_layer, vm_x, half_track=True, mode=1,
                                             unit_mode=True)
        self.connect_to_tracks([out_ng, out_pg, mid_warr], TrackID(vm_layer, vm_idx))

        # out wire
        vm_x = laygo_info.col_to_coord(col_out + seg_out, unit_mode=True)
        out_tidx = grid.coord_to_nearest_track(vm_layer, vm_x, half_track=True, mode=1,
                                               unit_mode=True)
        out_hm = [out_warr, fb_pg, fb_ng]
        out_warr = self.connect_to_tracks(out_hm, TrackID(vm_layer, out_tidx))

        return {'VSS': [in_n['d'], fb_n['d'], out_n['s']],
                'VDD': [in_p['s'], fb_p['d'], out_p['s']],
                'in': in_warr,
                'out_hm': out_hm,
                'out': out_warr,
                'clk': clk,
                'clkb': clkb,
                }

    def _draw_ff(self, x0, ncol_lat0, seg_in, seg_fb, seg_out, seg_buf, blk_sp, draw_vm_in=True):
        m_ports = self._draw_lat(x0, seg_in, seg_fb, seg_out, blk_sp, draw_vm_in=draw_vm_in)
        s_ports = self._draw_lat(x0 + ncol_lat0 + blk_sp, seg_in, seg_fb, seg_buf,
                                 blk_sp, draw_vm_in=False)

        mid_hm = m_ports['out_hm']
        mid_hm.extend((s_ports['in']))
        self.connect_wires(mid_hm)

        vss_warrs = m_ports['VSS']
        vdd_warrs = m_ports['VDD']
        vss_warrs.extend(s_ports['VSS'])
        vdd_warrs.extend(s_ports['VDD'])

        clk = [s_ports['clk'], m_ports['clkb']]
        clkb = [s_ports['clkb'], m_ports['clk']]

        return {'VSS': vss_warrs,
                'VDD': vdd_warrs,
                'out': s_ports['out'],
                'out_hm': s_ports['out_hm'],
                'in': m_ports['in'],
                'clk': clk,
                'clkb': clkb,
                }

    @classmethod
    def connect_as_dummy(cls, template, inst):
        vss_vm = list(chain(inst.port_pins_iter('VSS_vm'), inst.port_pins_iter('in'),
                            inst.port_pins_iter('clkp')))
        vdd_vm = list(chain(inst.port_pins_iter('VDD_vm'), inst.port_pins_iter('clkn')))
        template.connect_wires(vss_vm)
        template.connect_wires(vdd_vm)


class DividerGroup(TemplateBase):
    """A column of clock dividers.

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
        dictionary of optional parameters.  See documentation of
        :class:`bag.layout.template.TemplateBase` for details.
    """

    def __init__(self, temp_db, lib_name, params, used_names, **kwargs):
        # type: (TemplateDB, str, Dict[str, Any], Set[str], **kwargs) -> None
        TemplateBase.__init__(self, temp_db, lib_name, params, used_names, **kwargs)
        self._sch_params = None
        self._fg_tot = None
        self._sa_clk_tidx = None

    @property
    def sch_params(self):
        # type: () -> Dict[str, Any]
        return self._sch_params

    @property
    def fg_tot(self):
        # type: () -> int
        return self._fg_tot

    @property
    def sa_clk_tidx(self):
        return self._sa_clk_tidx

    @classmethod
    def get_num_col(cls, seg_dict, abut_mode):
        seg_div = SinClkDivider.get_col_info(seg_dict, abut_mode)[0]
        seg_re = EnableRetimer.get_col_info(seg_dict, abut_mode)[0]
        return max(seg_div, seg_re)

    @classmethod
    def get_params_info(cls):
        # type: () -> Dict[str, str]
        return dict(
            config='laygo configuration dictionary.',
            lat_row_info='Latch row AnalogBase layout information dictionary.',
            seg_dict='Number of segments dictionary.',
            tr_widths='Track width dictionary.',
            tr_spaces='Track spacing dictionary.',
            div_tr_info='divider track information dictionary.',
            re_out_type='retimer output track type.',
            re_in_type='retimer input track type.',
            laygo_edgel='If not None, abut on left edge.',
            laygo_edger='If not None, abut on right edge.',
            clk_inverted='True if the clock tracks are inverted.',
            re_dummy='True to connect retimer as dummy.',
            fg_min='Minimum number of fingers.',
            show_pins='True to draw pin geometries.',
        )

    @classmethod
    def get_default_param_values(cls):
        # type: () -> Dict[str, Any]
        return dict(
            laygo_edgel=None,
            laygo_edger=None,
            clk_inverted=False,
            re_dummy=False,
            fg_min=0,
            show_pins=True,
        )

    def get_layout_basename(self):
        if self.params['re_dummy']:
            return 'divider_group_re_dummy'
        else:
            return 'divider_group'

    def draw_layout(self):
        config = self.params['config']
        lat_row_info = self.params['lat_row_info']
        seg_dict = self.params['seg_dict']
        tr_widths = self.params['tr_widths']
        tr_spaces = self.params['tr_spaces']
        div_tr_info = self.params['div_tr_info']
        re_out_type = self.params['re_out_type']
        re_in_type = self.params['re_in_type']
        laygo_edgel = self.params['laygo_edgel']
        laygo_edger = self.params['laygo_edger']
        clk_inverted = self.params['clk_inverted']
        re_dummy = self.params['re_dummy']
        fg_min = self.params['fg_min']
        show_pins = self.params['show_pins']

        # create masters
        end_mode = 12
        abut_mode = 0
        if laygo_edgel is not None:
            end_mode ^= 4
            abut_mode |= 1
        if laygo_edger is not None:
            end_mode ^= 8
            abut_mode |= 2

        params = dict(config=config, row_layout_info=lat_row_info, seg_dict=seg_dict,
                      tr_widths=tr_widths, tr_spaces=tr_spaces, tr_info=div_tr_info, fg_min=fg_min,
                      end_mode=end_mode, abut_mode=abut_mode, div_pos_edge=clk_inverted,
                      laygo_edgel=laygo_edgel, laygo_edger=laygo_edger, show_pins=False)
        re_master = self.new_template(params=params, temp_cls=EnableRetimer)
        params['fg_min'] = fg_min = re_master.fg_tot
        params['en3_htr_idx'] = re_master.en3_htr_tidx
        div_master = self.new_template(params=params, temp_cls=SinClkDivider)
        self._sa_clk_tidx = div_master.sa_clk_tidx

        self._fg_tot = fg_tot_div = div_master.fg_tot
        if fg_tot_div > fg_min:
            params['fg_min'] = fg_tot_div
            re_master = self.new_template(params=params, temp_cls=EnableRetimer)

        # set this template to use the same RoutingGrid as LaygoBase
        self.grid = re_master.grid.copy()

        # add instances
        ycur = re_master.bound_box.top_unit
        inst_re = self.add_instance(re_master, 'XRE', loc=(0, ycur), orient='MX', unit_mode=True)
        inst_div = self.add_instance(div_master, 'XDIV', loc=(0, ycur), unit_mode=True)

        # set size
        self.array_box = inst_re.array_box.merge(inst_div.array_box)
        bnd_box = inst_re.bound_box.merge(inst_div.bound_box)
        top_layer = div_master.conn_layer + 3
        self.set_size_from_bound_box(top_layer, bnd_box)

        # connect/export pins
        clkp = inst_re.get_all_port_pins('clkp')
        clkn = inst_re.get_all_port_pins('clkn')
        if re_dummy:
            clkp.extend(inst_re.port_pins_iter('VSS_vm'))
            clkp.append(inst_re.get_pin('in'))
            clkn.extend(inst_re.port_pins_iter('VDD_vm'))
            self.connect_wires(clkp)
            self.connect_wires(clkn)
            self.reexport(inst_div.get_port('en'), net_name='en2', show=show_pins)
            self.reexport(inst_div.get_port('clk'), net_name='clkp', show=show_pins)
            self.reexport(inst_div.get_port('clkb'), net_name='clkn', show=show_pins)
        else:
            self.connect_wires([inst_re.get_pin('en3'), inst_div.get_pin('en_vm')])

            # NOTE: we flip clkp/clkn tracks
            if clk_inverted:
                clkp_idx, clk_w = div_tr_info['clkp']
                clkn_idx, _ = div_tr_info['clkn']
            else:
                clkp_idx, clk_w = div_tr_info['clkn']
                clkn_idx, _ = div_tr_info['clkp']
            clkp_idx = inst_re.translate_master_track(top_layer, clkp_idx)
            clkn_idx = inst_re.translate_master_track(top_layer, clkn_idx)
            clkp, clkn = self.connect_differential_tracks(clkp, clkn, top_layer, clkp_idx,
                                                          clkn_idx, width=clk_w)
            self.add_pin('clkp', clkp, show=show_pins)
            self.add_pin('clkn', clkn, show=show_pins)
            self.add_pin('clkn', inst_div.get_pin('clk'), show=show_pins)
            self.add_pin('clkp', inst_div.get_pin('clkb'), show=show_pins)

            if re_out_type == 'in':
                out_idx1 = div_tr_info['inp'][0]
                out_idx2 = div_tr_info['inn'][0]
            else:
                out_idx1 = div_tr_info['outp'][0]
                out_idx2 = div_tr_info['outn'][0]
            out_idx1 = inst_re.translate_master_track(top_layer, out_idx1)
            out_idx2 = inst_re.translate_master_track(top_layer, out_idx2)
            out_idx = self.grid.get_middle_track(out_idx1, out_idx2)
            en2 = self.connect_to_tracks(inst_re.get_pin('en2'),
                                         TrackID(top_layer, out_idx, width=clk_w), min_len_mode=0)
            self.add_pin('en2', en2, show=show_pins)

            in_idx = inst_re.translate_master_track(top_layer, div_tr_info[re_in_type][0])
            in_pin = self.connect_to_tracks(inst_re.get_pin('in'), TrackID(top_layer, in_idx))
            self.add_pin('in', in_pin, show=show_pins)

        for name in ['scan_s', 'q', 'qb']:
            self.reexport(inst_div.get_port(name), show=show_pins)
        # export pins
        for name in ['VDD', 'VSS']:
            warrs = list(chain(inst_re.port_pins_iter(name), inst_div.port_pins_iter(name)))
            self.add_pin(name, warrs, label=name + ':', show=show_pins)

        # do max space fill
        for lay_id in range(1, top_layer):
            self.do_max_space_fill(lay_id)
        self.fill_box = self.bound_box

        div_sch_params = div_master.sch_params
        self._sch_params = dict(
            lch=div_sch_params['lch'],
            w_dict=div_sch_params['w_dict'],
            th_dict=div_sch_params['th_dict'],
            seg_div=div_sch_params['seg_dict'],
            seg_re=re_master.sch_params['seg_dict'],
            seg_buf=re_master.sch_params['seg_buf'],
            sr_params=div_sch_params['sr_params'],
        )


class SinClkDivider(LaygoBase):
    """A Sinusoidal clock divider using LaygoBase.

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
    **kwargs :
        dictionary of optional parameters.  See documentation of
        :class:`bag.layout.template.TemplateBase` for details.
    """

    def __init__(self, temp_db, lib_name, params, used_names, **kwargs):
        # type: (TemplateDB, str, Dict[str, Any], Set[str], **kwargs) -> None
        LaygoBase.__init__(self, temp_db, lib_name, params, used_names, **kwargs)
        self._sch_params = None
        self._fg_tot = None
        self._sa_clk_tidx = None

    @property
    def sch_params(self):
        # type: () -> Dict[str, Any]
        return self._sch_params

    @property
    def fg_tot(self):
        # type: () -> int
        return self._fg_tot

    @property
    def sa_clk_tidx(self):
        return self._sa_clk_tidx

    @classmethod
    def get_col_info(cls, seg_dict, abut_mode):
        # compute number of columns, then draw floorplan
        blk_sp = seg_dict['blk_sp']
        seg_inv = cls._get_gate_inv_info(seg_dict)
        seg_int = cls._get_integ_amp_info(seg_dict)
        seg_sr = cls._get_sr_latch_info(seg_dict)
        seg_nor = cls._get_nor_info(seg_dict)

        if abut_mode & 1 != 0:
            # abut on left
            inc_coll = blk_sp
        else:
            inc_coll = 0
        if abut_mode & 2 != 0:
            # abut on right
            inc_colr = blk_sp
        else:
            inc_colr = 0

        seg_tot = seg_inv + seg_int + seg_sr + seg_nor + 3 * blk_sp + inc_coll + inc_colr
        return seg_tot, blk_sp, seg_inv, seg_int, seg_sr, seg_nor, inc_coll, inc_colr

    @classmethod
    def get_params_info(cls):
        # type: () -> Dict[str, str]
        return dict(
            config='laygo configuration dictionary.',
            row_layout_info='The AnalogBase layout information dictionary.',
            seg_dict='Number of segments dictionary.',
            tr_widths='Track width dictionary.',
            tr_spaces='Track spacing dictionary.',
            en3_htr_idx='Enable3 half-track index.',
            tr_info='output track information dictionary.',
            fg_min='Minimum number of core fingers.',
            end_mode='The LaygoBase end_mode flag.',
            abut_mode='The left/right abut mode flag.',
            div_pos_edge='True to divider off of clkp.',
            show_pins='True to show pins.',
        )

    @classmethod
    def get_default_param_values(cls):
        # type: () -> Dict[str, Any]
        return dict(
            tr_info=None,
            fg_min=0,
            end_mode=None,
            abut_mode=0,
            div_pos_edge=True,
            show_pins=True,
        )

    def draw_layout(self):
        row_layout_info = self.params['row_layout_info']
        seg_dict = self.params['seg_dict'].copy()
        tr_widths = self.params['tr_widths']
        tr_spaces = self.params['tr_spaces']
        en3_htr_idx = self.params['en3_htr_idx']
        tr_info = self.params['tr_info']
        fg_min = self.params['fg_min']
        end_mode = self.params['end_mode']
        abut_mode = self.params['abut_mode']
        div_pos_edge = self.params['div_pos_edge']
        show_pins = self.params['show_pins']

        # compute number of columns
        tmp = self.get_col_info(seg_dict, abut_mode)
        seg_tot, blk_sp, seg_inv, seg_int, seg_sr, seg_nor, col_inv, inc_colr = tmp
        if fg_min > seg_tot:
            deltal = (fg_min - seg_tot) // 4 * 2
            col_inv += deltal
            inc_colr += (fg_min - seg_tot - col_inv)
            seg_tot = fg_min

        self._fg_tot = seg_tot
        self.set_rows_direct(row_layout_info, end_mode=end_mode, num_col=seg_tot)

        # draw individual blocks
        tr_manager = TrackManager(self.grid, tr_widths, tr_spaces, half_space=True)
        vss_w, vdd_w = _draw_substrate(self, col_inv, seg_tot, seg_tot - inc_colr - col_inv)
        col_int = col_inv + seg_inv + blk_sp
        col_sr = col_int + seg_int + blk_sp
        col_nor = col_sr + seg_sr + blk_sp
        inv_ports, inv_seg = self._draw_gate_inv(col_inv, seg_inv, seg_dict, tr_manager)
        int_ports, int_seg = self._draw_integ_amp(col_int, seg_int, seg_dict, tr_manager)
        sr_ports, xm_locs, sr_params = self._draw_sr_latch(col_sr, seg_sr, seg_dict, tr_manager,
                                                           en3_htr_idx, inv_ports)
        nor_ports, nor_seg = self._draw_nor(col_nor, seg_dict, tr_manager, inv_ports)

        # connect enable
        en = self.connect_to_track_wires([inv_ports['en'], sr_ports['pen']], int_ports['en'])
        en_vm = sr_ports['nen']
        self.add_pin('en_vm', en_vm, label='en', show=False)
        en.append(en_vm)
        en.append(nor_ports['en'])
        # connect inverters to integ amp
        clk = self.connect_to_track_wires(inv_ports['clk'], int_ports['clk'])
        mp = inv_ports['mp']
        mn = inv_ports['mn']
        tr_upper = mp.upper
        tr_w = mp.track_id.width
        mp_tid = mp.track_id.base_index
        mn_tid = mn.track_id.base_index
        self.connect_differential_tracks(int_ports['mp'], int_ports['mn'],
                                         mp.layer_id, mp_tid, mn_tid,
                                         width=tr_w, track_upper=tr_upper)

        # connect integ amp to sr latch
        self.connect_wires([int_ports['sb'], sr_ports['sb']])
        self.connect_wires([int_ports['rb'], sr_ports['rb']])

        # connect sr latch to inverters
        xm_layer = self.conn_layer + 3
        xm_w_q = tr_manager.get_width(xm_layer, 'div')

        # connect supply wires
        vss_list = [inv_ports['VSS'], int_ports['VSS'], sr_ports['VSS'], nor_ports['VSS']]
        vdd_list = [inv_ports['VDD'], int_ports['VDD'], sr_ports['VDD'], nor_ports['VDD']]
        vss_intv = self.get_track_interval(0, 'ds')
        vdd_intv = self.get_track_interval(self.num_rows - 1, 'ds')
        vss = _connect_supply(self, vss_w, vss_list, vss_intv, tr_manager, round_up=False,
                              exc_set={en3_htr_idx})
        vdd = _connect_supply(self, vdd_w, vdd_list, vdd_intv, tr_manager, round_up=True)

        # fill space
        self.fill_space()

        # add pins.  Connect to xm_layer if track information are given
        q_warrs = nor_ports['q']
        qb_warrs = nor_ports['qb']
        scan_s = sr_ports['scan_s']
        if tr_info is None:
            en_lbl = 'en:'
            q, qb = self.connect_differential_tracks(q_warrs, qb_warrs, xm_layer, xm_locs[1],
                                                     xm_locs[0], width=xm_w_q)
        else:
            en_lbl = 'en'
            q_idx, w_q = tr_info['q']
            qb_idx = tr_info['qb'][0]
            en_idx, w_en = tr_info['en']
            if div_pos_edge:
                clk_idx, w_clk = tr_info['clkp']
                clkb_idx = tr_info['clkn'][0]
            else:
                clk_idx, w_clk = tr_info['clkn']
                clkb_idx = tr_info['clkp'][0]
            vdd_idx, w_vdd = tr_info['VDD']
            vss_idx, w_vss = tr_info['VSS']
            s_idx = tr_manager.get_next_track(xm_layer, en_idx, w_en, 1, up=False)
            self._sa_clk_tidx = tr_manager.get_next_track(xm_layer, s_idx, 1, 'clk', up=False)

            q, qb = self.connect_differential_tracks(q_warrs, qb_warrs, xm_layer, q_idx, qb_idx,
                                                     width=w_q)
            en = self.connect_to_tracks(en, TrackID(xm_layer, en_idx))
            clk = self.connect_to_tracks(clk, TrackID(xm_layer, clk_idx, width=w_clk))
            vdd = self.connect_to_tracks(vdd, TrackID(xm_layer, vdd_idx, width=w_vdd))
            vss = self.connect_to_tracks(vss, TrackID(xm_layer, vss_idx, width=w_vss))
            scan_s = self.connect_to_tracks(scan_s, TrackID(xm_layer, s_idx), min_len_mode=0)
            # add fake port so we can match clock wires
            clkb = self.add_wires(xm_layer, clkb_idx, clk.lower_unit, clk.upper_unit, width=w_clk,
                                  unit_mode=True)
            self.add_pin('clkb', clkb, show=False)

        self.add_pin('q', q, show=show_pins)
        self.add_pin('qb', qb, show=show_pins)
        self.add_pin('en', en, label=en_lbl, show=show_pins)
        self.add_pin('clk', clk, show=show_pins)
        self.add_pin('VDD', vdd, show=show_pins)
        self.add_pin('VSS', vss, show=show_pins)
        self.add_pin('scan_s', scan_s, show=show_pins)

        # compute schematic parameters.
        n0_info = self.get_row_info(1)
        n1_info = self.get_row_info(2)
        n2_info = self.get_row_info(3)
        p0_info = self.get_row_info(4)
        p1_info = self.get_row_info(5)
        inv_seg.update(int_seg)
        inv_seg.update(nor_seg)
        self._sch_params = dict(
            lch=self.laygo_info.lch,
            w_dict=dict(
                n0=n0_info['w_max'],
                n1=n1_info['w_max'],
                n2=n2_info['w_max'],
                p0=p0_info['w_max'],
                p1=p1_info['w_max'],
            ),
            th_dict=dict(
                n0=n0_info['threshold'],
                n1=n1_info['threshold'],
                n2=n2_info['threshold'],
                p0=p0_info['threshold'],
                p1=p1_info['threshold'],
            ),
            seg_dict=inv_seg,
            sr_params=sr_params,
        )

    @classmethod
    def _get_gate_inv_info(cls, seg_dict):
        seg_pen = seg_dict['inv_pen']
        seg_inv = seg_dict['inv_inv']

        if seg_inv % 2 != 0:
            raise ValueError('This generator only works for even inv_inv.')
        if seg_pen % 4 != 2:
            raise ValueError('This generator only works for seg_pen = 2 mod 4.')

        return 2 * seg_inv + (seg_pen + 2)

    @classmethod
    def _get_integ_amp_info(cls, seg_dict):
        seg_rst = seg_dict['int_rst']
        seg_pen = seg_dict['int_pen']
        seg_in = seg_dict['int_in']

        if seg_rst % 2 != 0 or seg_pen % 2 != 0 or seg_in % 2 != 0:
            raise ValueError('This generator only works for even sr_inv/sr_drv/sr_sp.')

        return 2 * max(seg_in, seg_rst + seg_pen)

    @classmethod
    def _get_sr_latch_info(cls, seg_dict):
        seg_inv = seg_dict['sr_inv']
        seg_drv = seg_dict['sr_drv']
        seg_set = seg_dict['sr_set']
        seg_sp = seg_dict['sr_sp']
        seg_nand = seg_dict['sr_nand']

        if seg_inv % 2 != 0 or seg_drv % 2 != 0 or seg_sp % 2 != 0:
            raise ValueError('This generator only works for even sr_inv/sr_drv/sr_sp.')
        if seg_sp < 2:
            raise ValueError('sr_sp must be >= 2.')

        seg_nand_set = max(seg_nand * 2, seg_set)
        return (seg_inv + seg_drv + seg_sp + seg_nand_set) * 2

    @classmethod
    def _get_nor_info(cls, seg_dict):
        seg_inv = seg_dict['nor_inv']
        seg_pdrv = seg_dict['nor_pdrv']
        seg_ndrv = seg_dict['nor_ndrv']
        seg_set = seg_dict['nor_set']

        return seg_inv + max(seg_pdrv, seg_ndrv) * 2 + seg_set * 2

    def _draw_gate_inv(self, start, seg_tot, seg_dict, tr_manager):
        blk_sp = seg_dict['blk_sp']
        seg_pen = seg_dict['inv_pen']
        seg_inv = seg_dict['inv_inv']

        xleft = self.laygo_info.col_to_coord(start, unit_mode=True)
        xright = self.laygo_info.col_to_coord(start + seg_tot, unit_mode=True)

        col_inv = start + (seg_pen + 2) // 2
        ridx = 3
        ninvl = self.add_laygo_mos(ridx, col_inv, seg_inv)
        pinvl = self.add_laygo_mos(ridx + 1, col_inv, seg_inv)
        col_inv += seg_inv
        ninvr = self.add_laygo_mos(ridx, col_inv, seg_inv)
        pinvr = self.add_laygo_mos(ridx + 1, col_inv, seg_inv)
        pgate = self.add_laygo_mos(ridx + 2, start, seg_tot, gate_loc='s')

        # get track indices
        hm_layer = self.conn_layer + 1
        vm_layer = hm_layer + 1
        hm_w_in = tr_manager.get_width(hm_layer, 'in')
        hm_w_out = tr_manager.get_width(hm_layer, 'out')
        vm_w_in = tr_manager.get_width(vm_layer, 'in')
        in_start, in_stop = self.get_track_interval(3, 'g')
        nin_locs = tr_manager.spread_wires(hm_layer, ['in', 'in'], in_stop - in_start,
                                           'in', alignment=1, start_idx=in_start)

        # hacks
        # TODO: HACKS.  fix later
        nin_locs = [nin_locs[0] - 4.5, nin_locs[1] - 4.5]

        gb_idx0 = self.get_track_index(3, 'gb', 0)
        gb_idx1 = self.get_track_index(4, 'gb', 0)
        ntr = gb_idx1 - gb_idx0 + 1
        out_locs = tr_manager.spread_wires(hm_layer, [1, 'out', 1, 'out', 1], ntr,
                                           'out', alignment=0, start_idx=gb_idx0)
        pin_idx0 = self.get_track_index(4, 'g', -1)
        clk_idx = self.get_track_index(5, 'g', -1)
        en_idx = clk_idx + 1
        tleft = self.grid.coord_to_nearest_track(vm_layer, xleft, unit_mode=True, half_track=True,
                                                 mode=1)
        tright = self.grid.coord_to_nearest_track(vm_layer, xright, unit_mode=True, half_track=True,
                                                  mode=-1)
        ntr = tright - tleft + 1
        vin_locs = tr_manager.align_wires(vm_layer, ['in', 'in'], ntr, alignment=0, start_idx=tleft)
        xleft = self.laygo_info.col_to_coord(col_inv + seg_inv, unit_mode=True)
        xright = self.laygo_info.col_to_coord(start + seg_tot + blk_sp, unit_mode=True)
        tleft = self.grid.coord_to_nearest_track(vm_layer, xleft, unit_mode=True, half_track=True,
                                                 mode=1)
        tright = self.grid.coord_to_nearest_track(vm_layer, xright, unit_mode=True, half_track=True,
                                                  mode=-1)
        ntr = tright - tleft + 1
        vout_locs = tr_manager.align_wires(vm_layer, ['in', 'in'], ntr, alignment=0,
                                           start_idx=tleft)

        # connect pmos tail
        tid = self.make_track_id(5, 'gb', 0)
        self.connect_to_tracks([pinvl['s'], pinvr['s'], pgate['s']], tid)

        # connect outputs
        outp = [ninvr['d'], pinvr['d']]
        outn = [ninvl['d'], pinvl['d']]
        outp, outn = self.connect_differential_tracks(outp, outn, hm_layer, out_locs[3],
                                                      out_locs[1], width=hm_w_out)
        outp, outn = self.connect_differential_tracks(outp, outn, vm_layer, vout_locs[1],
                                                      vout_locs[0], width=vm_w_in)

        # connect inputs
        ninp, ninn = self.connect_differential_tracks(ninvl['g'], ninvr['g'], hm_layer, nin_locs[1],
                                                      nin_locs[0], width=hm_w_in)
        pinp, pinn = self.connect_differential_tracks(pinvl['g'], pinvr['g'], hm_layer, pin_idx0,
                                                      pin_idx0 + 1, width=hm_w_in)
        self.connect_differential_tracks([ninp, pinp], [ninn, pinn], vm_layer,
                                         vin_locs[0], vin_locs[1], width=vm_w_in)

        # connect enables and clocks
        num_en = (seg_pen + 2) // 4
        pgate_warrs = pgate['g'].to_warr_list()
        en_warrs = pgate_warrs[:num_en] + pgate_warrs[-num_en:]
        en = self.connect_to_tracks(en_warrs, TrackID(hm_layer, en_idx))
        clk_warrs = pgate_warrs[num_en:-num_en]
        clk = self.connect_to_tracks(clk_warrs, TrackID(hm_layer, clk_idx))

        ports = {'VDD': pgate['d'], 'VSS': [ninvl['s'], ninvr['s']],
                 'mp': outp, 'mn': outn,
                 'qb': ninp, 'q': ninn,
                 'en': en, 'clk': clk}

        inv_seg_dict = dict(
            inv_clk=2 * seg_inv + 2,
            inv_en=seg_pen,
            inv_inv=seg_inv,
        )
        return ports, inv_seg_dict

    def _draw_integ_amp(self, start, seg_tot, seg_dict, tr_manager):
        seg_rst = seg_dict['int_rst']
        seg_pen = seg_dict['int_pen']
        seg_in = seg_dict['int_in']

        xleft = self.laygo_info.col_to_coord(start + 1, unit_mode=True)
        xright = self.laygo_info.col_to_coord(start + seg_tot - 1, unit_mode=True)

        # place instances
        seg_single = seg_tot // 2
        ridx = 1
        nclk = self.add_laygo_mos(ridx, start, seg_tot)
        nen = self.add_laygo_mos(ridx + 1, start, seg_tot, gate_loc='s')
        col_l = start + seg_single - seg_in
        inl = self.add_laygo_mos(ridx + 2, col_l, seg_in)
        inr = self.add_laygo_mos(ridx + 2, col_l + seg_in, seg_in)
        ridx = 4
        col = start + seg_single - seg_rst - seg_pen
        penl = self.add_laygo_mos(ridx, col, seg_pen)
        col += seg_pen
        rstl = self.add_laygo_mos(ridx, col, seg_rst)
        col += seg_rst
        rstr = self.add_laygo_mos(ridx, col, seg_rst)
        col += seg_rst
        penr = self.add_laygo_mos(ridx, col, seg_pen)

        # get track locations
        hm_layer = self.conn_layer + 1
        vm_layer = hm_layer + 1
        hm_w_tail = tr_manager.get_width(hm_layer, 'tail')
        hm_w_in = tr_manager.get_width(hm_layer, 'in')
        hm_w_out = tr_manager.get_width(hm_layer, 'out')
        vm_w_out = tr_manager.get_width(vm_layer, 'out')
        vm_w_clk = tr_manager.get_width(vm_layer, 'clk')
        tail_off = tr_manager.place_wires(hm_layer, ['tail'])[1][0]
        in_start, in_stop = self.get_track_interval(3, 'g')
        in_locs = tr_manager.spread_wires(hm_layer, ['in', 'in'], in_stop - in_start,
                                          'in', alignment=1, start_idx=in_start)
        gb_idx0 = self.get_track_index(3, 'gb', 0)
        gb_idx1 = self.get_track_index(4, 'gb', 0)
        ntr = gb_idx1 - gb_idx0 + 1
        out_locs = tr_manager.spread_wires(hm_layer, [1, 'out', 1, 'out', 1], ntr,
                                           'out', alignment=0, start_idx=gb_idx0)
        pg_start = self.get_track_interval(4, 'g')[0]
        pg_locs = tr_manager.place_wires(hm_layer, [1, 1, 1, 1], start_idx=pg_start)[1]
        tleft = self.grid.coord_to_nearest_track(vm_layer, xleft, unit_mode=True, half_track=True,
                                                 mode=1)
        tright = self.grid.coord_to_nearest_track(vm_layer, xright, unit_mode=True, half_track=True,
                                                  mode=-1)
        ntr = tright - tleft + 1
        vm_locs = tr_manager.spread_wires(vm_layer, [1, 'out', 'clk', 'out', 1], ntr,
                                          'out', alignment=0, start_idx=tleft)

        # connect intermediate wires
        tidx = self.get_track_index(1, 'gb', 0)
        self.connect_to_tracks([nclk['d'], nen['d']],
                               TrackID(hm_layer, tidx + tail_off, width=hm_w_tail))
        tidx = self.get_track_index(2, 'gb', 0)
        self.connect_to_tracks([nen['s'], inl['s'], inr['s']],
                               TrackID(hm_layer, tidx + tail_off, width=hm_w_tail))

        # connect gate wires
        inp, inn = self.connect_differential_tracks(inl['g'], inr['g'], hm_layer, in_locs[1],
                                                    in_locs[0], width=hm_w_in)

        # connect enables
        en = self.connect_to_tracks(nen['g'], self.make_track_id(2, 'g', -1))
        enl = self.connect_to_tracks(penl['g'], TrackID(hm_layer, pg_locs[1]), min_len_mode=0)
        enr = self.connect_to_tracks(penr['g'], TrackID(hm_layer, pg_locs[1]), min_len_mode=0)
        enl = self.connect_to_tracks([en, enl], TrackID(vm_layer, vm_locs[0]))
        enr = self.connect_to_tracks([en, enr], TrackID(vm_layer, vm_locs[-1]))

        # connect clocks
        clk1 = self.connect_to_tracks(nclk['g'], self.make_track_id(1, 'g', -1))
        clk2 = self.connect_to_tracks([rstl['g'], rstr['g']], TrackID(hm_layer, pg_locs[0]))
        clk = self.connect_to_tracks([clk1, clk2], TrackID(vm_layer, vm_locs[2], width=vm_w_clk))

        # connect outputs
        outp = [inr['d'], rstr['d'], penr['d']]
        outn = [inl['d'], rstl['d'], penl['d']]
        outp, outn = self.connect_differential_tracks(outp, outn, hm_layer, out_locs[3],
                                                      out_locs[1], width=hm_w_out)
        outp, outn = self.connect_differential_tracks(outp, outn, vm_layer, vm_locs[1], vm_locs[3],
                                                      width=vm_w_out)
        outp, outn = self.connect_differential_tracks(outp, outn, hm_layer, pg_locs[3],
                                                      pg_locs[2], width=1)

        ports = {'VSS': nclk['s'], 'VDD': [penl['s'], rstl['s'], rstr['s'], penr['s']],
                 'mp': inp, 'mn': inn,
                 'sb': outn, 'rb': outp,
                 'en': [enl, enr], 'clk': clk}

        int_seg_dict = dict(
            int_clk=seg_tot,
            int_en=seg_tot,
            int_in=seg_in,
            int_pen=seg_pen,
            int_rst=seg_rst,
        )
        return ports, int_seg_dict

    def _draw_sr_latch(self, start, seg_tot, seg_dict, tr_manager, en_htr_idx, inv_ports):
        seg_nand = seg_dict['sr_nand']
        seg_set = seg_dict['sr_set']
        seg_sp = seg_dict['sr_sp']
        seg_inv = seg_dict['sr_inv']
        seg_drv = seg_dict['sr_drv']
        seg_pnor = seg_dict.get('sr_pnor', 1)
        seg_nnor = seg_dict.get('sr_nnor', 2)
        seg_sinv = seg_dict.get('sr_sinv', 2)
        fg_nand = seg_nand * 2

        if seg_set > seg_drv:
            raise ValueError('Must have sr_set <= sr_drv')
        if seg_pnor > seg_nand:
            raise ValueError('Must have sr_pnor <= sr_nand.')
        if seg_nnor % 2 == 1 or seg_sinv % 2 == 1:
            raise ValueError('sr_nnor and sr_sinv must be even.')

        # place instances
        stop = start + seg_tot
        ridx = 3
        cidx = start
        col_spl = cidx + seg_nand * 2 + 1
        col_norl = cidx
        nnandl = self.add_laygo_mos(ridx, cidx, seg_nand, gate_loc='s', stack=True)
        pnandl = self.add_laygo_mos(ridx + 1, cidx, seg_nand, gate_loc='s', stack=True)
        pnorl = self.add_laygo_mos(ridx + 2, cidx, seg_pnor, gate_loc='s', stack=True, flip=True)
        nnor1l = self.add_laygo_mos(ridx - 1, cidx, seg_nnor)
        nnor2l = self.add_laygo_mos(ridx - 1, cidx + seg_nnor, seg_nnor)
        cidx = stop - fg_nand
        col_spr = cidx - 1
        col_norr = cidx + seg_pnor
        nnandr = self.add_laygo_mos(ridx, cidx, seg_nand, gate_loc='s', stack=True, flip=True)
        pnandr = self.add_laygo_mos(ridx + 1, cidx, seg_nand, gate_loc='s', stack=True, flip=True)
        pnorr = self.add_laygo_mos(ridx + 2, cidx, seg_pnor, gate_loc='s', stack=True)
        nnor1r = self.add_laygo_mos(ridx - 1, cidx + fg_nand - seg_nnor, seg_nnor)
        nnor2r = self.add_laygo_mos(ridx - 1, cidx + fg_nand - 2 * seg_nnor, seg_nnor)
        psinv = self.add_laygo_mos(ridx + 2, cidx - 1, 1)
        start += fg_nand + seg_sp
        stop -= fg_nand + seg_sp

        ndrvl = self.add_laygo_mos(ridx, start, seg_drv)
        setl = self.add_laygo_mos(ridx - 1, start, seg_set)
        pdrvl = self.add_laygo_mos(ridx + 1, start, seg_drv)
        cidx = stop - seg_drv
        ndrvr = self.add_laygo_mos(ridx, cidx, seg_drv)
        setr = self.add_laygo_mos(ridx - 1, cidx + seg_drv - seg_set, seg_set)
        pdrvr = self.add_laygo_mos(ridx + 1, cidx, seg_drv)
        start += seg_drv
        stop -= seg_drv

        ninvl = self.add_laygo_mos(ridx, start, seg_inv)
        pinvl = self.add_laygo_mos(ridx + 1, start, seg_inv)
        cidx = stop - seg_inv
        ninvr = self.add_laygo_mos(ridx, cidx, seg_inv)
        pinvr = self.add_laygo_mos(ridx + 1, cidx, seg_inv)
        if seg_sinv % 4 == 0:
            start += seg_inv - seg_sinv // 2
        else:
            start += seg_inv - (seg_sinv + 2) // 2
        nsinv = self.add_laygo_mos(ridx - 1, start, seg_sinv)

        # compute track locations
        hm_layer = self.conn_layer + 1
        vm_layer = hm_layer + 1
        xm_layer = vm_layer + 1
        hm_w_in = tr_manager.get_width(hm_layer, 'in')
        hm_w_out = tr_manager.get_width(hm_layer, 'div')
        vm_w_out = tr_manager.get_width(vm_layer, 1)
        gb_idx0 = self.get_track_index(3, 'gb', 0)
        gb_idx1 = self.get_track_index(4, 'gb', 0)
        ntr = gb_idx1 - gb_idx0 + 1
        gb_locs = tr_manager.spread_wires(hm_layer, [1, 'div', 1, 'div', 1], ntr, 'div',
                                          alignment=0, start_idx=gb_idx0)
        ng_ntr, ng_locs = tr_manager.place_wires(hm_layer, ['in', 'in', 1, 1])
        ng_stop = self.get_track_interval(3, 'g')[1]
        ng_locs = [idx + ng_stop - ng_ntr for idx in ng_locs]
        pg_start = self.get_track_interval(4, 'g')[0]
        pg_locs = tr_manager.place_wires(hm_layer, [1, 1, 1, 1], start_idx=pg_start)[1]
        ng0_tid = TrackID(hm_layer, ng_locs[3])
        ng1_tid = TrackID(hm_layer, ng_locs[2])
        pg0_tid = TrackID(hm_layer, pg_locs[0])
        pg1_tid = TrackID(hm_layer, pg_locs[1])
        psg_tid = self.make_track_id(5, 'g', -1)
        pen_tid = TrackID(hm_layer, psg_tid.base_index + 1)
        pvdd_tid = self.make_track_id(5, 'gb', 0)
        psetg_tid = self.make_track_id(5, 'gb', 1)
        psetg_tid2 = self.make_track_id(5, 'gb', 2)

        xl = ndrvl['d'].get_bbox_array(self.grid).xc_unit
        xr = ndrvr['d'].get_bbox_array(self.grid).xc_unit
        vm_qb_idx = self.grid.coord_to_nearest_track(vm_layer, xl, half_track=True, mode=-1,
                                                     unit_mode=True)
        vm_q_idx = self.grid.coord_to_nearest_track(vm_layer, xr, half_track=True, mode=1,
                                                    unit_mode=True)
        vm_xc_idx = self.grid.get_middle_track(vm_q_idx, vm_qb_idx)
        vm_q_tid = TrackID(vm_layer, vm_q_idx, width=vm_w_out)
        vm_qb_tid = TrackID(vm_layer, vm_qb_idx, width=vm_w_out)
        xl = self.laygo_info.col_to_coord(col_spl, unit_mode=True)
        xr = self.laygo_info.col_to_coord(col_spr, unit_mode=True)
        vm_r_idx = self.grid.coord_to_nearest_track(vm_layer, xl, half_track=True, mode=-1,
                                                    unit_mode=True)
        vm_s_idx = self.grid.coord_to_nearest_track(vm_layer, xr, half_track=True, mode=1,
                                                    unit_mode=True)
        xl = self.laygo_info.col_to_coord(col_norl, unit_mode=True)
        xr = self.laygo_info.col_to_coord(col_norr, unit_mode=True)
        vm_ssb_idx = self.grid.coord_to_nearest_track(vm_layer, xl, half_track=True, mode=-1,
                                                      unit_mode=True)
        vm_ss_idx = self.grid.coord_to_nearest_track(vm_layer, xr, half_track=True, mode=1,
                                                     unit_mode=True)
        vm_r_tid = TrackID(vm_layer, vm_r_idx)
        vm_s_tid = TrackID(vm_layer, vm_s_idx)
        xl = ninvl['d'].get_bbox_array(self.grid).xc_unit
        xr = ninvr['d'].get_bbox_array(self.grid).xc_unit
        vm_sb_idx = self.grid.coord_to_nearest_track(vm_layer, xl, half_track=True, mode=-1,
                                                     unit_mode=True)
        vm_rb_idx = self.grid.coord_to_nearest_track(vm_layer, xr, half_track=True, mode=1,
                                                     unit_mode=True)

        ymid = self.grid.track_to_coord(hm_layer, gb_locs[2], unit_mode=True)
        xm_mid = self.grid.coord_to_nearest_track(xm_layer, ymid, half_track=True, mode=0,
                                                  unit_mode=True)
        xm_locs = tr_manager.place_wires(xm_layer, ['div', 'div'])[1]
        mid = self.grid.get_middle_track(xm_locs[0], xm_locs[1])
        xm_locs = [val + xm_mid - mid for val in xm_locs]

        # gather wires
        vss_list = [inst['s'] for inst in (ndrvl, ndrvr, ninvl, ninvr)]
        vdd_list = [inst['s'] for inst in (pdrvl, pdrvr, pinvl, pinvr)]
        q_list = self.connect_wires([inst['d'] for inst in (nnandl, pnandl, ndrvl, pdrvl)])
        qb_list = self.connect_wires([inst['d'] for inst in (nnandr, pnandr, ndrvr, pdrvr)])
        s_list = self.connect_wires([ninvr['d'], pinvr['d']])
        r_list = self.connect_wires([ninvl['d'], pinvl['d']])
        nor_vss_list = [nnor1l['s'], nnor2l['s'], nnor1r['s'], nnor2r['s']]
        nor_vss_list.extend(vss_list)
        nand_vss_list = [nnandl['s'], nnandr['s']]
        nand_vdd_list = [pnandl['s'], pnandr['s']]
        nand_vss_list.extend(vss_list)
        nand_vdd_list.extend(vdd_list)

        ports = {}
        # connect middle wires
        q_warr, qb_warr = self.connect_differential_tracks(q_list, qb_list, hm_layer, gb_locs[3],
                                                           gb_locs[1], width=hm_w_out)
        self.connect_to_tracks(nand_vss_list, TrackID(hm_layer, gb_locs[0]))
        self.connect_to_tracks(nand_vdd_list, TrackID(hm_layer, gb_locs[-1]))
        sr_tid = TrackID(hm_layer, gb_locs[2])
        s_warr = self.connect_to_tracks(s_list, sr_tid)
        r_warr = self.connect_to_tracks(r_list, sr_tid)

        # export vss/vdd
        ports['VSS'] = nor_vss_list
        ports['VDD'] = vdd_list

        # connect q/qb
        for name, vtid, ninst, pinst, sinst, warr, warr2 in \
                [('q', vm_q_tid, nnandr, pnandr, setr, q_warr, inv_ports['q']),
                 ('qb', vm_qb_tid, nnandl, pnandl, setl, qb_warr, inv_ports['qb'])]:
            ng = self.connect_to_tracks(ninst['g1'], ng1_tid)
            pg = self.connect_to_tracks(pinst['g1'], pg1_tid)
            sd = self.connect_to_tracks(sinst['d'], warr2.track_id)
            vm_warr = self.connect_to_tracks([warr2, warr, ng, pg, sd], vtid)
            ports[name] = vm_warr

        self.connect_differential_wires(inv_ports['q'], inv_ports['qb'], setr['d'], setl['d'])

        # connect s/r
        for vtid, ninst, pinst, warr in [(vm_r_tid, ndrvl, pnandl, r_warr),
                                         (vm_s_tid, ndrvr, pnandr, s_warr)]:
            ng = self.connect_to_tracks(ninst['g'], ng0_tid)
            pg = self.connect_to_tracks(pinst['g0'], pg0_tid)
            self.connect_to_tracks([warr, pg, ng], vtid)

        # connect sb/rb
        sbb, rbb = self.connect_differential_tracks([nnandl['g0'], ninvr['g']],
                                                    [nnandr['g0'], ninvl['g']], hm_layer,
                                                    ng_locs[0], ng_locs[1], width=hm_w_in)
        sbt, rbt = self.connect_differential_tracks([pdrvl['g'], pinvr['g']],
                                                    [pdrvr['g'], pinvl['g']], hm_layer,
                                                    pg_locs[2], pg_locs[3], width=1)
        self.connect_differential_tracks([sbb, sbt], [rbb, rbt], vm_layer,
                                         vm_sb_idx, vm_rb_idx)
        ports['sb'] = sbt
        ports['rb'] = rbt

        # connect bottom NMOS logic nets
        nnord_tid = nsinvd_tid = self.make_track_id(2, 'gb', 0)
        nsetg_tid = self.make_track_id(2, 'g', -1)
        nen_tid = TrackID(hm_layer, nsetg_tid.base_index - 1)
        nsgr_tid = TrackID(hm_layer, nen_tid.base_index - 1)
        nsgl_tid = TrackID(hm_layer, nsgr_tid.base_index - 1)

        scan_ns = self.connect_to_tracks([nsinv['g'], nnor1r['g']], nsgr_tid, min_len_mode=0)
        scan_sb_ng = self.connect_to_tracks(nnor1l['g'], nsgl_tid, min_len_mode=0)
        scan_sb_nd = self.connect_to_tracks(nsinv['d'], nsinvd_tid, min_len_mode=0)
        nen = self.connect_to_tracks([nnor2l['g'], nnor2r['g']], nen_tid)
        nen_tid = TrackID(vm_layer, en_htr_idx / 2)
        nen = self.connect_to_tracks(nen, nen_tid, min_len_mode=1)
        ports['nen'] = nen
        # connect top PMOS logic nets
        scan_ps = self.connect_to_tracks([psinv['g'], pnorr['g0']], psg_tid, min_len_mode=0)
        scan_sb_pg = self.connect_to_tracks(pnorl['g0'], psg_tid, min_len_mode=0)
        scan_sb_pd = self.connect_to_tracks(psinv['s'], psetg_tid, min_len_mode=-1)
        pvdd_list = [pnorl['s'], pnorr['s']]
        pvdd_list.extend(vdd_list)
        self.connect_to_tracks(pvdd_list, pvdd_tid)
        pen = self.connect_to_tracks([pnorl['g1'], pnorr['g1']], pen_tid)
        ports['pen'] = pen
        # connect logic nets to vm layer
        vm_mid_idx = self.grid.coord_to_nearest_track(vm_layer, scan_sb_nd.middle_unit,
                                                      half_track=True, mode=0, unit_mode=True)
        self.connect_to_tracks([scan_sb_ng, scan_sb_nd], TrackID(vm_layer, vm_mid_idx))
        self.connect_to_tracks([scan_sb_pg, scan_sb_ng], TrackID(vm_layer, vm_ssb_idx))
        self.connect_to_tracks([scan_sb_pg, scan_sb_pd], TrackID(vm_layer, vm_xc_idx))
        scan_s = self.connect_to_tracks([scan_ps, scan_ns], TrackID(vm_layer, vm_ss_idx))
        ports['scan_s'] = scan_s

        # connect override transistor gate
        nnordr = self.connect_to_tracks([nnor1r['d'], nnor2r['d']], nnord_tid, min_len_mode=-1)
        nnordl = self.connect_to_tracks([nnor1l['d'], nnor2l['d']], nnord_tid, min_len_mode=1)
        nsetgl = self.connect_to_tracks(setl['g'], nsetg_tid, min_len_mode=-1)
        nsetgr = self.connect_to_tracks(setr['g'], nsetg_tid, min_len_mode=1)
        psetgr = self.connect_to_tracks(pnorr['d'], psetg_tid2, min_len_mode=-1)
        psetgl = self.connect_to_tracks(pnorl['d'], psetg_tid, min_len_mode=1)
        self.connect_to_tracks([nnordl, nsetgl, psetgl], TrackID(vm_layer, vm_ssb_idx + 1))
        self.connect_to_tracks([nnordr, nsetgr, psetgr], TrackID(vm_layer, vm_ss_idx - 1))

        nlrow_info = self.get_row_info(1)
        srow_info = self.get_row_info(2)
        nrow_info = self.get_row_info(3)
        prow_info = self.get_row_info(4)
        plrow_info = self.get_row_info(5)

        sr_sch_params = dict(
            lch=self.laygo_info.lch,
            w_dict=dict(
                n=nrow_info['w_max'],
                nl=nlrow_info['w_max'],
                s=srow_info['w_max'],
                p=prow_info['w_max'],
                pl=plrow_info['w_max'],
            ),
            th_dict=dict(
                n=nrow_info['threshold'],
                nl=nlrow_info['threshold'],
                s=srow_info['threshold'],
                p=prow_info['threshold'],
                pl=plrow_info['threshold'],
            ),
            seg_dict=dict(
                nand=seg_nand,
                inv=seg_inv,
                drv=seg_drv,
                set=seg_set,
                pnor=seg_pnor,
                nnor=seg_nnor,
                nsinv=seg_sinv,
                psinv=1,
            )
        )

        return ports, xm_locs, sr_sch_params

    def _draw_nor(self, start, seg_dict, tr_manager, inv_ports):
        seg_inv = seg_dict['nor_inv']
        seg_pdrv = seg_dict['nor_pdrv']
        seg_ndrv = seg_dict['nor_ndrv']
        seg_set = seg_dict['nor_set']

        ridx = 3
        cur = start
        nsetl = self.add_laygo_mos(ridx, cur, seg_set)
        cur += seg_set
        ndrvl = self.add_laygo_mos(ridx, cur + seg_pdrv - seg_ndrv, seg_ndrv)
        pdrvl = self.add_laygo_mos(ridx + 1, cur, seg_pdrv)
        pen = self.add_laygo_mos(ridx + 2, cur, seg_pdrv * 2, gate_loc='s')
        cur += seg_pdrv
        col_mid = cur
        ndrvr = self.add_laygo_mos(ridx, cur, seg_ndrv)
        pdrvr = self.add_laygo_mos(ridx + 1, cur, seg_pdrv)
        cur += seg_pdrv
        nsetr = self.add_laygo_mos(ridx, cur, seg_set)
        cur += seg_set
        col_inv = cur
        ninv = self.add_laygo_mos(ridx, cur, seg_inv)
        pinv = self.add_laygo_mos(ridx + 1, cur, seg_inv)

        # get track locations
        hm_layer = self.conn_layer + 1
        vm_layer = hm_layer + 1
        foot_idx = self.get_track_index(5, 'gb', 0)
        ng_idx = self.get_track_index(3, 'g', -1)
        pg_idx = self.get_track_index(4, 'g', -1)
        nb_idx = self.get_track_index(3, 'gb', 0)
        pt_idx = self.get_track_index(4, 'gb', 0)
        mid_idx = self.grid.get_middle_track(nb_idx, pt_idx, round_up=True)
        mid_tid = TrackID(hm_layer, mid_idx)
        ng_tid = TrackID(hm_layer, ng_idx)
        pg_tid = TrackID(hm_layer, pg_idx)

        self.connect_to_tracks([pen['s'], pdrvl['s'], pdrvr['s']], TrackID(hm_layer, foot_idx))
        q = self.connect_to_tracks([nsetl['d'], ndrvl['d'], pdrvl['d']], mid_tid)
        qb = self.connect_to_tracks([nsetr['d'], ndrvr['d'], pdrvr['d']], mid_tid)
        ninp, ninn = self.connect_differential_wires(ndrvr['g'], ndrvl['g'],
                                                     inv_ports['q'], inv_ports['qb'])
        pinp, pinn = self.connect_differential_tracks(pdrvr['g'], pdrvl['g'], hm_layer,
                                                      pg_idx, pg_idx + 1.5)

        # input connection
        pidx = self.laygo_info.col_to_track(vm_layer, col_mid + 1)
        nidx = self.laygo_info.col_to_track(vm_layer, col_mid - 1)
        self.connect_differential_tracks([pinp, ninp], [pinn, ninn], vm_layer, pidx, nidx)

        # output connection
        out_pidx = nidx - seg_pdrv // 2
        out_nidx = pidx + seg_pdrv // 2
        tr_w = tr_manager.get_width(vm_layer, 'div')
        q = self.connect_to_tracks(q, TrackID(vm_layer, out_pidx, width=tr_w), min_len_mode=0)
        qb = self.connect_to_tracks(qb, TrackID(vm_layer, out_nidx, width=tr_w), min_len_mode=0)

        # reset connection
        nrst = self.connect_to_tracks([nsetl['g'], nsetr['g']], ng_tid)
        prst = self.connect_to_tracks(pen['g'], TrackID(hm_layer, self.get_track_index(5, 'g', -1)))
        orst = self.connect_to_tracks([ninv['d'], pinv['d']], TrackID(hm_layer, pt_idx))
        vm_idx = self.laygo_info.col_to_track(vm_layer, col_inv + 1)
        self.connect_to_tracks([nrst, prst, orst], TrackID(vm_layer, vm_idx))

        # enable connection
        vm_idx = self.laygo_info.col_to_track(vm_layer, col_inv + seg_inv - 1)
        peng = self.connect_to_tracks(pinv['g'], pg_tid)
        neng = self.connect_to_tracks(ninv['g'], TrackID(hm_layer, ng_idx - 1))
        en = self.connect_to_tracks([peng, neng], TrackID(vm_layer, vm_idx))

        ports = {'VSS': [ninv['s'], nsetl['s'], nsetr['s'], ndrvl['s'], ndrvr['s']],
                 'VDD': [pen['d'], pinv['s']],
                 'en': en,
                 'q': q,
                 'qb': qb,
                 }
        nor_seg = dict(nor_inv=seg_inv, nor_pdrv=seg_pdrv,
                       nor_ndrv=seg_ndrv, nor_set=seg_set, nor_pen=seg_pdrv * 2)
        return ports, nor_seg
