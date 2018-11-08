# -*- coding: utf-8 -*-

"""This module defines layout generator for the TX datapath."""

from typing import TYPE_CHECKING, Dict, Set, Any

from itertools import chain

import yaml

from bag.layout.util import BBox
from bag.layout.routing.base import TrackID, TrackManager
from bag.layout.template import TemplateBase, BlackBoxTemplate

from abs_templates_ec.analog_mos.mos import DummyFillActive

from ..analog.cml import CMLAmpPMOS
from .ser import Serializer32

if TYPE_CHECKING:
    from bag.layout.template import TemplateDB


class TXDatapath(TemplateBase):
    """TX datapath, which consists of serializer and output driver.

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
            esd_fname='ESD diode configuration file name.',
            ser_params='serializer parameters.',
            amp_params='amplifier parameters.',
            tr_widths='Track width dictionary.',
            tr_spaces='Track spacing dictionary.',
            fill_config='fill configuration dictionary.',
            show_pins='True to draw pin layouts.',
        )

    @classmethod
    def get_default_param_values(cls):
        return dict(
            show_pins=True,
        )

    def draw_layout(self):
        tr_widths = self.params['tr_widths']
        tr_spaces = self.params['tr_spaces']
        show_pins = self.params['show_pins']

        tr_manager = TrackManager(self.grid, tr_widths, tr_spaces, half_space=True)

        # make masters and get information
        master_ser, master_amp, master_esd = self._make_masters()
        ym_layer = master_ser.top_layer
        hm_layer = ym_layer - 1
        top_layer = master_amp.top_layer
        box_ser = master_ser.bound_box
        box_amp = master_amp.bound_box
        box_esd = master_esd.bound_box
        h_ser = box_ser.height_unit
        h_amp = box_amp.height_unit
        h_esd = box_esd.height_unit

        # draw fill between CML amplifier and diode so we meet DRC rule
        mos_type = 'nch'
        threshold = master_amp.params['gm_params']['threshold']
        fill_space = DummyFillActive.get_min_fill_dim(self.grid.tech_info, mos_type, threshold)[0]
        w_blk, h_blk = self.grid.get_block_size(top_layer, unit_mode=True)
        w_fill = -(-fill_space // w_blk) * w_blk
        dum_params = dict(
            mos_type=mos_type,
            threshold=threshold,
            width=w_fill,
            height=h_amp,
        )
        master_fill = self.new_template(params=dum_params, temp_cls=DummyFillActive)

        # allocate space for ibias routing
        em_specs = master_amp.ibias_em_specs
        hm_tr_w_ibias = master_amp.get_port('ibias').get_pins()[0].width
        bot_w = self.grid.get_track_width(hm_layer, hm_tr_w_ibias, unit_mode=True)
        ym_tr_w_ibias = self.grid.get_min_track_width(ym_layer, bot_w=bot_w, unit_mode=True,
                                                      **em_specs)
        ntr, ibias_locs = tr_manager.place_wires(ym_layer, ['sh', ym_tr_w_ibias, 'sh'])
        ym_pitch = self.grid.get_track_pitch(ym_layer, unit_mode=True)
        w_route = ym_pitch * ntr

        # compute horizontal placement
        x_ser = 0
        x_route = x_ser + box_ser.width_unit
        x_amp = -(-(x_route + w_route) // w_blk) * w_blk
        x_fill = x_amp + box_amp.width_unit
        x_esd = x_amp + box_amp.width_unit + w_fill
        w_tot = -(-(x_esd + box_esd.width_unit) // w_blk) * w_blk

        # compute vertical placement
        h_tot = -(-max(h_ser, h_amp, 2 * h_esd) // h_blk) * h_blk
        y_ser = (h_tot - h_ser) // 2
        y_amp = (h_tot - h_amp) // 2
        y_esd = h_tot // 2

        # place masters
        ser = self.add_instance(master_ser, 'XSER', loc=(x_ser, y_ser), unit_mode=True)
        amp = self.add_instance(master_amp, 'XAMP', loc=(x_amp, y_amp), unit_mode=True)
        esdt = self.add_instance(master_esd, 'XESDT', loc=(x_esd, y_esd), unit_mode=True)
        esdb = self.add_instance(master_esd, 'XESDB', loc=(x_esd, y_esd), orient='MX',
                                 unit_mode=True)
        self.add_instance(master_fill, 'XFILL', loc=(x_fill, y_amp), unit_mode=True)

        # set size
        res = self.grid.resolution
        self.array_box = bnd_box = BBox(0, 0, w_tot, h_tot, res, unit_mode=True)
        self.set_size_from_bound_box(top_layer, bnd_box)
        self.add_cell_boundary(bnd_box)

        # draw connections
        sh_warrs = self._connect_ser_amp(ym_layer, tr_manager, ser, amp, x_route, ibias_locs,
                                         ym_tr_w_ibias, show_pins)

        vdd, vss = self._connect_ser_esd(amp, esdb, esdt, show_pins)

        self.add_pin('VDD', vdd, label='VDD:', show=show_pins)
        self.add_pin('VSS', vss, label='VSS:', show=show_pins)
        self.add_pin('VDD', sh_warrs, label='VDD:', show=show_pins)

        # schematic parameters
        self._sch_params = dict(
            ser_params=master_ser.sch_params,
            amp_params=master_amp.sch_params,
            esd_params=master_esd.sch_params,
        )

    def _connect_ser_esd(self, amp, esdb, esdt, show_pins):
        vdd = self.connect_wires(list(chain(esdb.port_pins_iter('VDD'),
                                            esdt.port_pins_iter('VDD'))))
        vss = self.connect_wires(list(chain(esdb.port_pins_iter('VSS'),
                                            esdt.port_pins_iter('VSS'))))
        outp = self.connect_to_track_wires(esdt.get_pin('in'), amp.get_pin('outp'))
        outn = self.connect_to_track_wires(esdb.get_pin('in'), amp.get_pin('outn'))
        self.add_pin('outp', outp, show=show_pins)
        self.add_pin('outn', outn, show=show_pins)

        vdd = self.connect_to_track_wires(vdd, amp.get_all_port_pins('VDD'))
        vss = self.connect_to_track_wires(vss, amp.get_all_port_pins('VSS'))

        return vdd, vss

    def _connect_ser_amp(self, ym_layer, tr_manager, ser, amp, x_route, ibias_locs,
                         ym_tr_w_ibias, show_pins):
        wp = self.connect_wires([ser.get_pin('outp'), amp.get_pin('inp')])[0]
        wn = self.connect_wires([ser.get_pin('outn'), amp.get_pin('inn')])[0]

        lower = min(wp.track_id.get_bounds(self.grid, unit_mode=True)[0],
                    wn.track_id.get_bounds(self.grid, unit_mode=True)[0])
        upper = amp.bound_box.top_unit

        ym_tr_w_sh = tr_manager.get_width(ym_layer, 'sh')
        tr0 = self.grid.find_next_track(ym_layer, x_route, mode=1, half_track=True,
                                        unit_mode=True)

        sh = self.add_wires(ym_layer, tr0 + ibias_locs[0], lower, upper, width=ym_tr_w_sh,
                            num=2, pitch=ibias_locs[2] - ibias_locs[0], unit_mode=True)
        ibias_tid = TrackID(ym_layer, tr0 + ibias_locs[1], width=ym_tr_w_ibias)

        self.add_pin('ibias', self.connect_to_tracks(amp.get_pin('ibias'), ibias_tid,
                                                     track_lower=lower, track_upper=upper,
                                                     unit_mode=True), show=show_pins)

        for name in ('ser_reset', 'div_en', 'clock_tx_div', 'clkp', 'clkn'):
            self.reexport(ser.get_port(name), show=show_pins)
        for idx in range(32):
            self.reexport(ser.get_port('data_tx<%d>' % idx), show=show_pins)

        self.reexport(ser.get_port('VDD'), label='VDD:', show=show_pins)
        self.reexport(ser.get_port('VSS'), label='VSS:', show=show_pins)

        return sh

    def _make_masters(self):
        esd_fname = self.params['esd_fname']
        ser_params = self.params['ser_params'].copy()
        amp_params = self.params['amp_params'].copy()
        tr_widths = self.params['tr_widths']
        tr_spaces = self.params['tr_spaces']
        fill_config = self.params['fill_config']

        with open(esd_fname, 'r') as f:
            esd_params = yaml.load(f)

        amp_params['tr_widths'] = tr_widths
        amp_params['tr_spaces'] = tr_spaces
        amp_params['ext_mode'] = 1
        amp_params['show_pins'] = False
        master_amp = self.new_template(params=amp_params, temp_cls=CMLAmpPMOS)

        ser_params['tr_widths'] = tr_widths
        ser_params['tr_spaces'] = tr_spaces
        ser_params['fill_config'] = fill_config
        ser_params['out_tid'] = master_amp.in_tid
        ser_params['show_pins'] = False
        master_ser = self.new_template(params=ser_params, temp_cls=Serializer32)

        esd_params['show_pins'] = False
        master_esd = self.new_template(params=esd_params, temp_cls=BlackBoxTemplate)

        return master_ser, master_amp, master_esd
