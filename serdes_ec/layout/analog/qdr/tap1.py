# -*- coding: utf-8 -*-

"""This module defines classes needed to build the DFE tap1 summer."""

from typing import TYPE_CHECKING, Dict, Any, Set

from bag.layout.routing import TrackManager

from .base import HybridQDRBaseInfo, HybridQDRBase

if TYPE_CHECKING:
    from bag.layout.template import TemplateDB


class Tap1FB(HybridQDRBase):
    """An integrating amplifier.

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
        HybridQDRBase.__init__(self, temp_db, lib_name, params, used_names, **kwargs)
        self._sch_params = None

    @property
    def sch_params(self):
        # type: () -> Dict[str, Any]
        return self._sch_params

    @classmethod
    def get_default_param_values(cls):
        # type: () -> Dict[str, Any]
        return dict(
            fg_min=0,
            end_mode=12,
            show_pins=True,
            options=None,
        )

    @classmethod
    def get_params_info(cls):
        # type: () -> Dict[str, str]
        return dict(
            lch='channel length, in meters.',
            ptap_w='NMOS substrate width, in meters/number of fins.',
            ntap_w='PMOS substrate width, in meters/number of fins.',
            w_dict='NMOS/PMOS width dictionary.',
            th_dict='NMOS/PMOS threshold flavor dictionary.',
            seg_fb='number of segments dictionary for tap1 feedback.',
            seg_latch='number of segments dictionary for digital latch.',
            fg_dum='Number of single-sided edge dummy fingers.',
            fg_min='Minimum number of fingers total.',
            tr_widths='Track width dictionary.',
            tr_spaces='Track spacing dictionary.',
            show_pins='True to create pin labels.',
            end_mode='AnalogBase end_mode flag.',
            options='other AnalogBase options',
        )

    def draw_layout(self):
        lch = self.params['lch']
        ptap_w = self.params['ptap_w']
        ntap_w = self.params['ntap_w']
        w_dict = self.params['w_dict']
        th_dict = self.params['th_dict']
        seg_fb = self.params['seg_fb']
        seg_latch = self.params['seg_latch']
        fg_dumr = self.params['fg_dum']
        fg_min = self.params['fg_min']
        tr_widths = self.params['tr_widths']
        tr_spaces = self.params['tr_spaces']
        show_pins = self.params['show_pins']
        end_mode = self.params['end_mode']
        options = self.params['options']

        top_layer = None
        if options is None:
            options = {}

        # get track manager and wire names
        tr_manager = TrackManager(self.grid, tr_widths, tr_spaces)
        wire_names = {
            'tail': dict(g=['clk'], ds=['ntail']),
            'enn': dict(g=['en'], ds=['ntail']),
            'in': dict(g=['in', 'in'], ds=[]),
            'enp': dict(ds=['out', 'out'], g=['en']),
            'load': dict(ds=['ptail'], g=['clk']),
        }

        # get total number of fingers
        qdr_info = HybridQDRBaseInfo(self.grid, lch, 0, top_layer=top_layer,
                                     end_mode=end_mode, **options)
        fb_info = qdr_info.get_integ_amp_info(seg_fb, fg_dum=0, sep_load=True)
        latch_info = qdr_info.get_integ_amp_info(seg_latch, fg_dum=0, sep_load=True)

        fg_latch = latch_info['fg_tot']
        hm_layer = qdr_info.mconn_port_layer + 1
        fg_sep = qdr_info.get_fg_sep_from_hm_space(tr_manager.get_width(hm_layer, 'out'),
                                                   round_even=True)
        fg_amp = fb_info['fg_tot'] + fg_latch + fg_sep
        fg_tot = max(fg_amp + 2 * fg_dumr, fg_min)
        fg_duml = fg_tot - fg_dumr - fg_amp

        self.draw_rows(lch, fg_tot, ptap_w, ntap_w, w_dict, th_dict, tr_manager,
                       wire_names, top_layer=top_layer, end_mode=end_mode, **options)

        # draw amplifier
        latch_ports, _ = self.draw_integ_amp(fg_duml, seg_latch, fg_dum=0, sep_load=True)
        fb_ports, _ = self.draw_integ_amp(fg_duml + fg_latch + fg_sep, seg_fb,
                                          fg_dum=0, sep_load=True)

        vss_warrs, vdd_warrs = self.fill_dummy()

        for key, val in latch_ports.items():
            self.add_pin('latch_' + key, val, show=show_pins)
        for key, val in fb_ports.items():
            self.add_pin('fb_' + key, val, show=show_pins)

        self.add_pin('VSS', vss_warrs, show=show_pins)
        self.add_pin('VDD', vdd_warrs, show=show_pins)
