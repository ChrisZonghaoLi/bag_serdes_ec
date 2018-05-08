# -*- coding: utf-8 -*-

"""This module defines classes needed to build the Hybrid-QDR FFE/DFE summer."""

from typing import TYPE_CHECKING, Dict, Any, Set

from itertools import repeat, chain

from bag.layout.util import BBox
from bag.layout.routing.base import TrackID, TrackManager
from bag.layout.template import TemplateBase

from abs_templates_ec.routing.bias import BiasShield

from analog_ec.layout.dac.rladder.top import RDACArray
from analog_ec.layout.passives.filter.highpass import HighPassArrayClk

from .datapath import RXDatapath

if TYPE_CHECKING:
    from bag.layout.template import TemplateDB


class RXFrontend(TemplateBase):
    """The receiver datapath.

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

    @property
    def sch_params(self):
        # type: () -> Dict[str, Any]
        return self._sch_params

    @classmethod
    def get_params_info(cls):
        # type: () -> Dict[str, str]
        return dict(
            dp_params='datapath parameters.',
            hp_params='high-pass filter array parameters.',
            tr_widths='Track width dictionary.',
            tr_spaces='Track spacing dictionary.',
            fill_config='Fill configuration dictionary.',
            bias_config='The bias configuration dictionary.',
            show_pins='True to create pin labels.',
        )

    @classmethod
    def get_default_param_values(cls):
        # type: () -> Dict[str, Any]
        return dict(
            show_pins=True,
        )

    def draw_layout(self):
        bus_margin = 8000

        tr_widths = self.params['tr_widths']
        tr_spaces = self.params['tr_spaces']
        fill_config = self.params['fill_config']
        bias_config = self.params['bias_config']
        show_pins = self.params['show_pins']

        dp_master, hpx_master, hp1_master = self._make_masters(tr_widths, tr_spaces)

        # place masters
        hp_h = hpx_master.array_box.top_unit
        hpx_w = hpx_master.bound_box.width_unit
        hp1_w = hp1_master.bound_box.width_unit

        top_layer = dp_master.top_layer
        tr_manager = TrackManager(self.grid, tr_widths, tr_spaces, half_space=True)
        tmp = self._compute_route_height(top_layer, tr_manager, dp_master.num_ffe,
                                         dp_master.num_dfe, bias_config)
        clk_locs, clk_h, vss_h, vdd_h = tmp

        bot_h = hp_h + clk_h + vss_h + vdd_h
        bnd_box = dp_master.bound_box
        blk_w, blk_h = self.grid.get_fill_size(top_layer, fill_config, unit_mode=True)
        dp_h = bnd_box.height_unit
        tot_w = -(-(bnd_box.width_unit + bus_margin) // blk_w) * blk_w
        tot_h = -(-(dp_h + 2 * bot_h) // blk_h) * blk_h
        x0 = tot_w - bnd_box.width_unit
        y0 = (tot_h - dp_h) // (2 * blk_h) * blk_h
        dp_inst = self.add_instance(dp_master, 'XDP', loc=(x0, y0), unit_mode=True)
        x_hpx = x0 + dp_master.x_tapx[1] - hpx_w
        x_hp1 = max(x_hpx + hpx_w, x0 + dp_master.x_tap1[1] - hp1_w)
        hpxb_inst = self.add_instance(hpx_master, 'XHPXB', loc=(x_hpx, 0), unit_mode=True)
        hp1b_inst = self.add_instance(hp1_master, 'XHP1B', loc=(x_hp1, 0), unit_mode=True)
        hpxt_inst = self.add_instance(hpx_master, 'XHPXB', loc=(x_hpx, tot_h),
                                      orient='MX', unit_mode=True)
        hp1t_inst = self.add_instance(hp1_master, 'XHP1B', loc=(x_hp1, tot_h),
                                      orient='MX', unit_mode=True)

        ym_layer = dp_master.top_layer
        bnd_box = BBox(0, 0, tot_w, tot_h, self.grid.resolution, unit_mode=True)
        self.set_size_from_bound_box(ym_layer, bnd_box)
        self.array_box = bnd_box
        self.add_cell_boundary(bnd_box)

        # mark blockages
        yb = hp_h
        yt = tot_h - hp_h
        res = self.grid.resolution
        for xl, xu in dp_master.blockage_intvs:
            self.mark_bbox_used(ym_layer, BBox(xl + x0, yb, xu + x0, yt, res, unit_mode=True))

        # export pins
        self._reexport_dp_pins(dp_inst, show_pins)

        # connect supplies
        vdd_wires = dp_inst.get_all_port_pins('VDD', layer=top_layer)
        vss_wires = dp_inst.get_all_port_pins('VSS', layer=top_layer)
        self._connect_supply_clk(tr_manager, ym_layer + 1, dp_inst, dp_master.sup_y_list,
                                 vdd_wires, vss_wires, show_pins)

        # connect clocks and VSS-referenced wires
        num_dfe = dp_master.num_dfe
        hm_layer = top_layer - 1
        clk_tr_w = tr_manager.get_width(hm_layer, 'clk')
        self._connect_clk_vss_bias(hm_layer, vss_wires, x0, tot_h, dp_inst, hpxb_inst, hp1b_inst,
                                   num_dfe, hp_h, clk_locs, clk_tr_w, clk_h, vss_h, bias_config,
                                   show_pins, is_bot=True)

        self._connect_clk_vss_bias(hm_layer, vss_wires, x0, tot_h, dp_inst, hpxt_inst, hp1t_inst,
                                   num_dfe, hp_h, clk_locs, clk_tr_w, clk_h, vss_h, bias_config,
                                   show_pins, is_bot=False)

        # gather VDD-referenced wires
        num_ffe = dp_master.num_ffe
        vdd_wires.extend(dp_inst.port_pins_iter('VDD', layer=top_layer - 2))
        y0 = hp_h + clk_h + vss_h
        self._connect_vdd_bias(hm_layer, x0, num_dfe, num_ffe, vdd_wires, dp_inst,
                               y0, bias_config, show_pins, is_bot=True)

        y0 = tot_h - (hp_h + clk_h + vss_h + vdd_h)
        self._connect_vdd_bias(hm_layer, x0, num_dfe, num_ffe, vdd_wires, dp_inst,
                               y0, bias_config, show_pins, is_bot=False)

        self._sch_params = dp_master.sch_params.copy()
        self._sch_params['hp_params'] = hpx_master.sch_params['hp_params']
        self._sch_params['ndum_res'] = hpx_master.sch_params['ndum'] * 4

    def _connect_supply_clk(self, tr_manager, xm_layer, dp_inst, sup_yc_list, vdd_wires, vss_wires,
                            show_pins):
        tr_w_sup = tr_manager.get_width(xm_layer, 'sup')
        tr_w_clk = tr_manager.get_width(xm_layer, 'clk')
        tr_w_div = tr_manager.get_width(xm_layer, 'en_div')
        dp_box = dp_inst.bound_box
        y0 = dp_box.bottom_unit
        xl = dp_box.left_unit
        xr = dp_box.right_unit
        yc = dp_box.yc_unit

        for idx, ysup_mid in enumerate(sup_yc_list):
            ycur = ysup_mid + y0
            if ycur < yc:
                tidx = self.grid.coord_to_nearest_track(xm_layer, ycur, half_track=True, mode=-1,
                                                        unit_mode=True)
            else:
                tidx = self.grid.coord_to_nearest_track(xm_layer, ycur, half_track=True, mode=1,
                                                        unit_mode=True)

            tid = TrackID(xm_layer, tidx, width=tr_w_sup)
            if idx % 2 == 0:
                warr = self.connect_to_tracks(vss_wires, tid, track_lower=xl, track_upper=xr,
                                              unit_mode=True)
                self.add_pin('VSS', warr, show=show_pins)
            else:
                warr = self.connect_to_tracks(vdd_wires, tid, track_lower=xl, track_upper=xr,
                                              unit_mode=True)
                self.add_pin('VDD', warr, show=show_pins)

        enb_y = y0 + (sup_yc_list[2] + sup_yc_list[3]) // 2
        clkn_y = y0 + (sup_yc_list[3] + sup_yc_list[4]) // 2
        clkp_y = y0 + (sup_yc_list[4] + sup_yc_list[5]) // 2
        ent_y = y0 + (sup_yc_list[5] + sup_yc_list[6]) // 2

        nidx = self.grid.coord_to_nearest_track(xm_layer, clkn_y, half_track=True, mode=-1,
                                                unit_mode=True)
        pidx = self.grid.coord_to_nearest_track(xm_layer, clkp_y, half_track=True, mode=1,
                                                unit_mode=True)
        clkp = dp_inst.get_all_port_pins('clkp')
        clkn = dp_inst.get_all_port_pins('clkn')
        clkp, clkn = self.connect_differential_tracks(clkp, clkn, xm_layer, pidx, nidx,
                                                      width=tr_w_clk)
        self.add_pin('clkp', clkp, label='clkp:', show=show_pins)
        self.add_pin('clkn', clkn, label='clkn:', show=show_pins)

        nidx = self.grid.coord_to_nearest_track(xm_layer, enb_y, half_track=True, mode=-1,
                                                unit_mode=True)
        pidx = self.grid.coord_to_nearest_track(xm_layer, ent_y, half_track=True, mode=1,
                                                unit_mode=True)
        en = self.connect_wires(list(chain(dp_inst.port_pins_iter('en_div<3>'),
                                           dp_inst.port_pins_iter('en_div<2>'))))
        tid = TrackID(xm_layer, nidx, width=tr_w_div, num=2, pitch=pidx - nidx)
        en = self.connect_to_tracks(en, tid)
        self.add_pin('enable_divider', en, show=show_pins)

    def _reexport_dp_pins(self, dp_inst, show_pins):
        for name in ['inp', 'inn', 'v_vincm', 'des_clk', 'des_clkb']:
            self.reexport(dp_inst.get_port(name), show=show_pins)

        for idx in range(4):
            suf = '<%d>' % idx
            self.reexport(dp_inst.get_port('data' + suf), show=show_pins)
            self.reexport(dp_inst.get_port('dlev' + suf), show=show_pins)

    def _connect_vdd_bias(self, hm_layer, x0, num_dfe, num_ffe, vdd_wires, dp_inst, y0,
                          bias_config, show_pins, is_bot=True):
        w_list = []
        name_list = []
        for port_name, out_name in self._vdd_ports_iter(num_dfe, num_ffe, is_bot=is_bot):
            w_list.append(dp_inst.get_pin(port_name))
            name_list.append(out_name)

        if not is_bot:
            w_list.reverse()
            name_list.reverse()
        bias_info = BiasShield.draw_bias_shields(self, hm_layer, bias_config, w_list, y0,
                                                 tr_lower=x0, lu_end_mode=1, sup_warrs=vdd_wires,
                                                 add_end=False)

        for name, tr in zip(name_list, bias_info.tracks):
            self.add_pin(name, tr, show=show_pins, edge_mode=-1)

    def _connect_clk_vss_bias(self, hm_layer, vss_wires, x0, tot_h, dp_inst, hpx_inst, hp1_inst,
                              num_dfe, hp_h, clk_locs, clk_tr_w, clk_h, vss_h, bias_config,
                              show_pins, is_bot=True):
        ntr_tot = len(clk_locs)
        num_pair = (ntr_tot - 2) // 2
        vss_idx_lookup = {}
        vss_warrs_list = []
        vss_name_list = []

        vss_idx = 0
        pwarr = None
        if is_bot:
            tr0 = self.grid.find_next_track(hm_layer, hp_h, half_track=True, mode=1, unit_mode=True)
            sgn = 1
        else:
            tr0 = self.grid.find_next_track(hm_layer, tot_h - hp_h, half_track=True, mode=-1,
                                            unit_mode=True)
            sgn = -1

        hpx_iter = self._hpx_ports_iter(num_dfe, is_bot=is_bot)
        hp1_iter = self._hp1_ports_iter(is_bot=is_bot)
        for inst, port_iter in ((hpx_inst, hpx_iter), (hp1_inst, hp1_iter)):
            for idx, (out_name, bias_name) in enumerate(port_iter):
                suf = '<%d>' % idx
                if idx % 2 == 0:
                    pwarr = [inst.get_pin('out' + suf), dp_inst.get_pin(out_name)]
                else:
                    nwarr = [inst.get_pin('out' + suf), dp_inst.get_pin(out_name)]

                    cur_tr_id = (idx // 2) % num_pair
                    pidx = tr0 + sgn * clk_locs[1 + cur_tr_id]
                    nidx = tr0 + sgn * clk_locs[ntr_tot - 2 - cur_tr_id]
                    self.connect_differential_tracks(pwarr, nwarr, hm_layer, pidx, nidx,
                                                     width=clk_tr_w, unit_mode=True)

                bias_pin = inst.get_pin('bias' + suf)
                if bias_name not in vss_idx_lookup:
                    vss_name_list.append(bias_name)
                    vss_idx_lookup[bias_name] = vss_idx
                    vss_warrs_list.append([bias_pin])
                    vss_idx += 1
                else:
                    vss_warrs_list[vss_idx_lookup[bias_name]].append(bias_pin)

        if is_bot:
            scan_name = 'scan_divider_clkp'
            scan_pins = dp_inst.get_all_port_pins('scan_div<3>')
            bot_tr = tr0 + clk_locs[0]
        else:
            scan_name = 'scan_divider_clkn'
            scan_pins = dp_inst.get_all_port_pins('scan_div<2>')
            bot_tr = tr0 - clk_locs[-1]
        vss_name_list.append(scan_name)
        vss_warrs_list.append(scan_pins)
        vss_tid = TrackID(hm_layer, bot_tr, width=1, num=2, pitch=abs(clk_locs[-1] - clk_locs[0]))

        _, vss_wires = self.connect_to_tracks(vss_wires, vss_tid, return_wires=True)
        if is_bot:
            vss_coord = vss_wires[0].lower_unit
            self.extend_wires(dp_inst.get_all_port_pins('VDD_ext'), lower=vss_coord, unit_mode=True)
            offset = hp_h + clk_h
        else:
            vss_name_list.reverse()
            vss_warrs_list.reverse()
            vss_coord = vss_wires[0].upper_unit
            self.extend_wires(dp_inst.get_all_port_pins('VDD_ext'), upper=vss_coord, unit_mode=True)
            offset = tot_h - hp_h - clk_h - vss_h

        bias_info = BiasShield.draw_bias_shields(self, hm_layer, bias_config, vss_warrs_list,
                                                 offset, tr_lower=x0, lu_end_mode=1, add_end=False)
        self.connect_to_track_wires(vss_wires, bias_info.shields)

        for name, tr in zip(vss_name_list, bias_info.tracks):
            self.add_pin(name, tr, show=show_pins, edge_mode=-1)

        # export clks
        clkp = self.connect_wires([hpx_inst.get_pin('clkp'), hp1_inst.get_pin('clkp')])
        clkn = self.connect_wires([hpx_inst.get_pin('clkn'), hp1_inst.get_pin('clkn')])
        self.add_pin('clkp', clkp, label='clkp:', show=show_pins)
        self.add_pin('clkn', clkn, label='clkn:', show=show_pins)

        # connect high-pass filter substrates
        vssl_list = []
        vssm_list = []
        vssr_list = []
        hpx_box = hpx_inst.bound_box
        hp1_box = hp1_inst.bound_box
        for warr in vss_wires:
            for w in warr.to_warr_list():
                box = w.get_bbox_array(self.grid).base
                if box.right_unit < hpx_box.left_unit:
                    vssl_list.append(w)
                elif box.left_unit > hp1_box.right_unit:
                    vssr_list.append(w)
                elif box.left_unit > hpx_box.right_unit and box.right_unit < hp1_box.left_unit:
                    vssm_list.append(w)

        vssl = hpx_inst.get_pin('VSSL')
        vssm = self.connect_wires([hpx_inst.get_pin('VSSR'), hp1_inst.get_pin('VSSL')])[0]
        vssr = hp1_inst.get_pin('VSSR')
        self.connect_to_track_wires(vssl_list, vssl)
        self.connect_to_track_wires(vssm_list, vssm)
        self.connect_to_track_wires(vssr_list, vssr)
        if hpx_inst.has_port('VSS'):
            vss = self.connect_wires([hpx_inst.get_pin('VSS'), hp1_inst.get_pin('VSS')])[0]
            self.connect_to_track_wires(vssl_list, vss)
            self.connect_to_track_wires(vssr_list, vss)
            if not vssm_list:
                vm_layer = hm_layer + 1
                tid = self.grid.coord_to_nearest_track(vm_layer, vssm.middle_unit, half_track=True,
                                                       unit_mode=True)
                self.connect_to_tracks([vss, vssm], TrackID(vm_layer, tid))
            else:
                self.connect_to_track_wires(vssm_list, vss)
        elif not vssm_list:
            raise ValueError('Cannot connect middle VSS of high-pass filters.')

    @classmethod
    def _vdd_ports_iter(cls, num_dfe, num_ffe, is_bot=True):
        if is_bot:
            nway = psuf = 3
            pway = 0
            nsufa = 2
        else:
            nway = psuf = 1
            pway = 2
            nsufa = 0

        for name in ('dlev', 'off'):
            for way in (pway, nway):
                yield ('bias_%sp<%d>' % (name, way), 'v_way_%d_%s_p' % (way, name))
                yield ('bias_%sn<%d>' % (name, way), 'v_way_%d_%s_n' % (way, name))

        for idx in range(num_ffe, 0, -1):
            yield ('bias_ffe<%d>' % (4 * idx + psuf), 'v_way_%d_ffe_%d' % (pway, idx))
            yield ('bias_ffe<%d>' % (4 * idx + nsufa), 'v_way_%d_ffe_%d' % (nway, idx))

        for idx in range(num_dfe, 1, -1):
            yield ('sgnp_dfe<%d>' % (4 * idx + psuf), 'bias_way_%d_dfe_%d_s<0>' % (pway, idx))
            yield ('sgnn_dfe<%d>' % (4 * idx + psuf), 'bias_way_%d_dfe_%d_s<1>' % (pway, idx))
            yield ('sgnp_dfe<%d>' % (4 * idx + nsufa), 'bias_way_%d_dfe_%d_s<0>' % (nway, idx))
            yield ('sgnn_dfe<%d>' % (4 * idx + nsufa), 'bias_way_%d_dfe_%d_s<1>' % (nway, idx))

    @classmethod
    def _hpx_ports_iter(cls, num_dfe, is_bot=True):
        if is_bot:
            nway = psuf = 3
            pway = nsufl = 0
            nsufa = 2
        else:
            nway = psuf = 1
            pway = nsufl = 2
            nsufa = 0

        yield ('clk_analog<%d>' % psuf, 'v_analog')
        yield ('clk_analog<%d>' % nsufl, 'v_analog')
        yield ('clk_main<%d>' % nsufa, 'v_way_%d_main' % nway)
        yield ('clk_main<%d>' % psuf, 'v_way_%d_main' % pway)

        idx = 0
        for dfe_idx in range(num_dfe, 1, -1):
            if dfe_idx == 3:
                # insert digital bias
                if idx % 2 == 0:
                    yield ('clk_digital_tapx<%d>' % psuf, 'v_digital')
                    yield ('clk_digital_tapx<%d>' % nsufl, 'v_digital')
                else:
                    yield ('clk_digital_tapx<%d>' % nsufl, 'v_digital')
                    yield ('clk_digital_tapx<%d>' % psuf, 'v_digital')
                idx += 1
            if idx % 2 == 0:
                yield ('clk_dfe<%d>' % (4 * dfe_idx + psuf), 'v_way_%d_dfe_%d_m' % (pway, dfe_idx))
                yield ('clk_dfe<%d>' % (4 * dfe_idx + nsufa), 'v_way_%d_dfe_%d_m' % (nway, dfe_idx))
            else:
                yield ('clk_dfe<%d>' % (4 * dfe_idx + nsufa), 'v_way_%d_dfe_%d_m' % (nway, dfe_idx))
                yield ('clk_dfe<%d>' % (4 * dfe_idx + psuf), 'v_way_%d_dfe_%d_m' % (pway, dfe_idx))
            idx += 1

    @classmethod
    def _hp1_ports_iter(cls, is_bot=True):
        if is_bot:
            psuf = 1
            nway = nsufl = 0
            nsufa = 2
            pway = 3
        else:
            psuf = 3
            nway = nsufl = 2
            nsufa = 0
            pway = 1

        yield ('clk_digital_tap1<%d>' % psuf, 'v_digital')
        yield ('clk_digital_tap1<%d>' % nsufl, 'v_digital')
        yield ('clk_tap1<%d>' % nsufa, 'v_tap1_main')
        yield ('clk_tap1<%d>' % psuf, 'v_tap1_main')
        yield ('clk_dfe<%d>' % (4 + psuf), 'v_way_%d_dfe_1_m' % pway)
        yield ('clk_dfe<%d>' % (4 + nsufa), 'v_way_%d_dfe_1_m' % nway)

    def _compute_route_height(self, top_layer, tr_manager, num_ffe, num_dfe, bias_config):
        num_clk_tr = 2

        # scan_div, ana, dig, tap1_main, int_main * 2, 2 * each DFE
        num_vss = 6 + 2 * num_dfe
        # dlev, offset, 2 * each FFE, 4 * each DFE 2+ (sign bits)
        num_vdd = 8 + 2 * num_ffe + 4 * (num_dfe - 1)

        hm_layer = top_layer - 1
        blk_h = self.grid.get_block_size(top_layer, unit_mode=True)[1]
        wtype_list = ['sh']
        wtype_list.extend(repeat('clk', 2 * num_clk_tr))
        wtype_list.append('sh')
        ntr, locs = tr_manager.place_wires(hm_layer, wtype_list)
        tr_pitch = self.grid.get_track_pitch(hm_layer, unit_mode=True)
        clk_h = -(-(int(round(tr_pitch * ntr))) // blk_h) * blk_h
        vdd_h = BiasShield.get_block_size(self.grid, hm_layer, bias_config, num_vdd)[1]
        vss_h = BiasShield.get_block_size(self.grid, hm_layer, bias_config, num_vss)[1]

        return locs, clk_h, vss_h, vdd_h

    def _make_masters(self, tr_widths, tr_spaces):
        dp_params = self.params['dp_params']
        hp_params = self.params['hp_params']

        dp_params = dp_params.copy()
        dp_params['tr_widths'] = tr_widths
        dp_params['tr_spaces'] = tr_spaces
        dp_params['show_pins'] = False
        dp_master = self.new_template(params=dp_params, temp_cls=RXDatapath)

        hp_params = hp_params.copy()
        hp_params['narr'] = dp_master.num_hp_tapx
        hp_params['tr_widths'] = tr_widths
        hp_params['tr_spaces'] = tr_spaces
        hp_params['show_pins'] = False
        hpx_master = self.new_template(params=hp_params, temp_cls=HighPassArrayClk)

        hp_params['narr'] = dp_master.num_hp_tap1
        hp1_master = self.new_template(params=hp_params, temp_cls=HighPassArrayClk)

        return dp_master, hpx_master, hp1_master


class RXTop(TemplateBase):
    """The receiver datapath.

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

    @property
    def sch_params(self):
        # type: () -> Dict[str, Any]
        return self._sch_params

    @classmethod
    def get_params_info(cls):
        # type: () -> Dict[str, str]
        return dict(
            fe_params='RX frontend parameters.',
            dac_params='RX DAC parameters.',
            fill_config='fill configuration dictionary.',
            bias_config='bias configuration dictionary.',
            fill_orient_mode='fill orientation mode.',
            show_pins='True to show pins.',
        )

    @classmethod
    def get_default_param_values(cls):
        # type: () -> Dict[str, Any]
        return dict(
            fill_orient_mode=0,
            show_pins=True,
        )

    def draw_layout(self):
        fe_params = self.params['fe_params'].copy()
        dac_params = self.params['dac_params'].copy()
        fill_config = self.params['fill_config']
        bias_config = self.params['bias_config']
        fill_orient_mode = self.params['fill_orient_mode']
        show_pins = self.params['show_pins']

        fe_params['fill_config'] = dac_params['fill_config'] = fill_config
        fe_params['bias_config'] = dac_params['bias_config'] = bias_config
        fe_params['fill_orient_mode'] = fill_orient_mode
        dac_params['fill_orient_mode'] = fill_orient_mode ^ 2
        fe_params['show_pins'] = dac_params['show_pins'] = False

        master_fe = self.new_template(params=fe_params, temp_cls=RXFrontend)
        master_dac = self.new_template(params=dac_params, temp_cls=RDACArray)
        box_fe = master_fe.bound_box
        box_dac = master_dac.bound_box

        top_layer = master_dac.top_layer
        w_fe = box_fe.width_unit
        w_dac = box_dac.width_unit
        w_tot = max(w_fe, w_dac)
        x_fe = w_tot - w_fe
        x_dac = w_tot - w_dac
        h_tot = box_fe.height_unit + box_dac.height_unit

        inst_fe = self.add_instance(master_fe, 'XFE', loc=(x_fe, 0), unit_mode=True)
        inst_dac = self.add_instance(master_dac, 'XDAC', loc=(x_dac, h_tot), orient='MX',
                                     unit_mode=True)

        bnd_box = inst_dac.bound_box.extend(x=0, y=0, unit_mode=True)
        self.set_size_from_bound_box(top_layer, bnd_box)
        self.array_box = bnd_box
        self.add_cell_boundary(bnd_box)

        for name in inst_dac.port_names_iter():
            if name.startswith('bias_'):
                self.reexport(inst_dac.get_port(name), show=show_pins)
        for name in inst_fe.port_names_iter():
            self.reexport(inst_fe.get_port(name), show=show_pins)

        self._sch_params = dict(
            fe_params=master_fe.sch_params,
            dac_params=master_dac.sch_params,
        )
