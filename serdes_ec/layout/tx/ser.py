# -*- coding: utf-8 -*-

"""This module defines layout generator for the TX serializer."""

from typing import TYPE_CHECKING, Dict, Set, Any

from itertools import chain

import yaml

from bag.layout.util import BBox
from bag.layout.routing.base import TrackID, TrackManager
from bag.layout.template import TemplateBase, BlackBoxTemplate

from ..qdr_hybrid.sampler import DividerColumn

if TYPE_CHECKING:
    from bag.layout.template import TemplateDB


class Serializer32(TemplateBase):
    """32-to-1 serializer built with primitives.

    Parameters
    ----------
    temp_db : :class:`bag.layout.template.TemplateDB`
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
        TemplateBase.__init__(self, temp_db, lib_name, params, used_names, **kwargs)
        self._sch_params = None

    @property
    def sch_params(self):
        return self._sch_params

    @classmethod
    def get_params_info(cls):
        return dict(
            ser16_fname='16-to-1 serializer configuration file.',
            mux_fname='2-to-1 mux configuration file.',
            div_params='divider parameters.',
            tr_widths='Track width dictionary.',
            tr_spaces='Track spacing dictionary.',
            fill_config='fill configuration dictionary.',
            sup_margin='supply margin, in resolution units.',
            show_pins='True to draw pin layouts.',
        )

    @classmethod
    def get_default_param_values(cls):
        return dict(
            sup_margin=200,
            show_pins=True,
        )

    def draw_layout(self):
        tr_widths = self.params['tr_widths']
        tr_spaces = self.params['tr_spaces']
        fill_config = self.params['fill_config']
        sup_margin = self.params['sup_margin']
        show_pins = self.params['show_pins']

        tr_manager = TrackManager(self.grid, tr_widths, tr_spaces, half_space=True)

        # make masters and get information
        master_ser, master_mux, master_div = self._make_masters()
        hm_layer = master_ser.top_layer
        top_layer = ym_layer = hm_layer + 1
        box_ser = master_ser.bound_box
        box_mux = master_mux.bound_box
        box_div = master_div.bound_box
        h_ser = box_ser.height_unit
        h_div = box_div.height_unit
        h_mux = box_mux.height_unit

        # compute horizontal placement
        w_blk, h_blk = self.grid.get_block_size(top_layer, unit_mode=True)
        ym_pitch = self.grid.get_track_pitch(ym_layer, unit_mode=True)
        ntr, en_locs = tr_manager.place_wires(ym_layer, ['sh', 'clk', 'clk', 'sh'])
        w_en = ntr * ym_pitch
        ntr, clk_locs = tr_manager.place_wires(ym_layer, ['clk', 'sh', 'clk', 'clk', 'sh',
                                                          'sig', 'sig'])
        w_clk = ntr * ym_pitch
        x_ser = 0
        x_en = x_ser + box_ser.width_unit
        x_div = -(-(x_en + w_en) // w_blk) * w_blk
        x_clk = x_div + box_div.width_unit
        x_mux = -(-(x_clk + w_clk) // w_blk) * w_blk
        w_tot = x_mux + box_mux.width_unit
        w_tot = -(-w_tot // w_blk) * w_blk

        # compute vertical placement
        h_tot = max(2 * h_ser, h_div, h_mux)
        y_div = (h_tot - h_div) // 2
        y_mux = (h_tot - h_mux) // 2

        # place masters
        inst_serb = self.add_instance(master_ser, 'XSERB', loc=(x_ser, 0), unit_mode=True)
        inst_sert = self.add_instance(master_ser, 'XSERT', loc=(x_ser, h_tot), orient='MX',
                                      unit_mode=True)
        inst_div = self.add_instance(master_div, 'XDIV', loc=(x_div, y_div), unit_mode=True)
        inst_mux = self.add_instance(master_mux, 'XMUX', loc=(x_mux, y_mux), unit_mode=True)

        # set size
        res = self.grid.resolution
        self.array_box = bnd_box = BBox(0, 0, w_tot, h_tot, res, unit_mode=True)
        self.set_size_from_bound_box(top_layer, bnd_box)
        self.add_cell_boundary(bnd_box)

        self._connect_ser(inst_serb, inst_sert, show_pins)

        tmp = self._connect_ser_div(ym_layer, tr_manager, inst_serb, inst_sert,
                                    inst_div, x_en, en_locs)
        vddo_list, vsso_list, vddi_list, vssi_list = tmp
        self._connect_ser_div_mux(ym_layer, tr_manager, inst_serb, inst_sert, inst_div, inst_mux,
                                  x_clk, clk_locs, vddo_list, vsso_list, vddi_list, vssi_list,
                                  show_pins)

        self._connect_supplies(ym_layer, vddo_list, vsso_list, vddi_list, vssi_list, sup_margin,
                               fill_config, show_pins)

        self._sch_params = dict(
            ser_params=master_ser.sch_params,
            mux_params=master_mux.sch_params,
            div_params=master_div.sch_params,
        )

    def _connect_supplies(self, ym_layer, vddo_list, vsso_list, vddi_list, vssi_list, sup_margin,
                          fill_config, show_pins):
        xr = self.bound_box.right_unit - sup_margin
        vddo_list = self.extend_wires(vddo_list, upper=xr, unit_mode=True)
        vsso_list = self.extend_wires(vsso_list, upper=xr, unit_mode=True)

        vddo_list.extend(vddi_list)
        vsso_list.extend(vssi_list)

        tr_w, tr_sp, sp, sp_le = fill_config[ym_layer]
        vdd, vss = self.do_power_fill(ym_layer, sp, sp_le, vdd_warrs=vddo_list, vss_warrs=vsso_list,
                                      fill_width=tr_w, fill_space=tr_sp, x_margin=sup_margin,
                                      y_margin=sup_margin, unit_mode=True)
        self.add_pin('VDD', vdd, show=show_pins)
        self.add_pin('VSS', vss, show=show_pins)

    def _connect_ser_div_mux(self, ym_layer, tr_manager, serb, sert, div, mux, x0, clk_locs,
                             vddo_list, vsso_list, vddi_list, vssi_list, show_pins):
        # get track locations
        ym_w_clk = tr_manager.get_width(ym_layer, 'clk')
        ym_w_sh = tr_manager.get_width(ym_layer, 'sh')
        ym_w_sig = tr_manager.get_width(ym_layer, 'sig')
        tr0 = self.grid.find_next_track(ym_layer, x0, half_track=True, unit_mode=True)
        en2_tid = TrackID(ym_layer, tr0 + clk_locs[0], width=ym_w_clk)
        sh_tid = TrackID(ym_layer, tr0 + clk_locs[1], width=ym_w_sh, num=2,
                         pitch=clk_locs[4] - clk_locs[1])
        out0_tid = TrackID(ym_layer, tr0 + clk_locs[5], width=ym_w_sig)
        out1_tid = TrackID(ym_layer, tr0 + clk_locs[6], width=ym_w_sig)

        # connect clocks
        pidx = tr0 + clk_locs[2]
        nidx = tr0 + clk_locs[3]
        clkp = list(chain(div.port_pins_iter('clkp'), mux.port_pins_iter('clkp')))
        clkn = list(chain(div.port_pins_iter('clkn'), mux.port_pins_iter('clkn')))
        clkp, clkn = self.connect_differential_tracks(clkp, clkn, ym_layer, pidx, nidx,
                                                      width=ym_w_clk)
        self.add_pin('clkp', clkp, show=show_pins)
        self.add_pin('clkn', clkn, show=show_pins)

        # draw shield connections
        mux_yb, mux_yt = mux.bound_box.get_interval('y', unit_mode=True)
        for name, o_list, i_list in (('VDD', vddo_list, vddi_list), ('VSS', vsso_list, vssi_list)):
            for warr in div.port_pins_iter(name):
                yb, yt = warr.track_id.get_bounds(self.grid, unit_mode=True)
                if yt < mux_yb or yb > mux_yt:
                    o_list.append(warr)
                else:
                    i_list.append(warr)

        # connect seriailzier to mux
        self.connect_to_tracks([serb.get_pin('out'), mux.get_pin('data0')], out0_tid)
        self.connect_to_tracks([sert.get_pin('out'), mux.get_pin('data1')], out1_tid)

        # export mux
        self.reexport(mux.get_port('outp'), show=show_pins)
        self.reexport(mux.get_port('outn'), show=show_pins)

        # gather mux supplies
        vddi_list.extend(mux.port_pins_iter('VDD'))
        vssi_list.extend(mux.port_pins_iter('VSS'))

        scan_list = [div.get_pin('scan_div<3>'), div.get_pin('scan_div<2>')]
        self.connect_to_tracks(scan_list, sh_tid)
        self.connect_to_tracks(vsso_list, sh_tid)

        # draw en2 connections
        self.connect_to_tracks(div.get_all_port_pins('en2'), en2_tid)

    def _connect_ser_div(self, ym_layer, tr_manager, serb, sert, div, x0, clk_locs):
        # get track locations
        ym_w_clk = tr_manager.get_width(ym_layer, 'clk')
        ym_w_sh = tr_manager.get_width(ym_layer, 'sh')
        tr0 = self.grid.find_next_track(ym_layer, x0, half_track=True, unit_mode=True)
        sh_tid = TrackID(ym_layer, tr0 + clk_locs[0], width=ym_w_sh, num=2,
                         pitch=clk_locs[3] - clk_locs[0])
        pidx = tr0 + clk_locs[1]
        nidx = tr0 + clk_locs[2]

        # connect clocks
        pwarrs = [serb.get_pin('clk'), sert.get_pin('clk'), div.get_pin('en<2>')]
        nwarrs = [serb.get_pin('clkb'), sert.get_pin('clkb'), div.get_pin('en<0>')]
        self.connect_differential_tracks(pwarrs, nwarrs, ym_layer, pidx, nidx, width=ym_w_clk)

        # draw shield connections
        div_yb, div_yt = div.bound_box.get_interval('y', unit_mode=True)
        vddo_list = []
        vsso_list = []
        vddi_list = []
        vssi_list = []
        for name, o_list, i_list in (('VDD', vddo_list, vddi_list), ('VSS', vsso_list, vssi_list)):
            for warr in chain(serb.port_pins_iter(name), sert.port_pins_iter(name)):
                yb, yt = warr.track_id.get_bounds(self.grid, unit_mode=True)
                if yt < div_yb or yb > div_yt:
                    o_list.append(warr)
                else:
                    i_list.append(warr)

        self.connect_to_tracks(vsso_list, sh_tid)

        return vddo_list, vsso_list, vddi_list, vssi_list

    def _connect_ser(self, serb, sert, show_pins):
        # connect reset
        if serb.has_port('rst_vm'):
            self.connect_wires([serb.get_pin('rst_vm'), sert.get_pin('rst_vm')])
        else:
            portb = serb.get_port('rst_vm')
            layer = portb.get_single_layer()
            box1 = portb.get_pins(layer)[0]
            box2 = sert.get_pin('rst_vm')
            self.add_rect(layer, box1.merge(box2))

        # export reset/divclk/inputs
        self.reexport(serb.get_port('rst'), net_name='ser_reset', show=show_pins)
        self.reexport(serb.get_port('divclk'), net_name='clock_tx_div', show=show_pins)

        for idx in range(16):
            port_name = 'in<%d>' % idx
            self.reexport(serb.get_port(port_name), net_name='data_tx<%d>' % (idx * 2),
                          show=show_pins)
            self.reexport(sert.get_port(port_name), net_name='data_tx<%d>' % (idx * 2 + 1),
                          show=show_pins)

    def _make_masters(self):
        ser16_fname = self.params['ser16_fname']
        mux_fname = self.params['mux_fname']
        div_params = self.params['div_params']
        tr_widths = self.params['tr_widths']
        tr_spaces = self.params['tr_spaces']

        with open(ser16_fname, 'r') as f:
            ser_params = yaml.load(f)
        with open(mux_fname, 'r') as f:
            mux_params = yaml.load(f)

        ser_params['show_pins'] = False
        master_ser = self.new_template(params=ser_params, temp_cls=BlackBoxTemplate)

        mux_params['show_pins'] = False
        master_mux = self.new_template(params=mux_params, temp_cls=BlackBoxTemplate)

        div_params['show_pins'] = False
        div_params['tr_widths'] = tr_widths
        div_params['tr_spaces'] = tr_spaces
        master_div = self.new_template(params=div_params, temp_cls=DividerColumn)

        return master_ser, master_mux, master_div
