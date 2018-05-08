# -*- coding: utf-8 -*-

"""This module defines classes needed to build the Hybrid-QDR FFE/DFE summer."""

from typing import TYPE_CHECKING, Dict, Any, Set

from itertools import repeat

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
        ml = 30000

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
        tot_w = -(-(bnd_box.width_unit + ml) // blk_w) * blk_w
        tot_h = -(-(dp_h + 2 * bot_h) // blk_h) * blk_h
        x0 = tot_w - bnd_box.width_unit
        y0 = (tot_h - dp_h) // (2 * blk_h) * blk_h
        dp_inst = self.add_instance(dp_master, 'XDP', loc=(x0, y0), unit_mode=True)
        x_hpx = x0 + dp_master.x_tapx[1] - hpx_w
        x_hp1 = max(x_hpx + hpx_w, x0 + dp_master.x_tap1[1] - hp1_w)
        hpx_inst = self.add_instance(hpx_master, 'XHPXB', loc=(x_hpx, 0), unit_mode=True)
        hp1_inst = self.add_instance(hp1_master, 'XHP1B', loc=(x_hp1, 0), unit_mode=True)

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

        # connect clocks and VSS-referenced wires
        num_dfe = dp_master.num_dfe
        hm_layer = top_layer - 1
        clk_tr_w = tr_manager.get_width(hm_layer, 'clk')
        self._connect_clk_vss_bias(hm_layer, dp_inst, hpx_inst, hp1_inst, num_dfe, hp_h, clk_locs,
                                   clk_tr_w, clk_h, bias_config, show_pins, is_bot=True)

        # gather VDD-referenced wires
        vdd_wires = dp_inst.get_all_port_pins('VDD', layer=top_layer)
        vdd_wires.extend(dp_inst.port_pins_iter('VDD', layer=top_layer - 2))
        self._connect_vdd_bias(vdd_wires, dp_inst)

        self._sch_params = dp_master.sch_params.copy()

    def _connect_vdd_bias(self, vdd_wires, dp_inst):
        pass

    def _connect_clk_vss_bias(self, hm_layer, dp_inst, hpx_inst, hp1_inst, num_dfe, y0, clk_locs,
                              clk_tr_w, clk_h, bias_config, show_pins, is_bot=True):
        ntr_tot = len(clk_locs)
        num_pair = (ntr_tot - 2) // 2
        vss_idx_lookup = {}
        vss_warrs_list = []
        vss_names_list = []

        vss_idx = 0
        pwarr = None
        tr0 = self.grid.find_next_track(hm_layer, y0, half_track=True, mode=1, unit_mode=True)
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
                    pidx = clk_locs[1 + cur_tr_id] + tr0
                    nidx = clk_locs[ntr_tot - 2 - cur_tr_id] + tr0
                    self.connect_differential_tracks(pwarr, nwarr, hm_layer, pidx, nidx,
                                                     width=clk_tr_w, unit_mode=True)

                bias_pin = inst.get_pin('bias' + suf)
                if bias_name not in vss_idx_lookup:
                    vss_names_list.append(bias_name)
                    vss_idx_lookup[bias_name] = vss_idx
                    vss_warrs_list.append([bias_pin])
                    vss_idx += 1
                else:
                    vss_warrs_list[vss_idx_lookup[bias_name]].append(bias_pin)

        if is_bot:
            scan_name = 'scan_divider_clkp'
            scan_pins = dp_inst.get_all_port_pins('scan_div<3>')
        else:
            scan_name = 'scan_divider_clkn'
            scan_pins = dp_inst.get_all_port_pins('scan_div<2>')
        vss_names_list.append(scan_name)
        vss_warrs_list.append(scan_pins)

        vss_tid = TrackID(hm_layer, tr0 + clk_locs[0], width=1, num=2,
                          pitch=clk_locs[-1] - clk_locs[0])

        vss_wires = dp_inst.get_all_port_pins('VSS')
        _, vss_wires = self.connect_to_tracks(vss_wires, vss_tid, return_wires=True)
        vss_lower = vss_wires[0].lower_unit
        self.extend_wires(dp_inst.get_all_port_pins('VDD_ext'), lower=vss_lower, unit_mode=True)
        bias_info = BiasShield.draw_bias_shields(self, hm_layer, bias_config, vss_warrs_list,
                                                 y0 + clk_h, lu_end_mode=1)
        self.draw_vias_on_intersections(bias_info.shields, vss_wires)

        for name, tr in zip(vss_names_list, bias_info.tracks):
            self.add_pin(name, tr, show=show_pins, edge_mode=-1)

    @classmethod
    def _vdd_ports_iter(cls, num_dfe, is_bot=True):
        if is_bot:
            nway = psuf = 3
            pway = nsufl = 0
            nsufa = 2
        else:
            nway = psuf = 1
            pway = nsufl = 2
            nsufa = 0

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
