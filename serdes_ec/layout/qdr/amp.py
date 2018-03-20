# -*- coding: utf-8 -*-

"""This module defines classes needed to build the DFE tap1 summer."""

from typing import TYPE_CHECKING, Dict, Any, Set


from bag.layout.routing import TrackManager

from .base import HybridQDRBaseInfo, HybridQDRBase

if TYPE_CHECKING:
    from bag.layout.template import TemplateDB


class IntegAmp(HybridQDRBase):
    """A single integrating amplifier.

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
        self._fg_tot = None
        self._track_info = None

    @property
    def sch_params(self):
        # type: () -> Dict[str, Any]
        return self._sch_params

    @property
    def fg_tot(self):
        # type: () -> int
        return self._fg_tot

    @property
    def track_info(self):
        return self._track_info

    @classmethod
    def get_default_param_values(cls):
        # type: () -> Dict[str, Any]
        return dict(
            fg_min=0,
            top_layer=None,
            show_pins=True,
            end_mode=15,
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
            seg_dict='number of segments dictionary.',
            fg_dum='Number of single-sided edge dummy fingers.',
            tr_widths='Track width dictionary.',
            tr_spaces='Track spacing dictionary.',
            fg_min='Minimum number of fingers total.',
            top_layer='Top layer ID',
            show_pins='True to create pin labels.',
            end_mode='The AnalogBase end_mode flag.',
            options='other AnalogBase options',
        )

    def draw_layout(self):
        lch = self.params['lch']
        ptap_w = self.params['ptap_w']
        ntap_w = self.params['ntap_w']
        w_dict = self.params['w_dict']
        th_dict = self.params['th_dict']
        seg_dict = self.params['seg_dict']
        fg_dumr = self.params['fg_dum']
        tr_widths = self.params['tr_widths']
        tr_spaces = self.params['tr_spaces']
        fg_min = self.params['fg_min']
        top_layer = self.params['top_layer']
        show_pins = self.params['show_pins']
        end_mode = self.params['end_mode']
        options = self.params['options']

        if options is None:
            options = {}

        # get track manager and wire names
        tr_manager = TrackManager(self.grid, tr_widths, tr_spaces, half_space=True)
        wire_names = {
            # TODO: hack tail gate for now, should fix itself later when we specify min height.
            'tail': dict(g=[1, 'clk'], ds=['ntail']),
            'nen': dict(g=['en'], ds=['ntail']),
            'in': dict(g=['in', 'in'], ds=[]),
            'pen': dict(ds=['out', 'out'], g=['en', 'en']),
            'load': dict(ds=['ptail'], g=['clk', 'clk']),
        }

        # get total number of fingers
        hm_layer = self.mos_conn_layer + 1
        if top_layer is None:
            top_layer = hm_layer
        qdr_info = HybridQDRBaseInfo(self.grid, lch, 0, top_layer=top_layer,
                                     end_mode=end_mode, **options)
        fg_sep_load = qdr_info.get_fg_sep_from_hm_space(tr_manager.get_width(hm_layer, 'en'),
                                                        round_even=True)
        fg_sep_load = max(0, fg_sep_load - 2)

        amp_info = qdr_info.get_integ_amp_info(seg_dict, fg_dum=0, fg_sep_load=fg_sep_load)

        fg_amp = amp_info['fg_tot']
        fg_tot = max(fg_amp + 2 * fg_dumr, fg_min)
        fg_duml = fg_tot - fg_dumr - fg_amp

        self.draw_rows(lch, fg_tot, ptap_w, ntap_w, w_dict, th_dict, tr_manager,
                       wire_names, top_layer=top_layer, end_mode=end_mode, **options)

        # draw amplifier
        ports, _ = self.draw_integ_amp(fg_duml, seg_dict, fg_dum=0, fg_sep_load=fg_sep_load)

        vss_warrs, vdd_warrs = self.fill_dummy()
        vss_warr = vss_warrs[0]
        vdd_warr = vdd_warrs[0]
        self.add_pin('VSS', vss_warr, show=show_pins)
        self.add_pin('VDD', vdd_warr, show=show_pins)
        self._track_info = dict(
            VSS=(vss_warr.track_id.base_index, vss_warr.track_id.width),
            VDD=(vdd_warr.track_id.base_index, vdd_warr.track_id.width),
        )

        for name in ('inp', 'inn', 'outp', 'outn', 'biasp'):
            warr = ports[name]
            self.add_pin(name, warr, show=show_pins)
            self._track_info[name] = (warr.track_id.base_index, warr.track_id.width)

        nen0 = ports['nen0']
        self.add_pin('nen0', nen0, show=False)
        self.add_pin('pen0', ports['pen0'], show=False)
        self.add_pin('en<0>', nen0, label='en<0>:', show=show_pins)
        self.add_pin('en<0>', ports['pen0'], label='en<0>:', show=show_pins)
        self._track_info['nen0'] = (nen0.track_id.base_index, nen0.track_id.width)

        for name, port_name in (('pen1', 'en<1>'), ('clkp', 'clkp'), ('clkn', 'clkn')):
            warr = ports[name]
            self.add_pin(port_name, warr, show=show_pins)
            if port_name == 'clkp' or port_name == 'clkn':
                self._track_info[port_name] = (warr.track_id.base_index, warr.track_id.width)

        # set schematic parameters
        self._sch_params = dict(
            lch=lch,
            w_dict=w_dict,
            th_dict=th_dict,
            seg_dict=seg_dict,
            dum_info=self.get_sch_dummy_info(),
        )
        self._fg_tot = fg_tot
