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


from typing import Dict, Any, Set


from bag.layout.routing import TrackID, TrackManager
from bag.layout.template import TemplateDB

from abs_templates_ec.laygo.core import LaygoBase


class StrongArmLatch(LaygoBase):
    """A StrongArm latch with simple cross-couple NAND gate as SR latch`12.

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
        super(StrongArmLatch, self).__init__(temp_db, lib_name, params, used_names, **kwargs)

    @classmethod
    def get_params_info(cls):
        """Returns a dictionary containing parameter descriptions.

        Override this method to return a dictionary from parameter names to descriptions.

        Returns
        -------
        param_info : dict[str, str]
            dictionary from parameter name to description.
        """
        return dict(
            config='laygo configuration dictionary.',
            w_dict='width dictionary.',
            th_dict='threshold dictionary.',
            num_dict='number of blocks dictionary.',
            tr_widths='Track width dictionary.',
            tr_spaces='Track spacing dictionary.',
            draw_boundaries='True to draw boundaries.',
            top_layer='the top routing layer.',
            show_pins='True to draw pin geometries.',
        )

    def draw_layout(self):
        """Draw the layout of a dynamic latch chain.
        """

        w_dict = self.params['w_dict']
        th_dict = self.params['th_dict']
        num_dict = self.params['num_dict']
        tr_widths = self.params['tr_widths']
        tr_spaces = self.params['tr_spaces']
        draw_boundaries = self.params['draw_boundaries']
        top_layer = self.params['top_layer']
        show_pins = self.params['show_pins']

        w_sub = self.params['config']['w_sub']

        n_in = num_dict['in']
        n_tail = num_dict['tail']
        n_invn = num_dict['invn']
        n_invp = num_dict['invp']
        n_rst = num_dict['rst']
        n_dum = num_dict['dum']
        n_nand = num_dict['nand']
        n_nand_sp = 1

        w_tail = w_dict['tail']
        w_in = w_dict['in']
        w_invn = w_dict['invn']
        w_invp = w_dict['invp']

        th_tail = th_dict['tail']
        th_in = th_dict['in']
        th_invn = th_dict['invn']
        th_invp = th_dict['invp']

        # error checking
        if n_nand % 2 != 0 or n_nand <= 0:
            raise ValueError('num_nand_blk must be even and positive.')

        tr_manager = TrackManager(self.grid, tr_widths, tr_spaces)

        # get row information
        row_list = ['ptap', 'nch', 'nch', 'nch', 'pch', 'ntap']
        orient_list = ['R0', 'R0', 'MX', 'MX', 'R0', 'MX']
        thres_list = [th_tail, th_tail, th_in, th_invn, th_invp, th_invp]
        w_list = [w_sub, w_tail, w_in, w_invn, w_invp, w_sub]
        row_kwargs = [{}] * 6
        end_mode = 15 if draw_boundaries else 0

        # get track information
        hm_layer = self.conn_layer + 1
        tr_w_clk = tr_manager.get_width(hm_layer, 'clk')
        tr_w_tail = tr_manager.get_width(hm_layer, 'tail')
        tr_w_in = tr_manager.get_width(hm_layer, 'in')
        tr_w_out = tr_manager.get_width(hm_layer, 'out')
        tr_w_mid = tr_manager.get_width(hm_layer, 'mid')
        tr_w_sup = tr_manager.get_width(hm_layer, 'sup')
        tr_w_nand = tr_manager.get_width(hm_layer, 'nand')

        num_g_tail, loc_g_tail = tr_manager.place_wires(hm_layer, ['clk'])
        num_g_in, loc_g_in = tr_manager.place_wires(hm_layer, ['in'])
        num_g_invn1, loc_g_invn1 = tr_manager.place_wires(hm_layer, ['out'])
        num_g_invp1, loc_g_invp1 = tr_manager.place_wires(hm_layer, ['clk'])
        num_g_inv2, _ = tr_manager.place_wires(hm_layer, ['nand', 'nand'])
        num_g_invn = max(num_g_invn1, num_g_inv2)
        num_g_invp = max(num_g_invp1, num_g_inv2)
        _, loc_g_invn = tr_manager.place_wires(hm_layer, ['out'], start_idx=num_g_invn - num_g_invn1)
        _, loc_g_invp = tr_manager.place_wires(hm_layer, ['clk'], start_idx=num_g_invp - num_g_invp1)
        _, loc_g_invn2 = tr_manager.place_wires(hm_layer, ['nand', 'nand'], start_idx=num_g_invn - num_g_inv2)
        _, loc_g_invp2 = tr_manager.place_wires(hm_layer, ['nand', 'nand'], start_idx=num_g_invp - num_g_inv2)

        num_gb_tail, loc_gb_tail = tr_manager.place_wires(hm_layer, ['tail'])
        num_gb_in, loc_gb_in = tr_manager.place_wires(hm_layer, ['mid'])
        num_gb_invn, loc_gb_invn = tr_manager.place_wires(hm_layer, ['out'])
        num_gb_invp, loc_gb_invp = tr_manager.place_wires(hm_layer, ['out', 'mid'])

        num_ds_sub, loc_ds_sub = tr_manager.place_wires(hm_layer, ['sup', 'sup'])

        num_g_tracks = [0, num_g_tail, num_g_in, num_g_invn, num_g_invp, 0]
        num_gb_tracks = [0, num_gb_tail, num_gb_in, num_gb_invn, num_gb_invp, 0]
        num_ds_tracks = [num_ds_sub, 0, 0, 0, 0, num_ds_sub]

        # determine number of blocks
        laygo_info = self.laygo_info
        ym_layer = hm_layer + 1
        # determine total number of latch blocks
        n_sep = 1
        n_ptot = n_invp + 2 * n_rst
        n_ntot = max(n_invn, n_in, n_tail)
        n_single = max(n_ptot, n_ntot)
        n_latch = n_sep + 2 * (n_single + n_dum)
        col_p = n_dum + n_single - n_ptot
        col_invn = n_dum + n_single - n_invn
        col_in = n_dum + n_single - n_in
        col_tail = n_dum + n_single - n_tail

        if n_invn % 2 == 1:
            outp_ds_type = 'd'
            outp_mid_col = col_invn + (n_invn - 1) // 2
        else:
            outp_ds_type = 's'
            outp_mid_col = n_invn + n_invn // 2

        # iterate to find total number of nand blocks
        num_ym_tracks, loc_ym = tr_manager.place_wires(ym_layer, ['out', 'out', 'mid', 'nand', 'nand'])

        n_nand_prev = -1
        n_nand_tot = 0
        n_sp = 0
        clk_idx, op_idx, on_idx = -1, -1, -1
        while n_nand_tot != n_nand_prev:
            n_nand_prev = n_nand_tot
            laygo_info.set_num_col(n_latch + n_nand_tot)

            # compute ym wire indices
            if n_sep % 2 == 1:
                x_latch_mid = laygo_info.col_to_coord(n_dum + n_single + (n_sep + 1) // 2, 'd', unit_mode=True)
            else:
                x_latch_mid = laygo_info.col_to_coord(n_dum + n_single + n_sep // 2, 's', unit_mode=True)

            clk_idx = self.grid.coord_to_nearest_track(ym_layer, x_latch_mid, half_track=True,
                                                       mode=1, unit_mode=True)

            # compute NAND gate location
            x_outp_mid = laygo_info.col_to_coord(outp_mid_col, outp_ds_type, unit_mode=True)
            op_idx = self.grid.coord_to_nearest_track(ym_layer, x_outp_mid, half_track=True,
                                                      mode=1, unit_mode=True)
            op_idx = min(op_idx, clk_idx - tr_manager.get_space(ym_layer, ('clk', 'out')))
            on_idx = clk_idx + (clk_idx - op_idx)
            nand_op_idx = on_idx + loc_ym[-1] - loc_ym[0]
            nand_op_x = self.grid.track_to_coord(ym_layer, nand_op_idx, unit_mode=True)
            # based on nand outp track index, compute nand gate column index.
            col_nand, _ = laygo_info.coord_to_nearest_col(nand_op_x, ds_type='d', mode=1, unit_mode=True)

            n_sp = col_nand - n_latch - n_nand // 2
            n_nand_tot = n_sp + 2 * n_nand + n_nand_sp

        n_tot = n_latch + n_nand_tot

        # specify row types
        self.set_row_types(row_list, w_list, orient_list, thres_list, draw_boundaries, end_mode,
                           num_g_tracks, num_gb_tracks, num_ds_tracks, guard_ring_nf=0,
                           top_layer=top_layer, row_kwargs=row_kwargs, num_col=n_tot)

        # add blocks
        ndum_list, pdum_list = [], []
        blk_type = 'fg2d'

        # nwell tap
        cur_col, row_idx = 0, 5
        nw_tap = self.add_laygo_primitive('sub', loc=(cur_col, row_idx), nx=n_tot, spx=1)

        # pmos inverter row
        cur_col, row_idx = 0, 4
        pdum_list.append((self.add_laygo_primitive(blk_type, loc=(cur_col, row_idx), nx=col_p, spx=1), 0))
        cur_col += col_p
        rst_midp = self.add_laygo_primitive(blk_type, loc=(cur_col, row_idx), nx=n_rst, spx=1)
        cur_col += n_rst
        rst_outp = self.add_laygo_primitive(blk_type, loc=(cur_col, row_idx), nx=n_rst, spx=1)
        cur_col += n_rst
        invp_outp = self.add_laygo_primitive(blk_type, loc=(cur_col, row_idx), nx=n_invp, spx=1)
        cur_col += n_invp
        pdum_list.append((self.add_laygo_primitive(blk_type, loc=(cur_col, row_idx), nx=n_sep, spx=1), 0))
        cur_col += n_sep
        invp_outn = self.add_laygo_primitive(blk_type, loc=(cur_col, row_idx), nx=n_invp, spx=1)
        cur_col += n_invp
        rst_outn = self.add_laygo_primitive(blk_type, loc=(cur_col, row_idx), nx=n_rst, spx=1)
        cur_col += n_rst
        rst_midn = self.add_laygo_primitive(blk_type, loc=(cur_col, row_idx), nx=n_rst, spx=1)
        cur_col += n_rst
        pdum_list.append((self.add_laygo_primitive(blk_type, loc=(cur_col, row_idx), nx=col_p, spx=1), 0))
        cur_col += col_p + n_sp
        nandpl, nandpr = {'gb': [], 'gt': [], 'd': [], 's': []}, {'gb': [], 'gt': [], 'd': [], 's': []}
        for nand_dict in [nandpl, nandpr]:
            for idx in range(n_nand):
                inst = self.add_laygo_primitive('fg2s', loc=(cur_col + idx, row_idx), flip=idx % 2 == 1)
                nand_dict['gb'].extend(inst.get_all_port_pins('g0'))
                nand_dict['gt'].extend(inst.get_all_port_pins('g1'))
                nand_dict['d'].extend(inst.get_all_port_pins('d'))
                nand_dict['s'].extend(inst.get_all_port_pins('s'))
            cur_col += n_nand + n_nand_sp

        # nmos inverter row
        cur_col, row_idx = 0, 3
        ndum_list.append((self.add_laygo_primitive(blk_type, loc=(cur_col, row_idx), nx=col_invn - 1, spx=1), 0))
        cur_col += col_invn - 1
        ndum_list.append((self.add_laygo_primitive(blk_type, loc=(cur_col, row_idx), split_s=True), 1))
        cur_col += 1
        invn_outp = self.add_laygo_primitive(blk_type, loc=(cur_col, row_idx), nx=n_invn, spx=1)
        cur_col += n_invn
        ndum_list.append((self.add_laygo_primitive(blk_type, loc=(cur_col, row_idx), split_s=True), 1))
        cur_col += 1
        if n_sep > 2:
            ndum_list.append((self.add_laygo_primitive(blk_type, loc=(cur_col, row_idx), nx=n_sep - 2, spx=1), 0))
            cur_col += n_sep - 2
        if n_sep >= 2:
            ndum_list.append((self.add_laygo_primitive(blk_type, loc=(cur_col, row_idx), split_s=True), 1))
            cur_col += 1
        invn_outn = self.add_laygo_primitive(blk_type, loc=(cur_col, row_idx), nx=n_invn, spx=1)
        cur_col += n_invn
        ndum_list.append((self.add_laygo_primitive(blk_type, loc=(cur_col, row_idx), split_s=True), -1))
        cur_col += 1
        ndum_list.append((self.add_laygo_primitive(blk_type, loc=(cur_col, row_idx), nx=col_invn - 1, spx=1), 0))
        cur_col += col_invn - 1 + n_sp
        nandnl, nandnr = {'gb': [], 'gt': [], 'd': [], 's': []}, {'gb': [], 'gt': [], 'd': [], 's': []}
        for nand_dict in [nandnl, nandnr]:
            for idx in range(n_nand):
                flip = idx % 2 == 1
                inst = self.add_laygo_primitive('stack2s', loc=(cur_col + idx, row_idx), flip=flip)
                nand_dict['gb'].extend(inst.get_all_port_pins('g0'))
                nand_dict['gt'].extend(inst.get_all_port_pins('g1'))
                nand_dict['d'].extend(inst.get_all_port_pins('d'))
                nand_dict['s'].extend(inst.get_all_port_pins('s'))
            cur_col += n_nand + n_nand_sp

        # nmos input row
        cur_col, row_idx = 0, 2
        ndum_list.append((self.add_laygo_primitive(blk_type, loc=(cur_col, row_idx), nx=col_in - 1, spx=1), 0))
        cur_col += col_in - 1
        ndum_list.append((self.add_laygo_primitive(blk_type, loc=(cur_col, row_idx), split_s=True), 1))
        cur_col += 1
        inn = self.add_laygo_primitive(blk_type, loc=(cur_col, row_idx), nx=n_in, spx=1)
        cur_col += n_in
        ndum_list.append((self.add_laygo_primitive(blk_type, loc=(cur_col, row_idx), split_s=True), 1))
        cur_col += 1
        if n_sep > 2:
            ndum_list.append((self.add_laygo_primitive(blk_type, loc=(cur_col, row_idx), nx=n_sep - 2, spx=1), 0))
            cur_col += n_sep - 2
        if n_sep >= 2:
            ndum_list.append((self.add_laygo_primitive(blk_type, loc=(cur_col, row_idx), split_s=True), 1))
            cur_col += 1
        inp = self.add_laygo_primitive(blk_type, loc=(cur_col, row_idx), nx=n_in, spx=1)
        cur_col += n_in
        ndum_list.append((self.add_laygo_primitive(blk_type, loc=(cur_col, row_idx), split_s=True), -1))
        cur_col += 1
        ndum_list.append(
            (self.add_laygo_primitive(blk_type, loc=(cur_col, row_idx), nx=col_in - 1 + n_nand_tot, spx=1), 0))

        # nmos tail row
        cur_col, row_idx = 0, 1
        ndum_list.append((self.add_laygo_primitive(blk_type, loc=(cur_col, row_idx), nx=col_tail, spx=1), 0))
        cur_col += col_tail
        tailn = self.add_laygo_primitive(blk_type, loc=(cur_col, row_idx), nx=n_tail, spx=1)
        cur_col += n_tail
        ndum_list.append((self.add_laygo_primitive(blk_type, loc=(cur_col, row_idx), nx=n_sep, spx=1), 0))
        cur_col += n_sep
        tailp = self.add_laygo_primitive(blk_type, loc=(cur_col, row_idx), nx=n_tail, spx=1)
        cur_col += n_tail
        ndum_list.append(
            (self.add_laygo_primitive(blk_type, loc=(cur_col, row_idx), nx=col_tail + n_nand_tot, spx=1), 0))

        # pwell tap
        cur_col, row_idx = 0, 0
        pw_tap = self.add_laygo_primitive('sub', loc=(cur_col, row_idx), nx=n_tot, spx=1)

        # compute overall block size
        self.fill_space()

        # connect ground
        source_vss = pw_tap.get_all_port_pins('VSS') + tailn.get_all_port_pins('s') + tailp.get_all_port_pins('s')
        source_vss.extend(nandnl['s'])
        source_vss.extend(nandnr['s'])
        drain_vss = []
        for inst, mode in ndum_list:
            if mode == 0:
                source_vss.extend(inst.get_all_port_pins('s'))
            drain_vss.extend(inst.get_all_port_pins('d'))
            drain_vss.extend(inst.get_all_port_pins('g'))
        source_vss_tid = self.make_track_id(0, 'ds', loc_ds_sub[0], width=tr_w_sup)
        drain_vss_tid = self.make_track_id(0, 'ds', loc_ds_sub[1], width=tr_w_sup)
        source_vss_warrs = self.connect_to_tracks(source_vss, source_vss_tid)
        drain_vss_warrs = self.connect_to_tracks(drain_vss, drain_vss_tid)
        self.add_pin('VSS', source_vss_warrs, show=show_pins)
        self.add_pin('VSS', drain_vss_warrs, show=show_pins)

        # connect tail
        tail = []
        for inst in (tailp, tailn, inp, inn):
            tail.extend(inst.get_all_port_pins('d'))
        tail_tid = self.make_track_id(1, 'gb', loc_gb_tail[0], width=tr_w_tail)
        self.connect_to_tracks(tail, tail_tid)

        # connect tail clk
        clk_list = []
        tclk_tid = self.make_track_id(1, 'g', loc_g_tail[0], width=tr_w_clk)
        tclk = tailp.get_all_port_pins('g') + tailn.get_all_port_pins('g')
        clk_list.append(self.connect_to_tracks(tclk, tclk_tid))

        # connect inputs
        in_tid = self.make_track_id(2, 'g', loc_g_in[0], width=tr_w_in)
        inp_warr = self.connect_to_tracks(inp.get_all_port_pins('g'), in_tid)
        inn_warr = self.connect_to_tracks(inn.get_all_port_pins('g'), in_tid)
        self.add_pin('inp', inp_warr, show=show_pins)
        self.add_pin('inn', inn_warr, show=show_pins)

        # get output/mid horizontal track id
        nout_tid = self.make_track_id(3, 'gb', loc_gb_invn[0], width=tr_w_out)
        mid_tid = self.make_track_id(2, 'gb', loc_gb_in[0], width=tr_w_mid)

        # connect nmos mid
        nmidp = inn.get_all_port_pins('s') + invn_outp.get_all_port_pins('s')
        nmidn = inp.get_all_port_pins('s') + invn_outn.get_all_port_pins('s')
        nmidp = self.connect_wires(nmidp)[0].to_warr_list()
        nmidn = self.connect_wires(nmidn)[0].to_warr_list()
        # TODO: fix this part
        # exclude last wire to avoid horizontal line-end DRC error.
        nmidp = self.connect_to_tracks(nmidp[:-1], mid_tid)
        nmidn = self.connect_to_tracks(nmidn[1:], mid_tid)

        # connect pmos mid
        mid_tid = self.make_track_id(4, 'gb', loc_gb_invp[1], width=tr_w_mid)
        pmidp = self.connect_to_tracks(rst_midp.get_all_port_pins('d'), mid_tid, min_len_mode=-1)
        pmidn = self.connect_to_tracks(rst_midn.get_all_port_pins('d'), mid_tid, min_len_mode=1)

        # connect nmos output
        noutp = self.connect_to_tracks(invn_outp.get_all_port_pins('d'), nout_tid)
        noutn = self.connect_to_tracks(invn_outn.get_all_port_pins('d'), nout_tid)

        # connect pmos output
        pout_tid = self.make_track_id(4, 'gb', loc_gb_invp[0], width=tr_w_mid)
        poutp = invp_outp.get_all_port_pins('d') + rst_outp.get_all_port_pins('d')
        poutn = invp_outn.get_all_port_pins('d') + rst_outn.get_all_port_pins('d')
        poutp = self.connect_to_tracks(poutp, pout_tid)
        poutn = self.connect_to_tracks(poutn, pout_tid)

        # connect clock in inverter row
        pclk = []
        for inst in (rst_midp, rst_midn, rst_outp, rst_outn):
            pclk.extend(inst.get_all_port_pins('g'))
        pclk_tid = self.make_track_id(4, 'g', loc_g_invp[0], width=tr_w_clk)
        clk_list.append(self.connect_to_tracks(pclk, pclk_tid))

        # connect inverter gate
        invg_tid = self.make_track_id(3, 'g', loc_g_invn[0], width=tr_w_out)
        invgp = invn_outp.get_all_port_pins('g') + invp_outp.get_all_port_pins('g')
        invgp = self.connect_to_tracks(invgp, invg_tid)
        invgn = invn_outn.get_all_port_pins('g') + invp_outn.get_all_port_pins('g')
        invgn = self.connect_to_tracks(invgn, invg_tid)

        # connect vdd
        source_vdd = nw_tap.get_all_port_pins('VDD')
        source_vdd.extend(invp_outp.get_all_port_pins('s'))
        source_vdd.extend(invp_outn.get_all_port_pins('s'))
        source_vdd.extend(rst_midp.get_all_port_pins('s'))
        source_vdd.extend(rst_midn.get_all_port_pins('s'))
        source_vdd.extend(nandpl['s'])
        source_vdd.extend(nandpr['s'])
        drain_vdd = []
        for inst, _ in pdum_list:
            source_vdd.extend(inst.get_all_port_pins('s'))
            drain_vdd.extend(inst.get_all_port_pins('d'))
            drain_vdd.extend(inst.get_all_port_pins('g'))
        source_vdd_tid = self.make_track_id(5, 'ds', loc_ds_sub[0], width=tr_w_sup)
        drain_vdd_tid = self.make_track_id(5, 'ds', loc_ds_sub[0], width=tr_w_sup)
        source_vdd_warrs = self.connect_to_tracks(source_vdd, source_vdd_tid)
        drain_vdd_warrs = self.connect_to_tracks(drain_vdd, drain_vdd_tid)
        self.add_pin('VDD', source_vdd_warrs, show=show_pins)
        self.add_pin('VDD', drain_vdd_warrs, show=show_pins)

        # connect nand
        nand_gbl_tid = self.make_track_id(3, 'g', loc_g_invn2[1], width=tr_w_nand)
        nand_gtl_id = self.get_track_index(3, 'g', loc_g_invn2[0])
        nand_gtr_id = self.get_track_index(4, 'g', loc_g_invp2[0])
        nand_gbr_tid = self.make_track_id(4, 'g', loc_g_invp2[1], width=tr_w_nand)
        nand_nmos_out_tid = self.make_track_id(3, 'gb', (tr_w_nand - 1) // 2, width=tr_w_nand)
        nand_outnl = self.connect_to_tracks(nandnl['d'], nand_nmos_out_tid, min_len_mode=1)
        nand_outnr = self.connect_to_tracks(nandnr['d'], nand_nmos_out_tid, min_len_mode=1)

        nand_gtl = nandnl['gt'] + nandpl['gt']
        nand_gtl.extend(nandpr['d'])
        nand_gtr = nandnr['gt'] + nandpr['gt']
        nand_gtr.extend(nandpl['d'])
        nand_outpl, nand_outpr = self.connect_differential_tracks(nand_gtr, nand_gtl, hm_layer, nand_gtr_id,
                                                                  nand_gtl_id, width=tr_w_nand)

        nand_gbl = self.connect_to_tracks(nandnl['gb'] + nandpl['gb'], nand_gbl_tid)
        nand_gbr = self.connect_to_tracks(nandnr['gb'] + nandpr['gb'], nand_gbr_tid)

        # connect nand ym wires
        tr_w_nand_y = tr_manager.get_width(ym_layer, 'nand')
        nand_outl_id = self.grid.coord_to_nearest_track(ym_layer, nand_outnl.middle, half_track=True, mode=1)
        nand_outr_id = self.grid.coord_to_nearest_track(ym_layer, nand_outnr.middle, half_track=True, mode=-1)
        nand_gbr_yt = self.grid.get_wire_bounds(hm_layer, nand_gbr_tid.base_index, unit_mode=True)[1]
        ym_via_ext = self.grid.get_via_extensions(hm_layer, 1, 1, unit_mode=True)[1]
        out_upper = nand_gbr_yt + ym_via_ext
        nand_outl, nand_outr = self.connect_differential_tracks(nand_outpl, nand_outpr, ym_layer,
                                                                nand_outl_id, nand_outr_id, track_upper=out_upper,
                                                                width=tr_w_nand_y, unit_mode=True)
        self.connect_to_tracks(nand_outnl, nand_outl.track_id)
        self.connect_to_tracks(nand_outnr, nand_outr.track_id)

        self.add_pin('outp', nand_outl, show=show_pins)
        self.add_pin('outn', nand_outr, show=show_pins)

        sp_nand_ym = tr_manager.get_space(ym_layer, ('nand', 'nand')) + tr_w_nand_y
        nand_inn_tid = nand_outl_id - sp_nand_ym
        nand_inp_tid = nand_outr_id + sp_nand_ym
        self.connect_differential_tracks(nand_gbl, nand_gbr, ym_layer, nand_inn_tid, nand_inp_tid, width=tr_w_nand_y)

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
        sp_out_mid = sp_out_ym + tr_manager.get_space(ym_layer, ('out', 'mid')) + (tr_w_mid_ym + tr_w_out_ym) / 2
        mn_tid = TrackID(ym_layer, on_idx + sp_out_mid, width=tr_w_mid_ym)
        mp_tid = TrackID(ym_layer, op_idx - sp_out_mid, width=tr_w_mid_ym)
        self.connect_to_tracks([nmidn, pmidn], mn_tid)
        self.connect_to_tracks([nmidp, pmidp], mp_tid)

        xm_layer = ym_layer + 1
        om_idx = self.grid.coord_to_nearest_track(xm_layer, outp1.middle, half_track=True)
        sp_out_xm = tr_manager.get_space(xm_layer, ('out', 'out'))
        tr_w_out_xm = tr_manager.get_width(xm_layer, 'out')
        outp, outn = self.connect_differential_tracks([outp1, outp2], [outn1, outn2], xm_layer,
                                                      om_idx + sp_out_xm / 2, om_idx - sp_out_xm / 2,
                                                      width=tr_w_out_xm)
        self.add_pin('midp', outp, show=show_pins)
        self.add_pin('midn', outn, show=show_pins)
        self.connect_differential_tracks(outn, outp, ym_layer, nand_inn_tid, nand_inp_tid, width=tr_w_nand_y)
