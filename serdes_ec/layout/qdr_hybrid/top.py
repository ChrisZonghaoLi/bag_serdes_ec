# -*- coding: utf-8 -*-

"""This module defines classes needed to build the Hybrid-QDR FFE/DFE summer."""

from typing import TYPE_CHECKING, Dict, Any, Set, List, Tuple

from itertools import repeat, chain, islice

from bag.layout.util import BBox
from bag.layout.routing.base import TrackID, TrackManager
from bag.layout.template import TemplateBase

from abs_templates_ec.analog_mos.mos import DummyFillActive
from abs_templates_ec.routing.bias import BiasShield, BiasShieldJoin, \
    compute_vroute_width, join_bias_vroutes
from abs_templates_ec.routing.fill import PowerFill

from analog_ec.layout.dac.rladder.top import RDACArray
from analog_ec.layout.passives.filter.highpass import HighPassArrayClk

from ..analog.passives import PassiveCTLE, TermRX
from ..digital.buffer import BufferArray
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
        self._buf_locs = None
        self._retime_ncol = None
        self._bot_scan_names = None
        self._top_scan_names = None
        self._bias_info_list = None
        self._xm_layer = None

    @property
    def sch_params(self):
        # type: () -> Dict[str, Any]
        return self._sch_params

    @property
    def buf_locs(self):
        # type: () -> Tuple[Tuple[int, int], Tuple[int, int]]
        return self._buf_locs

    @property
    def retime_ncol(self):
        # type: () -> int
        return self._retime_ncol

    @property
    def bot_scan_names(self):
        # type: () -> List[str]
        return self._bot_scan_names

    @property
    def top_scan_names(self):
        # type: () -> List[str]
        return self._top_scan_names

    @property
    def bias_info_list(self):
        # type: () -> List[Tuple[int, int, int]]
        return self._bias_info_list

    @property
    def xm_layer(self):
        # type: () -> int
        return self._xm_layer

    @classmethod
    def get_cache_properties(cls):
        # type: () -> List[str]
        """Returns a list of properties to cache."""
        return ['sch_params', 'buf_locs', 'retime_ncol', 'bot_scan_names', 'top_scan_names',
                'xm_layer']

    @classmethod
    def get_params_info(cls):
        # type: () -> Dict[str, str]
        return dict(
            top_layer='The top routing layer.',
            ctle_params='CTLE parameters.',
            dp_params='datapath parameters.',
            hp_params='high-pass filter array parameters.',
            scan_buf_params='scan buffer parameters.',
            cap_h_table='AC coupling capacitor height dictionary.',
            tr_widths='Track width dictionary.',
            tr_spaces='Track spacing dictionary.',
            tr_widths_dig='Track width dictionary for digital.',
            tr_spaces_dig='Track spacing dictionary for digital.',
            fill_config='fill configuration dictionary.',
            bias_config='The bias configuration dictionary.',
            show_pins='True to create pin labels.',
            export_probe='True to export probe ports.',
        )

    @classmethod
    def get_default_param_values(cls):
        # type: () -> Dict[str, Any]
        return dict(
            show_pins=True,
            export_probe=False,
        )

    def draw_layout(self):
        top_layer = self.params['top_layer']
        tr_widths = self.params['tr_widths']
        tr_spaces = self.params['tr_spaces']
        fill_config = self.params['fill_config']
        bias_config = self.params['bias_config']
        show_pins = self.params['show_pins']
        export_probe = self.params['export_probe']

        master_ctle, master_dp, master_hpx, master_hp1 = self._make_masters(tr_widths, tr_spaces)

        # compute instance placements
        ctle_box = master_ctle.bound_box
        dp_box = master_dp.bound_box
        ctle_w = ctle_box.width_unit
        ctle_h = ctle_box.height_unit
        hp_h = master_hpx.array_box.top_unit
        hpx_w = master_hpx.bound_box.width_unit
        hp1_w = master_hp1.bound_box.width_unit

        # compute vertical placement
        ym_layer = master_dp.top_layer
        self._xm_layer = xm_layer = ym_layer + 1
        vm_layer = ym_layer - 2
        blk_h = self.grid.get_block_size(xm_layer, unit_mode=True, half_blk_y=False)[1]
        fill_w, fill_h = self.grid.get_fill_size(top_layer, fill_config, unit_mode=True)
        tr_manager = TrackManager(self.grid, tr_widths, tr_spaces, half_space=True)
        tmp = self._compute_route_height(ym_layer - 1, blk_h, tr_manager, master_dp.num_ffe,
                                         master_dp.num_dfe, bias_config)
        clk_locs, clk_h, vss_h, vdd_h, num_vm_vss, num_vm_vdd = tmp

        bot_h = hp_h + clk_h + vss_h + vdd_h
        dp_h = dp_box.height_unit
        inner_h = dp_h + 2 * bot_h
        tot_h = -(-inner_h // fill_h) * fill_h
        yoff = (tot_h - inner_h) // 2
        y_ctle = (tot_h - ctle_h) // 2
        y_dp = yoff + bot_h

        # compute horizontal placement
        tmp = compute_vroute_width(self, vm_layer, fill_w, num_vm_vdd, num_vm_vss, bias_config)
        route_w, vdd_x, vss_x = tmp
        tot_w = -(-(route_w + ctle_w + dp_box.width_unit) // fill_w) * fill_w
        x_dp = tot_w - dp_box.width_unit
        x_ctle = x_dp - ctle_w
        x_ctle_route = (x_ctle // fill_w) * fill_w
        ctle_inst = self.add_instance(master_ctle, 'XCTLE', loc=(x_ctle, y_ctle), unit_mode=True)
        dp_inst = self.add_instance(master_dp, 'XDP', loc=(x_dp, y_dp), unit_mode=True)
        dbuf_locs = master_dp.buf_locs
        self._buf_locs = ((dbuf_locs[0][0] + x_dp, dbuf_locs[0][1] + y_dp),
                          (dbuf_locs[1][0] + x_dp, dbuf_locs[1][1] + y_dp))
        x_hpx = x_dp + master_dp.x_tapx[1] - hpx_w
        xr_hpx = x_hpx + hpx_w
        x_hp1 = max(xr_hpx, x_dp + master_dp.x_tap1[1] - hp1_w)
        hpxb_inst = self.add_instance(master_hpx, 'XHPXB', loc=(x_hpx, yoff), unit_mode=True)
        hp1b_inst = self.add_instance(master_hp1, 'XHP1B', loc=(x_hp1, yoff), unit_mode=True)
        hpxt_inst = self.add_instance(master_hpx, 'XHPXB', loc=(x_hpx, tot_h - yoff),
                                      orient='MX', unit_mode=True)
        hp1t_inst = self.add_instance(master_hp1, 'XHP1B', loc=(x_hp1, tot_h - yoff),
                                      orient='MX', unit_mode=True)

        self.array_box = tot_box = BBox(0, 0, tot_w, tot_h, self.grid.resolution, unit_mode=True)
        self.set_size_from_bound_box(top_layer, tot_box)
        self.add_cell_boundary(tot_box)

        # fill between high-pass filters
        if x_hp1 > xr_hpx:
            dum_params = dict(
                mos_type='nch',
                threshold=master_hpx.params['threshold'],
            )
            res = self.grid.resolution
            box = BBox(xr_hpx, yoff, x_hp1, yoff + hp_h, res, unit_mode=True)
            self._fill_active(box, dum_params)
            box = BBox(xr_hpx, tot_h - yoff - hp_h, x_hp1, tot_h - yoff, res, unit_mode=True)
            self._fill_active(box, dum_params)

        # mark blockages
        yb = yoff + hp_h
        yt = tot_h - yoff - hp_h
        res = self.grid.resolution
        for xl, xu in master_dp.blockage_intvs:
            xl += x_dp
            xu += x_dp
            self.mark_bbox_used(ym_layer, BBox(xl, yb, xu, y_dp, res, unit_mode=True))
            self.mark_bbox_used(ym_layer, BBox(xl, y_dp + dp_box.height_unit, xu, yt,
                                               res, unit_mode=True))

        # export pins
        self._reexport_dp_pins(dp_inst, show_pins, export_probe)

        # connect clocks and enables
        sup_yc_list = master_dp.sup_y_list
        clkp_tid, clkn_tid = self._connect_clk_en(tr_manager, top_layer, xm_layer, dp_inst,
                                                  sup_yc_list, show_pins)

        # connect CTLE
        tmp = self._connect_ctle(tr_manager, ctle_inst, dp_inst, clkp_tid, clkn_tid, show_pins)
        vincm, ctle_vss, biasl_vss, biasl_vdd = tmp
        # connect biases
        num_dfe = master_dp.num_dfe
        hm_layer = ym_layer - 1
        clk_tr_w = tr_manager.get_width(hm_layer, 'clk')
        ytop = tot_h - yoff

        vdd_pins = []
        vss_pins = []
        hm_bias_info_list = [None, None, None, None]
        vdd_wires = dp_inst.get_all_port_pins('VDD', layer=ym_layer)
        vss_wires = dp_inst.get_all_port_pins('VSS', layer=ym_layer)
        bi = self._connect_clk_vss_bias(tr_manager, hm_layer, vss_wires, x_ctle_route, yoff, ytop,
                                        dp_inst, hpxb_inst, hp1b_inst, num_dfe, hp_h, clk_locs,
                                        clk_tr_w, clk_h, vss_h, bias_config, show_pins, vss_pins,
                                        top_layer, fill_config, is_bot=True)
        hm_bias_info_list[0] = bi

        bi = self._connect_clk_vss_bias(tr_manager, hm_layer, vss_wires, x_ctle_route, yoff, ytop,
                                        dp_inst, hpxt_inst, hp1t_inst, num_dfe, hp_h, clk_locs,
                                        clk_tr_w, clk_h, vss_h, bias_config, show_pins, vss_pins,
                                        top_layer, fill_config, is_bot=False)
        hm_bias_info_list[3] = bi

        # gather VDD-referenced wires
        num_ffe = master_dp.num_ffe
        bias_vdd_wires = dp_inst.get_all_port_pins('VDD', layer=vm_layer)
        bias_vdd_wires.extend(vdd_wires)
        y_bvdd = yoff + hp_h + clk_h + vss_h
        bi = self._connect_vdd_bias(hm_layer, x_ctle_route, num_dfe, num_ffe, bias_vdd_wires,
                                    dp_inst, y_bvdd, bias_config, show_pins, vdd_pins, is_bot=True)
        hm_bias_info_list[1] = bi

        y_tvdd = ytop - (hp_h + clk_h + vss_h + vdd_h)
        bi = self._connect_vdd_bias(hm_layer, x_ctle_route, num_dfe, num_ffe, bias_vdd_wires,
                                    dp_inst, y_tvdd, bias_config, show_pins, vdd_pins, is_bot=False)
        hm_bias_info_list[2] = bi

        # connect vincm
        vss_rtids = BiasShield.get_route_tids(self.grid, vm_layer, vss_x[0],
                                              bias_config, num_vm_vss)
        vincm_tid = TrackID(vm_layer, vss_rtids[-2][0], width=vss_rtids[-2][1])
        y_route = ytop - hp_h - clk_h
        vincm = self.connect_to_tracks(vincm, vincm_tid, track_upper=y_route, unit_mode=True)
        # join bias routes together
        ctle_vss.extend(biasl_vss)
        tmp = join_bias_vroutes(self, vm_layer, vdd_x, vss_x, x_ctle_route, num_vm_vdd, num_vm_vss,
                                hm_bias_info_list, bias_config, vdd_pins, vss_pins,
                                xl=0, vss_warrs=ctle_vss, vdd_warrs=biasl_vdd)
        vdd_pins, vss_pins, vdd_bias, vss_bias = tmp
        vss_pins.append(('v_vincm', vincm))

        # extend bias routes to edge
        self._extend_bias_routes(hm_layer, bias_config, vdd_pins, vss_pins, y_route,
                                 vdd_x[0], vss_x[0], show_pins)

        # connect supplies and clock
        vdd_wires.extend(vdd_bias)
        vss_wires.extend(vss_bias)
        fill_box = BBox(route_w, y_dp, x_dp, y_tvdd, res, unit_mode=True)
        self._connect_supplies(tr_manager, xm_layer, dp_inst, sup_yc_list, vdd_wires,
                               vss_wires, biasl_vdd, ctle_vss, fill_box, fill_config, show_pins)

        # do fill
        core_fill_box = ctle_inst.fill_box.merge(dp_inst.fill_box)
        for layer in range(ym_layer, ym_layer + 2):
            self.do_max_space_fill(layer, bound_box=core_fill_box, fill_pitch=2)
            for inst in (hpxb_inst, hpxt_inst, hp1b_inst, hp1t_inst):
                self.do_max_space_fill(layer, bound_box=inst.fill_box, fill_pitch=2)

        self._sch_params = master_dp.sch_params.copy()
        self._sch_params['ctle_params'] = master_ctle.sch_params
        self._sch_params['hp_params'] = master_hpx.sch_params['hp_params']
        self._sch_params['ndum_res'] = master_hpx.sch_params['ndum'] * 4
        self._sch_params['export_probe'] = export_probe

    def _fill_active(self, box, dum_params):
        dum_params['width'] = box.width_unit
        dum_params['height'] = box.height_unit
        master_dum = self.new_template(params=dum_params, temp_cls=DummyFillActive)
        self.add_instance(master_dum, loc=(box.left_unit, box.bottom_unit), unit_mode=True)

    def _extend_bias_routes(self, hm_layer, bias_config, vdd_pins, vss_pins, y_route,
                            x_vdd, x_vss, show_pins):
        # make corner masters
        vm_layer = hm_layer - 1
        ym_layer = hm_layer + 1
        num_vss = len(vss_pins)
        num_vdd = len(vdd_pins)
        vss_params = dict(
            nwire=num_vss,
            width=1,
            space_sig=0,
        )
        vdd_params = dict(
            nwire=num_vdd,
            width=1,
            space_sig=0,
        )
        vssc_params = dict(
            bot_layer=vm_layer,
            bias_config=bias_config,
            bot_params=vss_params,
            top_params=vss_params,
        )
        vddc_params = dict(
            bot_layer=vm_layer,
            bias_config=bias_config,
            bot_params=vdd_params,
            top_params=vdd_params,
        )
        master_vssc = self.new_template(params=vssc_params, temp_cls=BiasShieldJoin)
        master_vddc = self.new_template(params=vddc_params, temp_cls=BiasShieldJoin)

        # extend to corners, then to edge
        ytop = self.bound_box.top_unit
        y_vssc = ytop - master_vssc.bound_box.height_unit
        y_vddc = y_vssc - master_vddc.bound_box.height_unit
        for master, x, y, num, pins in ((master_vssc, x_vss, y_vssc, num_vss, vss_pins),
                                        (master_vddc, x_vdd, y_vddc, num_vdd, vdd_pins)):
            inst = self.add_instance(master, loc=(x, y), unit_mode=True)
            sup_ym = self.extend_wires(inst.get_all_port_pins('sup_core', layer=ym_layer),
                                       lower=y_route, unit_mode=True)
            sup_hm, _ = BiasShield.draw_bias_shields(self, vm_layer, bias_config, num, x,
                                                     y_route, y, check_blockage=False)
            self.draw_vias_on_intersections(sup_hm, sup_ym)

            if x > 0:
                BiasShield.draw_bias_shields(self, hm_layer, bias_config, num, y,
                                             0, x, check_blockage=False)

            tr0 = self.grid.find_next_track(hm_layer, y, half_track=True, mode=1, unit_mode=True)
            for (name, warr), (tidx, tr_w) in zip(pins, islice(master.hm_route_tids, 1, num + 1)):
                tid = TrackID(hm_layer, tidx + tr0, width=tr_w)
                warr = self.connect_to_tracks(warr, tid, track_lower=0, unit_mode=True)
                self.add_pin(name, warr, show=show_pins, edge_mode=-1)

    def _connect_ctle(self, tr_manager, ctle_inst, dp_inst, p_tid, n_tid, show_pins):
        xm_layer = p_tid.layer_id
        hm_layer = xm_layer - 2
        tr_w = tr_manager.get_width(xm_layer, 'serdes_in')
        pyb = p_tid.get_bounds(self.grid, unit_mode=True)[0]
        nyt = n_tid.get_bounds(self.grid, unit_mode=True)[1]
        pidx = self.grid.find_next_track(xm_layer, pyb, tr_width=tr_w, half_track=True,
                                         mode=-1, unit_mode=True)
        nidx = self.grid.find_next_track(xm_layer, nyt, tr_width=tr_w, half_track=True,
                                         mode=1, unit_mode=True)

        outp = self.connect_to_tracks(ctle_inst.get_pin('outp'),
                                      TrackID(xm_layer, pidx, width=tr_w))
        outn = self.connect_to_tracks(ctle_inst.get_pin('outn'),
                                      TrackID(xm_layer, nidx, width=tr_w))
        self.connect_differential_wires(outp, outn, dp_inst.get_pin('inp'),
                                        dp_inst.get_pin('inn'), unit_mode=True)

        inp = self.connect_to_tracks(ctle_inst.get_pin('inp'), TrackID(xm_layer, pidx, width=tr_w),
                                     min_len_mode=-1, track_lower=0, unit_mode=True)
        inn = self.connect_to_tracks(ctle_inst.get_pin('inn'), TrackID(xm_layer, nidx, width=tr_w),
                                     min_len_mode=-1, track_lower=0, unit_mode=True)

        self.add_pin('inp', inp, show=show_pins)
        self.add_pin('inn', inn, show=show_pins)

        ctle_vss = ctle_inst.get_all_port_pins('VSS')
        biasl_vss = []
        biasl_vdd = []
        ctle_box = ctle_inst.bound_box
        ctle_yb = ctle_box.bottom_unit
        ctle_yt = ctle_box.top_unit
        for pin in dp_inst.port_pins_iter('VSS', layer=hm_layer):
            pin_yb, pin_yt = pin.track_id.get_bounds(self.grid, unit_mode=True)
            if pin_yt < ctle_yb or pin_yb > ctle_yt:
                biasl_vss.append(pin)
        for pin in dp_inst.port_pins_iter('VDD', layer=hm_layer):
            pin_yb, pin_yt = pin.track_id.get_bounds(self.grid, unit_mode=True)
            if pin_yt < ctle_yb or pin_yb > ctle_yt:
                biasl_vdd.append(pin)

        return ctle_inst.get_pin('outcm'), ctle_vss, biasl_vss, biasl_vdd

    @staticmethod
    def _warr_sort_fun(w):
        return w.track_id.base_index

    def _connect_clk_en(self, tr_manager, top_layer, xm_layer, dp_inst, sup_yc_list, show_pins):
        xm_tr_w_clk = tr_manager.get_width(xm_layer, 'clk')
        tr_w_div = tr_manager.get_width(xm_layer, 'en_div')
        dp_box = dp_inst.bound_box
        y0 = dp_box.bottom_unit

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

        clkp_cur = sorted(clkp, key=self._warr_sort_fun)
        clkn_cur = sorted(clkn, key=self._warr_sort_fun)

        curp_list = []
        curn_list = []
        for curp, curn in zip(clkp_cur, clkn_cur):
            curp, curn = self.connect_differential_tracks(curp, curn, xm_layer, pidx, nidx,
                                                          width=xm_tr_w_clk)
            curp_list.append(curp)
            curn_list.append(curn)
        clkp_cur = curp_list
        clkn_cur = curn_list
        clkp_tid = clkp_cur[0].track_id
        clkn_tid = clkn_cur[0].track_id
        for lay in range(xm_layer + 1, top_layer + 1):
            tr_sp_clk = tr_manager.get_space(lay, ('clk', 'clk'))
            tr_w_clk = tr_manager.get_width(lay, 'clk')
            tr_pitch = int(round(2 * (tr_sp_clk + tr_w_clk)))
            tr_pitch = tr_pitch // 2 if tr_pitch % 2 == 0 else (tr_pitch + 1) // 2
            curp_list = []
            curn_list = []
            for curp, curn in zip(clkp_cur, clkn_cur):
                idxm = self.grid.coord_to_nearest_track(lay, curp.middle_unit, mode=0,
                                                        half_track=True, unit_mode=True)
                pidx = idxm + tr_pitch / 2
                nidx = idxm - tr_pitch / 2
                curp, curn = self.connect_differential_tracks(curp, curn, lay, pidx, nidx,
                                                              width=tr_w_clk)
                curp_list.append(curp)
                curn_list.append(curn)
            clkp_cur = curp_list
            clkn_cur = curn_list
        clkp = self.connect_wires(clkp_cur)[0]
        clkn = self.connect_wires(clkn_cur)[0]

        self.add_pin('clkp', clkp, label='clkp:', show=show_pins)
        self.add_pin('clkn', clkn, label='clkn:', show=show_pins)

        pidx = self.grid.coord_to_nearest_track(xm_layer, ent_y, half_track=True, mode=1,
                                                unit_mode=True)
        nidx = self.grid.coord_to_nearest_track(xm_layer, enb_y, half_track=True, mode=-1,
                                                unit_mode=True)
        tid = TrackID(xm_layer, nidx, width=tr_w_div)
        en = self.connect_to_tracks(dp_inst.get_all_port_pins('en_div'), tid, unit_mode=True)

        # connect en_div to M5 track
        ym_layer = xm_layer - 1
        ym_tidx = dp_inst.master.en_div_tidx
        ym_tidx = dp_inst.translate_master_track(ym_layer, ym_tidx)
        env, enh = self.connect_to_tracks(en, TrackID(ym_layer, ym_tidx), min_len_mode=True,
                                          return_wires=True)

        # add matching dummy divider wire
        self.add_wires(xm_layer, pidx, enh[0].lower_unit, enh[0].upper_unit,
                       width=tr_w_div, unit_mode=True)
        self.add_pin('enable_divider', env, show=show_pins)

        return clkp_tid, clkn_tid

    def _connect_supplies(self, tr_manager, xm_layer, dp_inst, sup_yc_list, vdd_wires,
                          vss_wires, hm_vdd, hm_vss, fill_box, fill_config, show_pins):
        # do power fill on CTLE region
        ym_layer = xm_layer - 1
        fw, fsp, sp, sple = fill_config[ym_layer]
        xl = fill_box.left_unit
        hm_vdd = self.extend_wires(hm_vdd, lower=xl, unit_mode=True)
        hm_vss = self.extend_wires(hm_vss, lower=xl, unit_mode=True)
        ym_vdd, ym_vss = self.do_power_fill(ym_layer, sp, sple, bound_box=fill_box,
                                            vdd_warrs=hm_vdd, vss_warrs=hm_vss,
                                            fill_width=fw, fill_space=fsp, unit_mode=True)
        ym_vdd.extend(vdd_wires)
        ym_vss.extend(vss_wires)

        tr_w_sup = tr_manager.get_width(xm_layer, 'sup')
        dp_box = dp_inst.bound_box
        y0 = dp_box.bottom_unit
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

            warr = self.add_wires(xm_layer, tidx, 0, xr, width=tr_w_sup, unit_mode=True)
            if idx % 2 == 0:
                self.draw_vias_on_intersections(ym_vss, warr)
                self.add_pin('VSS', warr, show=show_pins)
            else:
                self.draw_vias_on_intersections(ym_vdd, warr)
                self.add_pin('VDD', warr, show=show_pins)

        # re-export retimer VDD/VSS
        self.add_pin('VDD_re', dp_inst.get_all_port_pins('VDD_re'), label='VDD', show=False)
        self.add_pin('VSS_re', dp_inst.get_all_port_pins('VSS_re'), label='VSS', show=False)

    def _reexport_dp_pins(self, dp_inst, show_pins, export_probe):
        self.reexport(dp_inst.get_port('des_clk'), show=show_pins)
        self.reexport(dp_inst.get_port('des_clkb'), show=show_pins)
        for idx in range(4):
            suf = '<%d>' % idx
            self.reexport(dp_inst.get_port('data' + suf), show=show_pins)
            self.reexport(dp_inst.get_port('dlev' + suf), show=show_pins)

        if export_probe:
            for pin_name in dp_inst.port_names_iter():
                if pin_name.startswith('clk_'):
                    self.reexport(dp_inst.get_port(pin_name), show=True)

    def _connect_vdd_bias(self, hm_layer, x0, num_dfe, num_ffe, vdd_wires, dp_inst, y0,
                          bias_config, show_pins, pin_list, is_bot=True):
        wire_list = []
        name_list = []
        for port_name, out_name in self._vdd_ports_iter(num_dfe, num_ffe, is_bot=is_bot):
            wire_list.append(dp_inst.get_pin(port_name))
            name_list.append(out_name)

        if is_bot:
            self._bot_scan_names = scan_names = ['enable_divider', 'scan_divider_clkn']
        else:
            self._top_scan_names = scan_names = ['scan_divider_clkp']
            wire_list.reverse()
            name_list.reverse()
        x1 = self._buf_locs[0][0]
        bias_info = BiasShield.connect_bias_shields(self, hm_layer, bias_config, wire_list, y0,
                                                    tr_lower=x0, tr_upper=x1, lu_end_mode=1,
                                                    sup_warrs=vdd_wires, add_end=False,
                                                    extend_tracks=False)

        for name, tr in zip(name_list, bias_info.tracks):
            if name.startswith('bias'):
                scan_names.append(name)
                tr = self.extend_wires(tr, upper=x1, unit_mode=True)
                self.add_pin(name, tr, show=show_pins, edge_mode=1)

            else:
                pin_list.append((name, tr))

        return 1, len(wire_list), bias_info.p0[1]

    def _connect_clk_vss_bias(self, tr_manager, hm_layer, vss_wires, x0, ybot, ytop, dp_inst,
                              hpx_inst, hp1_inst, num_dfe, hp_h, clk_locs, clk_tr_w, clk_h, vss_h,
                              bias_config, show_pins, pin_list, top_layer, fill_config,
                              is_bot=True):
        ntr_tot = len(clk_locs)
        num_pair = (ntr_tot - 2) // 2
        vss_idx_lookup = {}
        vss_warrs_list = []
        vss_name_list = []

        vss_idx = 0
        pwarr = None
        if is_bot:
            tr0 = self.grid.find_next_track(hm_layer, ybot + hp_h, half_track=True, mode=1,
                                            unit_mode=True)
            sgn = 1
        else:
            tr0 = self.grid.find_next_track(hm_layer, ytop - hp_h, half_track=True, mode=-1,
                                            unit_mode=True)
            sgn = -1

        hpx_iter = self._hpx_ports_iter(num_dfe, is_bot=is_bot)
        hp1_iter = self._hp1_ports_iter(is_bot=is_bot)
        for inst, port_iter in ((hpx_inst, hpx_iter), (hp1_inst, hp1_iter)):
            for idx, (out_name, bias_name, _) in enumerate(port_iter):
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
            scan_name = 'scan_divider_clkn'
            scan_pins = dp_inst.get_all_port_pins('scan_div<3>')
            bot_tr = tr0 + clk_locs[0]
        else:
            scan_name = 'scan_divider_clkp'
            scan_pins = dp_inst.get_all_port_pins('scan_div<2>')
            bot_tr = tr0 - clk_locs[-1]
        vss_name_list.append(scan_name)
        vss_warrs_list.append(scan_pins)
        vss_tid = TrackID(hm_layer, bot_tr, width=1, num=2, pitch=abs(clk_locs[-1] - clk_locs[0]))

        _, vss_wires = self.connect_to_tracks(vss_wires, vss_tid, return_wires=True)
        if is_bot:
            vss_coord = vss_wires[0].lower_unit
            self.extend_wires(dp_inst.get_all_port_pins('VDD_ext'), lower=vss_coord, unit_mode=True)
            offset = ybot + hp_h + clk_h
        else:
            vss_name_list.reverse()
            vss_warrs_list.reverse()
            vss_coord = vss_wires[0].upper_unit
            self.extend_wires(dp_inst.get_all_port_pins('VDD_ext'), upper=vss_coord, unit_mode=True)
            offset = ytop - hp_h - clk_h - vss_h

        x1 = self._buf_locs[0][0]
        bias_info = BiasShield.connect_bias_shields(self, hm_layer, bias_config, vss_warrs_list,
                                                    offset, tr_lower=x0, tr_upper=x1, lu_end_mode=1,
                                                    add_end=False, extend_tracks=False)
        self.connect_to_track_wires(vss_wires, bias_info.shields)

        for name, tr in zip(vss_name_list, bias_info.tracks):
            if name.startswith('scan'):
                tr = self.extend_wires(tr, upper=x1, unit_mode=True)
                self.add_pin(name, tr, show=show_pins, edge_mode=1)
            else:
                pin_list.append((name, tr))

        # export clks
        clkp = self.connect_wires([hpx_inst.get_pin('clkp'), hp1_inst.get_pin('clkp')])[0]
        clkn = self.connect_wires([hpx_inst.get_pin('clkn'), hp1_inst.get_pin('clkn')])[0]
        xm_layer = clkp.layer_id
        h_mode = 1 if is_bot else -1
        for lay in range(xm_layer + 1, top_layer + 1):
            fill_tr_w, fill_tr_sp, _, _ = fill_config[lay]
            fill_pitch = fill_tr_w + fill_tr_sp
            tr_sp_clk = tr_manager.get_space(lay, ('clk', 'clk'))
            tr_w_clk = tr_manager.get_width(lay, 'clk')
            tr_pitch = int(round(2 * (tr_sp_clk + tr_w_clk)))
            tr_pitch = tr_pitch // 2 if tr_pitch % 2 == 0 else (tr_pitch + 1) // 2
            tr_pitch = max(tr_pitch, fill_pitch)
            if (lay - xm_layer) % 2 == 1:
                # vertical layer
                xl = clkp.lower_unit
                xr = clkp.upper_unit
                idx0 = self.grid.coord_to_nearest_fill_track(lay, xl, fill_config, mode=1,
                                                             unit_mode=True)
                idx1 = self.grid.coord_to_nearest_fill_track(lay, xr, fill_config, mode=-1,
                                                             unit_mode=True)
                curp_list = []
                curn_list = []
                num = int(round(idx1 - idx0)) // tr_pitch
                for cnt in range(0, num, 4):
                    idxp = idx0 + cnt * tr_pitch
                    curp, curn = self.connect_differential_tracks(clkp, clkn, lay, idxp,
                                                                  idxp + tr_pitch,
                                                                  width=tr_w_clk)
                    curp_list.append(curp)
                    curn_list.append(curn)
                clkp = curp_list
                clkn = curn_list
            else:
                coord = clkp[0].middle_unit
                midx = self.grid.coord_to_nearest_fill_track(lay, coord, fill_config,
                                                             mode=h_mode, unit_mode=True)
                pidx = midx - tr_pitch / 2
                nidx = midx + tr_pitch / 2
                clkp, clkn = self.connect_differential_tracks(clkp, clkn, lay, pidx, nidx,
                                                              width=tr_w_clk)

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
                ym_layer = hm_layer + 1
                tid = self.grid.coord_to_nearest_track(ym_layer, vssm.middle_unit, half_track=True,
                                                       unit_mode=True)
                self.connect_to_tracks([vss, vssm], TrackID(ym_layer, tid))
            else:
                self.connect_to_track_wires(vssm_list, vss)
        elif not vssm_list:
            raise ValueError('Cannot connect middle VSS of high-pass filters.')

        return 0, len(vss_warrs_list), bias_info.p0[1]

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

        yield ('clk_analog<%d>' % psuf, 'v_analog', 'analog')
        yield ('clk_analog<%d>' % nsufl, 'v_analog', 'analog')
        yield ('clk_main<%d>' % nsufa, 'v_way_%d_main' % nway, 'main_tapx')
        yield ('clk_main<%d>' % psuf, 'v_way_%d_main' % pway, 'main_tapx')

        idx = 0
        for dfe_idx in range(num_dfe, 1, -1):
            if dfe_idx == 3:
                # insert digital bias
                if idx % 2 == 0:
                    yield ('clk_digital_tapx<%d>' % psuf, 'v_digital', 'digital_tapx')
                    yield ('clk_digital_tapx<%d>' % nsufl, 'v_digital', 'digital_tapx')
                else:
                    yield ('clk_digital_tapx<%d>' % nsufl, 'v_digital', 'digital_tapx')
                    yield ('clk_digital_tapx<%d>' % psuf, 'v_digital', 'digital_tapx')
                idx += 1
            if idx % 2 == 0:
                yield ('clk_dfe<%d>' % (4 * dfe_idx + psuf), 'v_way_%d_dfe_%d_m' % (pway, dfe_idx),
                       'dfe_%d' % dfe_idx)
                yield ('clk_dfe<%d>' % (4 * dfe_idx + nsufa), 'v_way_%d_dfe_%d_m' % (nway, dfe_idx),
                       'dfe_%d' % dfe_idx)
            else:
                yield ('clk_dfe<%d>' % (4 * dfe_idx + nsufa), 'v_way_%d_dfe_%d_m' % (nway, dfe_idx),
                       'dfe_%d' % dfe_idx)
                yield ('clk_dfe<%d>' % (4 * dfe_idx + psuf), 'v_way_%d_dfe_%d_m' % (pway, dfe_idx),
                       'dfe_%d' % dfe_idx)
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

        yield ('clk_digital_tap1<%d>' % psuf, 'v_digital', 'digital_tap1')
        yield ('clk_digital_tap1<%d>' % nsufl, 'v_digital', 'digital_tap1')
        yield ('clk_tap1<%d>' % nsufa, 'v_tap1_main', 'main_tap1')
        yield ('clk_tap1<%d>' % psuf, 'v_tap1_main', 'main_tap1')
        yield ('clk_dfe<%d>' % (4 + psuf), 'v_way_%d_dfe_1_m' % pway, 'dfe_1')
        yield ('clk_dfe<%d>' % (4 + nsufa), 'v_way_%d_dfe_1_m' % nway, 'dfe_1')

    def _compute_route_height(self, hm_layer, blk_h, tr_manager, num_ffe, num_dfe, bias_config):
        num_clk_tr = 2

        # scan_div, ana, dig, tap1_main, int_main * 2, 2 * each DFE
        num_hm_vss = 6 + 2 * num_dfe
        # dlev, offset, 2 * each FFE, 4 * each DFE 2+ (sign bits)
        num_hm_vdd = 8 + 2 * num_ffe + 4 * (num_dfe - 1)
        # vincm, ana, dig, tap1_main, int_main * 4, 4 * each DFE
        num_vm_vss = 8 + 4 * num_dfe
        # dlev, offset, 4 * each FFE
        num_vm_vdd = 16 + 4 * num_ffe

        wtype_list = ['sh']
        wtype_list.extend(repeat('clk', 2 * num_clk_tr))
        wtype_list.append('sh')
        ntr, locs = tr_manager.place_wires(hm_layer, wtype_list)
        tr_pitch = self.grid.get_track_pitch(hm_layer, unit_mode=True)
        clk_h = -(-(int(round(tr_pitch * ntr))) // blk_h) * blk_h
        vdd_h = BiasShield.get_block_size(self.grid, hm_layer, bias_config, num_hm_vdd)[1]
        vss_h = BiasShield.get_block_size(self.grid, hm_layer, bias_config, num_hm_vss)[1]

        return locs, clk_h, vss_h, vdd_h, num_vm_vss, num_vm_vdd

    def _make_masters(self, tr_widths, tr_spaces):
        ctle_params = self.params['ctle_params']
        dp_params = self.params['dp_params']
        hp_params = self.params['hp_params']
        buf_params = self.params['scan_buf_params']
        cap_h_table = self.params['cap_h_table']
        tr_widths_dig = self.params['tr_widths_dig']
        tr_spaces_dig = self.params['tr_spaces_dig']

        ctle_params = ctle_params.copy()
        ctle_params['tr_widths'] = tr_widths
        ctle_params['tr_spaces'] = tr_spaces
        ctle_params['show_pins'] = False
        master_ctle = self.new_template(params=ctle_params, temp_cls=PassiveCTLE)

        dp_params = dp_params.copy()
        dp_params['scan_buf_params'] = buf_params
        dp_params['tr_widths'] = tr_widths
        dp_params['tr_spaces'] = tr_spaces
        dp_params['tr_widths_dig'] = tr_widths_dig
        dp_params['tr_spaces_dig'] = tr_spaces_dig
        dp_params['show_pins'] = False
        master_dp = self.new_template(params=dp_params, temp_cls=RXDatapath)
        self._retime_ncol = master_dp.retime_ncol
        num_dfe = master_dp.num_dfe

        hp_params = hp_params.copy()
        hp_params['narr'] = master_dp.num_hp_tapx
        hp_params['tr_widths'] = tr_widths
        hp_params['tr_spaces'] = tr_spaces
        hp_params['show_pins'] = False
        hp_params['cap_h_list'] = [cap_h_table[name]
                                   for _, _, name in self._hpx_ports_iter(num_dfe)]
        master_hpx = self.new_template(params=hp_params, temp_cls=HighPassArrayClk)

        hp_params['narr'] = master_dp.num_hp_tap1
        hp_params['cap_h_list'] = [cap_h_table[name]
                                   for _, _, name in self._hp1_ports_iter()]
        master_hp1 = self.new_template(params=hp_params, temp_cls=HighPassArrayClk)

        return master_ctle, master_dp, master_hpx, master_hp1


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
        self._bot_scan_names = None
        self._top_scan_names = None

    @property
    def sch_params(self):
        # type: () -> Dict[str, Any]
        return self._sch_params

    @property
    def bot_scan_names(self):
        # type: () -> List[str]
        return self._bot_scan_names

    @property
    def top_scan_names(self):
        # type: () -> List[str]
        return self._top_scan_names

    @classmethod
    def get_params_info(cls):
        # type: () -> Dict[str, str]
        return dict(
            term_params='Termination parameters.',
            fe_params='RX frontend parameters.',
            dac_params='RX DAC parameters.',
            top_layer='Top routing layer.',
            clk_tr_info='clock track information.',
            fill_config='fill configuration dictionary.',
            bias_config='bias configuration dictionary.',
            fill_orient_mode='fill orientation mode.',
            show_pins='True to show pins.',
        )

    @classmethod
    def get_default_param_values(cls):
        # type: () -> Dict[str, Any]
        return dict(
            clk_tr_info=None,
            fill_orient_mode=0,
            show_pins=True,
        )

    def draw_layout(self):
        top_layer = self.params['top_layer']
        clk_tr_info = self.params['clk_tr_info']
        fill_config = self.params['fill_config']
        bias_config = self.params['bias_config']
        show_pins = self.params['show_pins']

        master_term, master_fe, master_dac, master_bufb, master_buft = self._make_masters()
        box_term = master_term.bound_box
        box_fe = master_fe.bound_box
        box_dac = master_dac.bound_box

        xm_layer = master_fe.xm_layer
        hm_layer = xm_layer - 2
        w_term = box_term.width_unit
        h_term = box_term.height_unit
        w_fe = box_fe.width_unit
        h_fe = box_fe.height_unit
        w_dac = box_dac.width_unit
        h_dac = box_dac.height_unit
        w_tot = max(w_term + w_fe, w_dac)
        x_fe = w_tot - w_fe
        x_term = x_fe - w_term
        x_dac = w_tot - w_dac
        h_tot = h_fe + h_dac
        y_term = (h_fe - h_term) // 2

        inst_term = self.add_instance(master_term, 'XTERM', loc=(x_term, y_term), unit_mode=True)
        inst_fe = self.add_instance(master_fe, 'XFE', loc=(x_fe, 0), unit_mode=True)
        inst_dac = self.add_instance(master_dac, 'XDAC', loc=(x_dac, h_tot), orient='MX',
                                     unit_mode=True)
        buf_loc = (master_fe.buf_locs[0][0] + x_fe, master_fe.buf_locs[0][1])
        inst_bufb = self.add_instance(master_bufb, 'XBUFB', loc=buf_loc, orient='MX',
                                      unit_mode=True)
        buf_loc = (master_fe.buf_locs[1][0] + x_fe, master_fe.buf_locs[1][1])
        inst_buft = self.add_instance(master_buft, 'XBUFT', loc=buf_loc, unit_mode=True)

        bnd_box = inst_dac.bound_box.extend(x=0, y=0, unit_mode=True)
        self.set_size_from_bound_box(top_layer, bnd_box)
        self.array_box = bnd_box
        self.add_cell_boundary(bnd_box)

        self._connect_fe(top_layer, inst_fe, clk_tr_info, show_pins)
        self._connect_term(inst_term, inst_fe, show_pins)

        self._bot_scan_names = bot_scan_names = master_fe.bot_scan_names
        self._top_scan_names = top_scan_names = master_fe.top_scan_names
        self._connect_buffers(hm_layer, inst_fe, inst_bufb, inst_buft, bot_scan_names,
                              top_scan_names, show_pins)

        self._connect_bias_routes(hm_layer, inst_fe, inst_dac, h_fe, bias_config)

        # re-export DAC pins
        for name in inst_dac.port_names_iter():
            if name.startswith('bias_'):
                self.reexport(inst_dac.get_port(name), show=show_pins)

        self._power_fill(fill_config, top_layer, xm_layer, inst_fe, inst_term, inst_dac, show_pins)

        self._sch_params = dict(
            term_params=master_term.sch_params,
            fe_params=master_fe.sch_params,
            dac_params=master_dac.sch_params,
            bufb_params=master_bufb.sch_params,
            buft_params=master_buft.sch_params,
        )

    def _power_fill(self, fill_config, top_layer, xm_layer, inst_fe, inst_term,
                    inst_dac, show_pins):
        fill_orient_mode = self.params['fill_orient_mode']

        vdd = list(chain(inst_fe.port_pins_iter('VDD'), inst_term.port_pins_iter('VDD')))
        vss = list(chain(inst_fe.port_pins_iter('VSS'), inst_term.port_pins_iter('VSS')))
        bnd_box = inst_fe.bound_box.merge(inst_term.bound_box)

        if top_layer > xm_layer:
            sp = 800
            flip = fill_orient_mode & 1 != 0
            vdd, vss = self.do_power_fill(xm_layer + 1, sp, sp, vdd_warrs=vdd, vss_warrs=vss,
                                          bound_box=bnd_box, fill_width=3, fill_space=3,
                                          flip=flip, unit_mode=True)
            bnd_box = bnd_box.extend(x=0, unit_mode=True)
            for lay in range(xm_layer + 2, top_layer + 1):
                if (lay - xm_layer) % 2 == 0:
                    flip = fill_orient_mode & 2 != 0
                else:
                    flip = fill_orient_mode & 1 != 0
                tr_w, tr_sp, sp, sp_le = fill_config[lay]
                vdd, vss = self.do_power_fill(lay, sp, sp_le, vdd_warrs=vdd, vss_warrs=vss,
                                              bound_box=bnd_box, fill_width=tr_w,
                                              fill_space=tr_sp, flip=flip, unit_mode=True)

        if inst_dac.master.top_layer < top_layer:
            params = dict(fill_config=fill_config, bot_layer=top_layer - 1, show_pins=False)
            fill_master = self.new_template(params=params, temp_cls=PowerFill)
            fill_box = fill_master.bound_box
            dac_box = inst_dac.bound_box
            x = 0
            y = dac_box.bottom_unit
            blk_w = fill_box.width_unit
            blk_h = fill_box.height_unit
            nx = dac_box.right_unit // blk_w
            ny = dac_box.height_unit // blk_h
            if fill_orient_mode & 2 != 0:
                y += blk_h
            if fill_orient_mode & 1 != 0:
                x += blk_w
            orient = PowerFill.get_fill_orient(fill_orient_mode)
            inst = self.add_instance(fill_master, loc=(x, y), nx=nx, ny=ny, spx=blk_w, spy=blk_h,
                                     orient=orient, unit_mode=True)
            vdd_dac = self.connect_wires(inst.get_all_port_pins('VDD'))
            vss_dac = self.connect_wires(inst.get_all_port_pins('VSS'))
            vdd.extend(vdd_dac)
            vss.extend(vss_dac)
        else:
            vdd.extend(inst_dac.port_pins_iter('VDD'))
            vss.extend(inst_dac.port_pins_iter('VSS'))

        self.add_pin('VDD', vdd, label='VDD:', show=show_pins)
        self.add_pin('VSS', vss, label='VSS:', show=show_pins)

    def _connect_term(self, inst_term, inst_fe, show_pins):
        inp = inst_term.get_pin('inp')
        inn = inst_term.get_pin('inn')
        inp = self.extend_wires(inp, lower=0, unit_mode=True)
        inn = self.extend_wires(inn, lower=0, unit_mode=True)
        self.add_pin('inp', inp, show=show_pins)
        self.add_pin('inn', inn, show=show_pins)
        self.connect_wires([inst_term.get_pin('outp'), inst_fe.get_pin('inp')])
        self.connect_wires([inst_term.get_pin('outn'), inst_fe.get_pin('inn')])

    def _connect_bias_routes(self, hm_layer, inst_fe, inst_dac, y_dac, bias_config):
        x_fe = inst_fe.location_unit[0]
        x_dac = inst_dac.location_unit[0]
        master_dac = inst_dac.master
        (x_vdd, vdd_names), (x_vss, vss_names) = master_dac.bias_info
        x_vdd += x_dac
        x_vss += x_dac

        # make corner masters
        vm_layer = hm_layer - 1
        ym_layer = hm_layer + 1
        num_vss = len(vss_names)
        num_vdd = len(vdd_names)
        vss_params = dict(
            nwire=num_vss,
            width=1,
            space_sig=0,
        )
        vdd_params = dict(
            nwire=num_vdd,
            width=1,
            space_sig=0,
        )
        vssc_params = dict(
            bot_layer=vm_layer,
            bias_config=bias_config,
            bot_params=vss_params,
            top_params=vss_params,
        )
        vddc_params = dict(
            bot_layer=vm_layer,
            bias_config=bias_config,
            bot_params=vdd_params,
            top_params=vdd_params,
        )
        master_vssc = self.new_template(params=vssc_params, temp_cls=BiasShieldJoin)
        master_vddc = self.new_template(params=vddc_params, temp_cls=BiasShieldJoin)
        arr_box_vssc = master_vssc.array_box
        h_end = master_vssc.bound_box.top_unit - arr_box_vssc.top_unit
        y_vssc = y_dac - h_end
        y_vddc = y_vssc - master_vssc.bound_box.height_unit
        for master, x, yt, num, names in ((master_vssc, x_vss, y_vssc, num_vss, vss_names),
                                          (master_vddc, x_vdd, y_vddc, num_vdd, vdd_names)):
            arr_box = master.array_box
            warr = arr_box.width_unit
            harr = arr_box.height_unit
            xr = x + warr
            inst = self.add_instance(master, loc=(xr, yt), orient='R180', unit_mode=True)
            sup_ym = self.extend_wires(inst.get_all_port_pins('sup', layer=ym_layer),
                                       upper=y_dac, unit_mode=True)
            sup_hm, _ = BiasShield.draw_bias_shields(self, vm_layer, bias_config, num, x,
                                                     yt, y_dac, check_blockage=False)
            self.draw_vias_on_intersections(sup_hm, sup_ym)

            yb = yt - harr
            BiasShield.draw_bias_shields(self, hm_layer, bias_config, num, yb,
                                         xr, x_fe, check_blockage=False)
            for name in names:
                pin_dac = inst_dac.get_pin(name)
                pin_fe = inst_fe.get_pin(name)
                self.connect_to_track_wires(pin_dac, pin_fe)

    def _connect_fe(self, top_layer, inst_fe, clk_tr_info, show_pins):
        for name in ['des_clk', 'des_clkb']:
            self.reexport(inst_fe.get_port(name), show=show_pins)

        clkp = inst_fe.get_all_port_pins('clkp')
        clkn = inst_fe.get_all_port_pins('clkn')
        if clk_tr_info is None:
            self.add_pin('clkp', clkp, label='clkp:', show=show_pins)
            self.add_pin('clkn', clkn, label='clkn:', show=show_pins)
        else:
            pidx, nidx, tr_w = clk_tr_info
            clkp, clkn = self.connect_differential_tracks(clkp, clkn, top_layer + 1, pidx, nidx,
                                                          width=tr_w)
            self.add_pin('clkp', clkp, show=show_pins)
            self.add_pin('clkn', clkn, show=show_pins)

        for idx in range(4):
            suf = '<%d>' % idx
            self.reexport(inst_fe.get_port('data' + suf), show=show_pins)
            self.reexport(inst_fe.get_port('dlev' + suf), show=show_pins)

    def _connect_buffers(self, hm_layer, inst_fe, inst_bufb, inst_buft, bot_names, top_names,
                         show_pins):
        # connect supplies
        vdd = inst_fe.get_pin('VDD_re')
        vss = inst_fe.get_pin('VSS_re')
        vdd_list = list(chain(inst_bufb.port_pins_iter('VDD'), inst_buft.port_pins_iter('VDD')))
        vss_list = list(chain(inst_bufb.port_pins_iter('VSS'), inst_buft.port_pins_iter('VSS')))
        self.connect_to_track_wires(vdd_list, vdd)
        self.connect_to_track_wires(vss_list, vss)

        # connect signals
        for inst, names in ((inst_bufb, bot_names), (inst_buft, top_names)):
            for idx, name in enumerate(names):
                pin = inst_fe.get_pin(name)
                cur_out = inst.get_pin('out<%d>' % idx)
                if name == 'enable_divider':
                    hm_tidx = self.grid.coord_to_nearest_track(hm_layer, cur_out.middle_unit,
                                                               half_track=True, unit_mode=True)
                    self.connect_to_tracks([cur_out, pin], TrackID(hm_layer, hm_tidx),
                                           min_len_mode=1)
                else:
                    self.connect_to_track_wires(cur_out, pin)
                cur_pin = self.extend_wires(inst.get_pin('in<%d>' % idx),
                                            unit_mode=True, min_len_mode=1)
                self.add_pin(name, cur_pin, show=show_pins)

    def _make_masters(self):
        term_params = self.params['term_params'].copy()
        fe_params = self.params['fe_params'].copy()
        dac_params = self.params['dac_params'].copy()
        top_layer = self.params['top_layer']
        fconf = self.params['fill_config']
        bias_config = self.params['bias_config']
        fill_orient_mode = self.params['fill_orient_mode']

        term_params['fill_config'] = fe_params['fill_config'] = dac_params['fill_config'] = fconf
        fe_params['bias_config'] = dac_params['bias_config'] = bias_config
        dac_params['fill_orient_mode'] = fill_orient_mode ^ 2
        term_params['show_pins'] = fe_params['show_pins'] = dac_params['show_pins'] = False
        term_params['top_layer'] = fe_params['top_layer'] = top_layer

        master_fe = self.new_template(params=fe_params, temp_cls=RXFrontend)

        if top_layer == master_fe.xm_layer:
            dac_params['top_layer'] = top_layer
        else:
            dac_params['top_layer'] = top_layer - 1
        master_dac = self.new_template(params=dac_params, temp_cls=RDACArray)

        in_tid = master_fe.get_port('inp').get_pins()[0].track_id
        tr_off = self.grid.coord_to_track(in_tid.layer_id, master_fe.bound_box.height_unit // 2,
                                          unit_mode=True)
        term_params['cap_out_tid'] = (in_tid.base_index - tr_off - 0.5, in_tid.width)
        master_term = self.new_template(params=term_params, temp_cls=TermRX)

        buf_params = fe_params['scan_buf_params'].copy()
        buf_params['config'] = fe_params['dp_params']['config']
        buf_params['tr_widths'] = fe_params['tr_widths_dig']
        buf_params['tr_spaces'] = fe_params['tr_spaces_dig']
        buf_params['ncol_min'] = master_fe.retime_ncol
        buf_params['show_pins'] = False
        master_buft = self.new_template(params=buf_params, temp_cls=BufferArray)
        nbuf_list2 = list(buf_params['nbuf_list'])
        nbuf_list2[-1] += 1
        buf_params['nbuf_list'] = nbuf_list2
        master_bufb = self.new_template(params=buf_params, temp_cls=BufferArray)

        return master_term, master_fe, master_dac, master_bufb, master_buft
