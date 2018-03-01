# -*- coding: utf-8 -*-

"""This module defines classes needed to build the DFE tap1 summer."""

from typing import TYPE_CHECKING, Dict, Any, Set

from itertools import chain

from bag.layout.routing import TrackManager, TrackID
from bag.layout.template import TemplateBase

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
        self._fg_tot = None

    @property
    def sch_params(self):
        # type: () -> Dict[str, Any]
        return self._sch_params

    @property
    def fg_tot(self):
        # type: () -> int
        return self._fg_tot

    @classmethod
    def get_default_param_values(cls):
        # type: () -> Dict[str, Any]
        return dict(
            fg_min=0,
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
            seg_lat='number of segments dictionary for digital latch.',
            fg_dum='Number of single-sided edge dummy fingers.',
            fg_min='Minimum number of fingers total.',
            tr_widths='Track width dictionary.',
            tr_spaces='Track spacing dictionary.',
            show_pins='True to create pin labels.',
            options='other AnalogBase options',
        )

    def draw_layout(self):
        lch = self.params['lch']
        ptap_w = self.params['ptap_w']
        ntap_w = self.params['ntap_w']
        w_dict = self.params['w_dict']
        th_dict = self.params['th_dict']
        seg_fb = self.params['seg_fb']
        seg_lat = self.params['seg_lat']
        fg_dumr = self.params['fg_dum']
        fg_min = self.params['fg_min']
        tr_widths = self.params['tr_widths']
        tr_spaces = self.params['tr_spaces']
        show_pins = self.params['show_pins']
        options = self.params['options']

        if options is None:
            options = {}

        # get track manager and wire names
        tr_manager = TrackManager(self.grid, tr_widths, tr_spaces)
        wire_names = {
            'tail': dict(g=['clk'], ds=['ntail']),
            'nen': dict(g=['en'], ds=['ntail']),
            'in': dict(g=['in', 'in'], ds=[]),
            'pen': dict(ds=['out', 'out'], g=['en']),
            'load': dict(ds=['ptail'], g=['clk']),
        }

        # get total number of fingers
        hm_layer = self.mos_conn_layer + 1
        top_layer = vm_layer = hm_layer + 1
        qdr_info = HybridQDRBaseInfo(self.grid, lch, 0, top_layer=top_layer,
                                     end_mode=12, **options)
        fg_sep_out = qdr_info.get_fg_sep_from_hm_space(tr_manager.get_width(hm_layer, 'out'),
                                                       round_even=True)
        fg_sep_load = qdr_info.get_fg_sep_from_hm_space(tr_manager.get_width(hm_layer, 'en'),
                                                        round_even=True)
        fg_sep_load = max(0, fg_sep_load - 2)

        fb_info = qdr_info.get_integ_amp_info(seg_fb, fg_dum=0, fg_sep_load=fg_sep_load)
        latch_info = qdr_info.get_integ_amp_info(seg_lat, fg_dum=0, fg_sep_load=fg_sep_load)

        fg_latch = latch_info['fg_tot']
        fg_amp = fb_info['fg_tot'] + fg_latch + fg_sep_out
        fg_tot = max(fg_amp + 2 * fg_dumr, fg_min)
        fg_duml = fg_tot - fg_dumr - fg_amp

        self.draw_rows(lch, fg_tot, ptap_w, ntap_w, w_dict, th_dict, tr_manager,
                       wire_names, top_layer=top_layer, end_mode=12, **options)

        # draw amplifier
        lat_ports, _ = self.draw_integ_amp(fg_duml, seg_lat, fg_dum=0,
                                           fg_sep_load=fg_sep_load, net_prefix='lat_')
        fb_ports, _ = self.draw_integ_amp(fg_duml + fg_latch + fg_sep_out, seg_fb,
                                          fg_dum=0, fg_sep_load=fg_sep_load, net_prefix='fb_')

        vss_warrs, vdd_warrs = self.fill_dummy()

        w_vm_en = tr_manager.get_width(vm_layer, 'en')

        for name in ('inp', 'inn'):
            cur_warr = self.connect_wires([lat_ports[name], fb_ports[name]])
            self.add_pin(name, cur_warr, show=show_pins)

        nen = self.connect_wires([lat_ports['nen0'], fb_ports['nen0']])[0]
        en0_list = []
        for idx, warr in enumerate(chain(lat_ports['pen0'], fb_ports['pen0'])):
            mode = -1 if idx % 2 == 0 else 1
            mtr = self.grid.coord_to_nearest_track(vm_layer, warr.middle, half_track=True,
                                                   mode=mode)
            tid = TrackID(vm_layer, mtr, width=w_vm_en)
            en0_list.append(self.connect_to_tracks([warr, nen], tid))
        self.add_pin('en0', en0_list, show=show_pins)

        for name, port_name in (('pen1', 'en1'), ('clkp', 'clkp'), ('clkn', 'clkn')):
            warr_list = []
            for idx, warr in enumerate(chain(lat_ports[name], fb_ports[name])):
                mode = -1 if idx % 2 == 0 else 1
                mtr = self.grid.coord_to_nearest_track(vm_layer, warr.middle, half_track=True,
                                                       mode=mode)
                tid = TrackID(vm_layer, mtr, width=w_vm_en)
                warr_list.append(self.connect_to_tracks(warr, tid, min_len_mode=0))

            self.add_pin(port_name, warr_list, label=port_name + ':', show=show_pins)

        self.add_pin('lat_clkp', lat_ports['bias_clkp'], show=show_pins)
        self.add_pin('fb_clkp', fb_ports['bias_clkp'], show=show_pins)
        for name in ('outp', 'outn'):
            for prefix, port in (('lat_', lat_ports), ('fb_', fb_ports)):
                self.add_pin(prefix + name, port[name], show=show_pins)

        self.add_pin('VSS', vss_warrs, show=show_pins)
        self.add_pin('VDD', vdd_warrs, show=show_pins)

        # set properties
        self._sch_params = dict(
            lch=lch,
            w_dict=w_dict,
            th_dict=th_dict,
            seg_fb=seg_fb,
            seg_lat=seg_lat,
            dum_info=self.get_sch_dummy_info(),
        )
        self._fg_tot = fg_tot


class Tap1Main(HybridQDRBase):
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
        self._fg_tot = None

    @property
    def sch_params(self):
        # type: () -> Dict[str, Any]
        return self._sch_params

    @property
    def fg_tot(self):
        # type: () -> int
        return self._fg_tot

    @classmethod
    def get_default_param_values(cls):
        # type: () -> Dict[str, Any]
        return dict(
            fg_min=0,
            is_end=False,
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
            seg_dict='number of segments dictionary.',
            fg_dum='Number of single-sided edge dummy fingers.',
            fg_min='Minimum number of fingers total.',
            tr_widths='Track width dictionary.',
            tr_spaces='Track spacing dictionary.',
            show_pins='True to create pin labels.',
            is_end='True if this is the end row.',
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
        fg_min = self.params['fg_min']
        tr_widths = self.params['tr_widths']
        tr_spaces = self.params['tr_spaces']
        show_pins = self.params['show_pins']
        is_end = self.params['is_end']
        options = self.params['options']

        end_mode = 13 if is_end else 12
        if options is None:
            options = {}

        # get track manager and wire names
        tr_manager = TrackManager(self.grid, tr_widths, tr_spaces)
        wire_names = {
            'tail': dict(g=['clk'], ds=['ntail']),
            'nen': dict(g=['en'], ds=['ntail']),
            'in': dict(g=['in', 'in'], ds=[]),
            'pen': dict(ds=['out', 'out'], g=['en']),
            'load': dict(ds=['ptail'], g=['clk']),
        }

        # get total number of fingers
        hm_layer = self.mos_conn_layer + 1
        top_layer = vm_layer = hm_layer + 1
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

        w_vm_en = tr_manager.get_width(vm_layer, 'en')

        for name in ('inp', 'inn', 'outp', 'outn', 'bias_clkp'):
            self.add_pin(name, ports[name], show=show_pins)

        nen = ports['nen0']
        en0_list = []
        for idx, warr in enumerate(ports['pen0']):
            mode = -1 if idx % 2 == 0 else 1
            mtr = self.grid.coord_to_nearest_track(vm_layer, warr.middle, half_track=True,
                                                   mode=mode)
            tid = TrackID(vm_layer, mtr, width=w_vm_en)
            en0_list.append(self.connect_to_tracks([warr, nen], tid))
        self.add_pin('en0', en0_list, show=show_pins)

        for name, port_name in (('pen1', 'en1'), ('clkp', 'clkp'), ('clkn', 'clkn')):
            warr_list = []
            for idx, warr in enumerate(ports[name]):
                mode = -1 if idx % 2 == 0 else 1
                mtr = self.grid.coord_to_nearest_track(vm_layer, warr.middle, half_track=True,
                                                       mode=mode)
                tid = TrackID(vm_layer, mtr, width=w_vm_en)
                warr_list.append(self.connect_to_tracks(warr, tid, min_len_mode=0))

            self.add_pin(port_name, warr_list, label=port_name + ':', show=show_pins)

        self.add_pin('VSS', vss_warrs, show=show_pins)
        self.add_pin('VDD', vdd_warrs, show=show_pins)

        # set schematic parameters
        self._sch_params = dict(
            lch=lch,
            w_dict=w_dict,
            th_dict=th_dict,
            seg_dict=seg_dict,
            dum_info=self.get_sch_dummy_info(),
        )
        self._fg_tot = fg_tot


class Tap1Summer(TemplateBase):
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
        TemplateBase.__init__(self, temp_db, lib_name, params, used_names, **kwargs)
        self._sch_params = None

    @property
    def sch_params(self):
        # type: () -> Dict[str, Any]
        return self._sch_params

    @classmethod
    def get_default_param_values(cls):
        # type: () -> Dict[str, Any]
        return dict(
            is_end=False,
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
            seg_main='number of segments dictionary for main tap.',
            seg_fb='number of segments dictionary for tap1 feedback.',
            seg_lat='number of segments dictionary for digital latch.',
            fg_dum='Number of single-sided edge dummy fingers.',
            tr_widths='Track width dictionary.',
            tr_spaces='Track spacing dictionary.',
            show_pins='True to create pin labels.',
            is_end='True if this is the end row.',
            options='other AnalogBase options',
        )

    def draw_layout(self):
        # get parameters
        fb_params = self.params.copy()
        del fb_params['seg_main']
        del fb_params['is_end']
        main_params = self.params.copy()
        del main_params['seg_fb']
        del main_params['seg_lat']
        main_params['seg_dict'] = main_params['seg_main']
        del main_params['seg_main']

        # get masters
        f_master = self.new_template(params=fb_params, temp_cls=Tap1FB)
        m_master = self.new_template(params=main_params, temp_cls=Tap1Main)
        fg_min = max(f_master.fg_tot, m_master.fg_tot)
        if f_master.fg_tot < fg_min:
            f_master = f_master.new_template_with(fg_min=fg_min)
        if m_master.fg_tot < fg_min:
            m_master = m_master.new_template_with(fg_min=fg_min)

        # place instances
        y0 = m_master.array_box.height_unit + f_master.array_box.height_unit
        m_inst = self.add_instance(m_master, 'XMAIN')
        f_inst = self.add_instance(f_master, 'XFB', loc=(0, y0), orient='MX', unit_mode=True)

        # set size
        self.array_box = m_inst.array_box.merge(f_inst.array_box)
        self.set_size_from_array_box(m_master.top_layer)
