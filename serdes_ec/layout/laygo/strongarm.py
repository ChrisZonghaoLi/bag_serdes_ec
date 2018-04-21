# -*- coding: utf-8 -*-


from typing import TYPE_CHECKING, Dict, Any, Set

from bag.layout.routing import TrackID, TrackManager

from abs_templates_ec.laygo.core import LaygoBase

if TYPE_CHECKING:
    from bag.layout.template import TemplateDB


class SenseAmpStrongArm(LaygoBase):
    """A sense amplifier built from StrongArm latch and NAND gate SR latch.

    This design has no bridge switch, since we do not expect input to flip parity frequently
    during evaluation period.

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
        # type: (TemplateDB, str, Dict[str, Any], Set[str], **Any) -> None
        LaygoBase.__init__(self, temp_db, lib_name, params, used_names, **kwargs)
        self._sch_params = None

    @property
    def sch_params(self):
        # type: () -> Dict[str, Any]
        return self._sch_params

    @classmethod
    def get_params_info(cls):
        # type: () -> Dict[str, str]
        return dict(
            config='laygo configuration dictionary.',
            w_dict='width dictionary.',
            th_dict='threshold dictionary.',
            seg_dict='number of segments dictionary.',
            tr_widths='Track width dictionary.',
            tr_spaces='Track spacing dictionary.',
            top_layer='the top routing layer.',
            draw_boundaries='True to draw boundaries.',
            end_mode='Boundary end mode.',
            min_height='Minimum height.',
            show_pins='True to draw pin geometries.',
        )

    @classmethod
    def get_default_param_values(cls):
        # type: () -> Dict[str, Any]
        return dict(
            draw_boundaries=True,
            end_mode=None,
            min_height=0,
            show_pins=True,
        )

    def draw_layout(self):
        """Draw the layout of a dynamic latch chain.
        """
        w_dict = self.params['w_dict']
        th_dict = self.params['th_dict']
        seg_dict = self.params['seg_dict']
        tr_widths = self.params['tr_widths']
        tr_spaces = self.params['tr_spaces']
        top_layer = self.params['top_layer']
        draw_boundaries = self.params['draw_boundaries']
        end_mode = self.params['end_mode']
        min_height = self.params['min_height']
        show_pins = self.params['show_pins']

        n_in = seg_dict['in']
        n_tail = seg_dict['tail']
        n_ninv = seg_dict['ninv']
        n_pinv = seg_dict['pinv']
        n_rst = seg_dict['rst']
        n_dum = seg_dict['dum']
        n_nand = seg_dict['nand']
        n_nand_sp = 2

        # error checking
        for name, val in seg_dict.items():
            if val % 2 != 0 or val <= 0:
                raise ValueError('seg_%s = %d is not even or positive.' % (name, val))

        w_sub = self.params['config']['w_sub']
        w_tail = w_dict['tail']
        w_in = w_dict['in']
        w_ninv = w_dict['ninv']
        w_pinv = w_dict['pinv']

        th_tail = th_dict['tail']
        th_in = th_dict['in']
        th_ninv = th_dict['ninv']
        th_pinv = th_dict['pinv']

        tr_manager = TrackManager(self.grid, tr_widths, tr_spaces)

        # get row information
        row_list = ['ptap', 'nch', 'nch', 'nch', 'pch', 'ntap']
        orient_list = ['R0', 'R0', 'MX', 'MX', 'R0', 'MX']
        thres_list = [th_tail, th_tail, th_in, th_ninv, th_pinv, th_pinv]
        w_list = [w_sub, w_tail, w_in, w_ninv, w_pinv, w_sub]
        if end_mode is None:
            end_mode = 15 if draw_boundaries else 0

        # get track information
        wire_names = [
            dict(ds=['sup', 'sup'],),
            dict(g=['clk'], gb=['tail'],),
            dict(g=['in'], gb=['mid'],),
            dict(g=['nand', 'nand'], gb=['out'],),
            dict(g=['nand', 'nand'], gb=['out', 'mid'],),
            dict(ds=['sup', 'sup'],),
        ]

        # determine number of blocks
        laygo_info = self.laygo_info
        lch = laygo_info.lch
        hm_layer = self.conn_layer + 1
        ym_layer = hm_layer + 1
        # determine number of separation blocks needed for mid reset wires to be DRC clean
        tr_w_mid = tr_manager.get_width(hm_layer, 'mid')
        vm_w = self.grid.get_track_width(hm_layer - 1, 1, unit_mode=True)  # type: int
        mid_via_ext = self.grid.get_via_extensions(hm_layer - 1, 1, tr_w_mid,
                                                   unit_mode=True)[1]  # type: int
        mid_sp_le = self.grid.get_line_end_space(hm_layer, tr_w_mid, unit_mode=True)  # type: int
        n_sep = -(-(vm_w + mid_via_ext * 2 + mid_sp_le) // (2 * laygo_info.col_width)) * 2
        # determine total number of latch blocks
        n_ptot = n_pinv + 2 * n_rst
        n_ntot = max(n_ninv, n_in, n_tail)
        n_single = max(n_ptot, n_ntot)
        n_latch = n_sep + 2 * (n_single + n_dum)
        col_p = n_dum + n_single - n_ptot
        col_ninv = n_dum + n_single - n_ninv
        col_in = n_dum + n_single - n_in
        col_tail = n_dum + n_single - n_tail

        # find space between latch and nand gates from wire placement
        # step 1: find relative track index of clock
        clk_col = n_dum + n_single + n_sep // 2
        clk_ridx = laygo_info.col_to_nearest_rel_track(ym_layer, clk_col, half_track=True, mode=0)
        # step 2: find relative track index of outp
        op_col = col_ninv + n_ninv // 2
        op_ridx = laygo_info.col_to_nearest_rel_track(ym_layer, op_col, half_track=True, mode=-1)
        # make sure spacing between outp and clk is satisfied.
        op_ridx2 = tr_manager.get_next_track(ym_layer, clk_ridx, 'clk', 'out', up=False)
        op_ridx = min(op_ridx, op_ridx2)
        # step 3: find NAND outp relative track index
        num_ym_tracks, loc_ym = tr_manager.place_wires(ym_layer, ['out', 'out', 'mid',
                                                                  'nand', 'nand'])
        on_ridx = clk_ridx + (clk_ridx - op_ridx)
        nand_op_ridx = on_ridx + loc_ym[-1] - loc_ym[0]
        # step 4: find left NAND gate column index, then compute number of space columns
        col_nand = laygo_info.rel_track_to_nearest_col(ym_layer, nand_op_ridx, mode=1)
        n_sp = max(col_nand - n_latch - n_nand, 2)
        n_nand_tot = n_sp + 4 * n_nand + n_nand_sp
        n_tot = n_latch + n_nand_tot

        # specify row types
        self.set_row_types(row_list, w_list, orient_list, thres_list, draw_boundaries, end_mode,
                           top_layer=top_layer, num_col=n_tot, min_height=min_height,
                           tr_manager=tr_manager, wire_names=wire_names)

        # calculate clk/outp/outn vertical track indices
        clk_idx = laygo_info.col_to_track(ym_layer, clk_col)
        op_idx = laygo_info.col_to_track(ym_layer, op_col)
        op_idx2 = tr_manager.get_next_track(ym_layer, clk_idx, 'clk', 'out', up=False)
        op_idx = min(op_idx, op_idx2)
        on_idx = clk_idx + (clk_idx - op_idx)

        # add blocks
        ndum_list, pdum_list, dum_info_list = [], [], []

        # nwell tap
        cur_col, row_idx = 0, 5
        nw_tap = self.add_laygo_mos(row_idx, cur_col, n_tot)

        # pmos inverter row
        cur_col, row_idx = 0, 4
        pdum_list.append(self.add_laygo_mos(row_idx, cur_col, col_p))
        cur_col += col_p
        rst_midp = self.add_laygo_mos(row_idx, cur_col, n_rst)
        cur_col += n_rst
        rst_outp = self.add_laygo_mos(row_idx, cur_col, n_rst)
        cur_col += n_rst
        pinv_outp = self.add_laygo_mos(row_idx, cur_col, n_pinv)
        cur_col += n_pinv
        pdum_list.append(self.add_laygo_mos(row_idx, cur_col, n_sep))
        cur_col += n_sep
        pinv_outn = self.add_laygo_mos(row_idx, cur_col, n_pinv)
        cur_col += n_pinv
        rst_outn = self.add_laygo_mos(row_idx, cur_col, n_rst)
        cur_col += n_rst
        rst_midn = self.add_laygo_mos(row_idx, cur_col, n_rst)
        cur_col += n_rst
        pdum_list.append(self.add_laygo_mos(row_idx, cur_col, col_p))
        cur_col += col_p + n_sp
        nandpl = self.add_laygo_mos(row_idx, cur_col, n_nand * 2, gate_loc='s')
        cur_col += n_nand * 2 + n_nand_sp
        nandpr = self.add_laygo_mos(row_idx, cur_col, n_nand * 2, gate_loc='s')
        dum_info_list.append((('pch', w_pinv, lch, th_pinv, '', ''), 2 * col_p + n_sep))

        # nmos inverter row
        cur_col, row_idx = 0, 3
        cur_col = self._draw_nedge_dummy(row_idx, cur_col, col_ninv, ndum_list, left=True)
        ninv_outp = self.add_laygo_mos(row_idx, cur_col, n_ninv)
        cur_col += n_ninv
        cur_col = self._draw_nsep_dummy(row_idx, cur_col, n_sep, ndum_list)
        ninv_outn = self.add_laygo_mos(row_idx, cur_col, n_ninv)
        cur_col += n_ninv
        cur_col = self._draw_nedge_dummy(row_idx, cur_col, col_ninv, ndum_list, left=False)
        cur_col += n_sp
        nandnl = self.add_laygo_mos(row_idx, cur_col, n_nand, stack=True, gate_loc='s')
        cur_col += n_nand * 2 + n_nand_sp
        nandnr = self.add_laygo_mos(row_idx, cur_col, n_nand, stack=True, gate_loc='s')
        dum_info_list.append((('nch', w_ninv, lch, th_ninv, '', ''), 2 * col_ninv + n_sep - 4))
        dum_info_list.append((('nch', w_ninv, lch, th_ninv, '', 'intp'), 2))
        dum_info_list.append((('nch', w_ninv, lch, th_ninv, '', 'intn'), 2))

        # nmos input row
        cur_col, row_idx = 0, 2
        cur_col = self._draw_nedge_dummy(row_idx, cur_col, col_in, ndum_list, left=True)
        inn = self.add_laygo_mos(row_idx, cur_col, n_in)
        cur_col += n_in
        cur_col = self._draw_nsep_dummy(row_idx, cur_col, n_sep, ndum_list)
        inp = self.add_laygo_mos(row_idx, cur_col, n_in)
        cur_col += n_in
        ndum = n_tot - cur_col
        self._draw_nedge_dummy(row_idx, cur_col, ndum, ndum_list, left=False)
        dum_info_list.append((('nch', w_in, lch, th_in, '', ''), col_in + ndum + n_sep - 4))
        dum_info_list.append((('nch', w_in, lch, th_in, '', 'intp'), 2))
        dum_info_list.append((('nch', w_in, lch, th_in, '', 'intn'), 2))

        # nmos tail row
        cur_col, row_idx = 0, 1
        ndum_list.append((self.add_laygo_mos(row_idx, cur_col, col_tail), 0))
        cur_col += col_tail
        tailn = self.add_laygo_mos(row_idx, cur_col, n_tail)
        cur_col += n_tail
        ndum_list.append((self.add_laygo_mos(row_idx, cur_col, n_sep), 0))
        cur_col += n_sep
        tailp = self.add_laygo_mos(row_idx, cur_col, n_tail)
        cur_col += n_tail
        ndum = n_tot - cur_col
        ndum_list.append((self.add_laygo_mos(row_idx, cur_col, ndum), 0))
        dum_info_list.append((('nch', w_tail, lch, th_tail, '', ''), col_in + ndum + n_sep))

        # pwell tap
        cur_col, row_idx = 0, 0
        pw_tap = self.add_laygo_mos(row_idx, cur_col, n_tot)

        # fill dummy
        self.fill_space()

        # connect ground
        vss_s = [pw_tap['VSS_s'], tailn['s'], tailp['s'], nandnl['s'], nandnr['s']]
        vss_d = [pw_tap['VSS_d']]
        for inst, mode in ndum_list:
            if mode == 0:
                vss_s.append(inst['s'])
            vss_d.append(inst['d'])
            vss_d.append(inst['g'])

        vss_s_tid = self.get_wire_id(0, 'ds', wire_idx=0)
        vss_d_tid = self.get_wire_id(0, 'ds', wire_idx=1)
        vss_s_warrs = self.connect_to_tracks(vss_s, vss_s_tid)
        vss_d_warrs = self.connect_to_tracks(vss_d, vss_d_tid)
        self.add_pin('VSS', vss_s_warrs, label='VSS:', show=show_pins)
        self.add_pin('VSS', vss_d_warrs, label='VSS:', show=show_pins)

        # connect tail
        tail = [tailp['d'], tailn['d'], inp['d'], inn['d']]
        tail_tid = self.get_wire_id(1, 'gb', wire_idx=0)
        self.connect_to_tracks(tail, tail_tid)

        # connect tail clk
        tclk_tid = self.get_wire_id(1, 'g', wire_idx=0)
        clk_list = [self.connect_to_tracks([tailp['g'], tailn['g']], tclk_tid)]

        # connect inputs
        in_tid = self.get_wire_id(2, 'g', wire_idx=0)
        inp_warr = self.connect_to_tracks(inp['g'], in_tid, min_len_mode=0)
        inn_warr = self.connect_to_tracks(inn['g'], in_tid, min_len_mode=0)
        self.add_pin('inp', inp_warr, show=show_pins)
        self.add_pin('inn', inn_warr, show=show_pins)

        # get output/mid horizontal track id
        nout_tid = self.get_wire_id(3, 'gb', wire_idx=0)
        mid_tid = self.get_wire_id(2, 'gb', wire_idx=0)
        # connect nmos mid
        nmidp = [inn['s'], ninv_outp['s']]
        nmidn = [inp['s'], ninv_outn['s']]
        nmidp = self.connect_to_tracks(nmidp, mid_tid)
        nmidn = self.connect_to_tracks(nmidn, mid_tid)

        # connect pmos mid
        mid_tid = self.get_wire_id(4, 'gb', wire_name='mid')
        pmidp = self.connect_to_tracks(rst_midp['d'], mid_tid, min_len_mode=-1)
        pmidn = self.connect_to_tracks(rst_midn['d'], mid_tid, min_len_mode=1)

        # connect nmos output
        noutp = self.connect_to_tracks(ninv_outp['d'], nout_tid, min_len_mode=0)
        noutn = self.connect_to_tracks(ninv_outn['d'], nout_tid, min_len_mode=0)

        # connect pmos output
        pout_tid = self.get_wire_id(4, 'gb', wire_name='out')
        poutp = [pinv_outp['d'], rst_outp['d']]
        poutn = [pinv_outn['d'], rst_outn['d']]
        poutp = self.connect_to_tracks(poutp, pout_tid)
        poutn = self.connect_to_tracks(poutn, pout_tid)

        # connect clock in inverter row
        pclk = [rst_midp['g'], rst_midn['g'], rst_outp['g'], rst_outn['g']]
        pclk_tid = self.get_wire_id(4, 'g', wire_idx=0)
        clk_list.append(self.connect_to_tracks(pclk, pclk_tid))

        # connect inverter gate
        invg_tid = self.get_wire_id(3, 'g', wire_idx=1)
        invgp = self.connect_to_tracks([ninv_outp['g'], pinv_outp['g']], invg_tid)
        invgn = self.connect_to_tracks([ninv_outn['g'], pinv_outn['g']], invg_tid)

        # connect vdd
        vdd_s = [nw_tap['VDD_s'], pinv_outp['s'], pinv_outn['s'], rst_midp['s'],
                 rst_midn['s'], nandpl['s'], nandpr['s']]
        vdd_d = [nw_tap['VDD_d']]
        for inst in pdum_list:
            vdd_d.append(inst['d'])
            vdd_d.append(inst['g'])
            vdd_s.append(inst['s'])
        vdd_d_tid = self.get_wire_id(5, 'ds', wire_idx=0)
        vdd_s_tid = self.get_wire_id(5, 'ds', wire_idx=1)
        self.add_pin('VDD', self.connect_to_tracks(vdd_s, vdd_s_tid), show=show_pins)
        self.add_pin('VDD', self.connect_to_tracks(vdd_d, vdd_d_tid), show=show_pins)

        # connect nand
        nand_gbl_tid = self.get_wire_id(3, 'g', wire_idx=0)
        nand_gtl_tid = self.get_wire_id(3, 'g', wire_idx=1)
        nand_gtr_tid = self.get_wire_id(4, 'g', wire_idx=0)
        nand_gbr_tid = self.get_wire_id(4, 'g', wire_idx=1)
        nand_nmos_out_tid = self.get_wire_id(3, 'gb', wire_idx=0)
        nand_outnl = self.connect_to_tracks(nandnl['d'], nand_nmos_out_tid, min_len_mode=0)
        nand_outnr = self.connect_to_tracks(nandnr['d'], nand_nmos_out_tid, min_len_mode=0)

        nand_gtl = [nandnl['g1'], nandpl['g1'], nandpr['d']]
        nand_gtr = [nandnr['g1'], nandpr['g1'], nandpl['d']]
        tr_w = nand_gtr_tid.width
        pidx = nand_gtr_tid.base_index
        nidx = nand_gtl_tid.base_index
        nand_outpl, nand_outpr = self.connect_differential_tracks(nand_gtr, nand_gtl, hm_layer,
                                                                  pidx, nidx, width=tr_w)
        nand_gbl = self.connect_to_tracks([nandnl['g0'], nandpl['g0']], nand_gbl_tid)
        nand_gbr = self.connect_to_tracks([nandnr['g0'], nandpr['g0']], nand_gbr_tid)

        # connect nand ym wires
        tr_w_nand_y = tr_manager.get_width(ym_layer, 'nand')
        nand_outl_id = self.grid.coord_to_nearest_track(ym_layer, nand_outnl.middle,
                                                        half_track=True, mode=1)
        nand_outr_id = self.grid.coord_to_nearest_track(ym_layer, nand_outnr.middle,
                                                        half_track=True, mode=-1)
        nand_gbr_yt = self.grid.get_wire_bounds(hm_layer, nand_gbr_tid.base_index,
                                                unit_mode=True)[1]
        ym_via_ext = self.grid.get_via_extensions(hm_layer, 1, 1, unit_mode=True)[1]
        out_upper = nand_gbr_yt + ym_via_ext
        nand_outl, nand_outr = self.connect_differential_tracks(nand_outpl, nand_outpr, ym_layer,
                                                                nand_outl_id, nand_outr_id,
                                                                track_upper=out_upper,
                                                                width=tr_w_nand_y, unit_mode=True)
        nand_outl = self.connect_to_tracks(nand_outnl, nand_outl.track_id,
                                           track_upper=out_upper, unit_mode=True)
        nand_outr = self.connect_to_tracks(nand_outnr, nand_outr.track_id,
                                           track_upper=out_upper, unit_mode=True)
        self.add_pin('outp', nand_outl, show=show_pins)
        self.add_pin('outn', nand_outr, show=show_pins)

        sp_nand_ym = tr_manager.get_space(ym_layer, ('nand', 'nand')) + tr_w_nand_y
        nand_inn_tid = nand_outl_id - sp_nand_ym
        nand_inp_tid = nand_outr_id + sp_nand_ym
        self.connect_differential_tracks(nand_gbl, nand_gbr, ym_layer, nand_inn_tid,
                                         nand_inp_tid, width=tr_w_nand_y)

        # connect ym wires
        clk_tid = TrackID(ym_layer, clk_idx, width=tr_manager.get_width(ym_layer, 'clk'))
        clk_warr = self.connect_to_tracks(clk_list, clk_tid)
        self.add_pin('clk', clk_warr, show=show_pins)

        tr_w_out_ym = tr_manager.get_width(ym_layer, 'out')
        sp_out_ym = tr_manager.get_space(ym_layer, ('out', 'out')) + tr_w_out_ym
        op_tid = TrackID(ym_layer, op_idx, width=tr_w_out_ym)
        outp1 = self.connect_to_tracks([poutp, noutp], op_tid)
        on_tid = TrackID(ym_layer, on_idx, width=tr_w_out_ym)
        outn1 = self.connect_to_tracks([poutn, noutn], on_tid)
        op_tid = TrackID(ym_layer, on_idx + sp_out_ym, width=tr_w_out_ym)
        on_tid = TrackID(ym_layer, op_idx - sp_out_ym, width=tr_w_out_ym)
        outp2 = self.connect_to_tracks(invgn, op_tid)
        outn2 = self.connect_to_tracks(invgp, on_tid)

        tr_w_mid_ym = tr_manager.get_width(ym_layer, 'mid')
        sp_om_y = tr_manager.get_space(ym_layer, ('out', 'mid'))
        sp_out_mid = sp_out_ym + sp_om_y + (tr_w_mid_ym + tr_w_out_ym) / 2
        mn_tid = TrackID(ym_layer, on_idx + sp_out_mid, width=tr_w_mid_ym)
        mp_tid = TrackID(ym_layer, op_idx - sp_out_mid, width=tr_w_mid_ym)
        self.connect_to_tracks([nmidn, pmidn], mn_tid)
        self.connect_to_tracks([nmidp, pmidp], mp_tid)

        xm_layer = ym_layer + 1
        om_idx = self.grid.coord_to_nearest_track(xm_layer, outp1.middle, half_track=True)
        _, loc_xm_out = tr_manager.place_wires(xm_layer, ['out', 'out'])
        out_mid_idx = (loc_xm_out[0] + loc_xm_out[1]) / 2
        outp_idx = loc_xm_out[1] + om_idx - out_mid_idx
        outn_idx = loc_xm_out[0] + om_idx - out_mid_idx
        tr_w_out_xm = tr_manager.get_width(xm_layer, 'out')
        outp, outn = self.connect_differential_tracks([outp1, outp2], [outn1, outn2], xm_layer,
                                                      outp_idx, outn_idx, width=tr_w_out_xm)
        self.add_pin('midp', outp, show=show_pins)
        self.add_pin('midn', outn, show=show_pins)
        self.connect_differential_tracks(outn, outp, ym_layer, nand_inn_tid, nand_inp_tid,
                                         width=tr_w_nand_y)

        # set schematic parameters
        self._sch_params = dict(
            lch=self.params['config']['lch'],
            w_dict=w_dict,
            th_dict=th_dict,
            seg_dict=seg_dict,
            dum_info=dum_info_list,
        )

    def _draw_nsep_dummy(self, row_idx, cur_col, n_sep, ndum_list):
        ndum_list.append((self.add_laygo_mos(row_idx, cur_col, 2), 1))
        cur_col += 2
        if n_sep > 4:
            ndum_list.append((self.add_laygo_mos(row_idx, cur_col, n_sep - 4), 0))
            cur_col += n_sep - 4
        if n_sep >= 4:
            ndum_list.append((self.add_laygo_mos(row_idx, cur_col, 2), 1))
            cur_col += 2

        return cur_col

    def _draw_nedge_dummy(self, row_idx, cur_col, n_dum, ndum_list, left=True):
        if left:
            info = [(n_dum - 2, 0), (2, 1)]
        else:
            info = [(2, 1), (n_dum - 2, 0)]

        for seg, mode in info:
            ndum_list.append((self.add_laygo_mos(row_idx, cur_col, seg), mode))
            cur_col += seg
        return cur_col
