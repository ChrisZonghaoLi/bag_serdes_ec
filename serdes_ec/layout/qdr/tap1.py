# -*- coding: utf-8 -*-

"""This module defines classes needed to build the DFE tap1 summer."""

from typing import TYPE_CHECKING, Dict, Any, Set

from bag.layout.util import BBox
from bag.layout.routing import TrackManager
from bag.layout.template import TemplateBase

from .base import HybridQDRBaseInfo, HybridQDRBase
from .laygo import SinClkDivider

if TYPE_CHECKING:
    from bag.layout.template import TemplateDB


class Tap1FB(HybridQDRBase):
    """tap1 summer DFE feedback Gm and the first digital latch.

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
        self._fg_core = None

    @property
    def sch_params(self):
        # type: () -> Dict[str, Any]
        return self._sch_params

    @property
    def fg_core(self):
        # type: () -> int
        return self._fg_core

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
            tr_widths='Track width dictionary.',
            tr_spaces='Track spacing dictionary.',
            fg_min='Minimum number of core fingers.',
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
        tr_manager = TrackManager(self.grid, tr_widths, tr_spaces, half_space=True)
        wire_names = {
            'tail': dict(g=['clk'], ds=['ntail']),
            'nen': dict(g=['en'], ds=['ntail']),
            'in': dict(g=['in', 'in'], ds=[]),
            'pen': dict(ds=['out', 'out'], g=['en', 'en']),
            'load': dict(ds=['ptail'], g=['clk', 'clk']),
        }

        # get total number of fingers
        hm_layer = self.mos_conn_layer + 1
        top_layer = hm_layer + 1
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
        fg_tot = fg_amp + 2 * fg_dumr
        self._fg_core = qdr_info.get_placement_info(fg_tot).core_fg
        if self._fg_core < fg_min:
            fg_tot += (fg_min - self._fg_core)
            self._fg_core = fg_min
        fg_duml = fg_tot - fg_dumr - fg_amp

        self.draw_rows(lch, fg_tot, ptap_w, ntap_w, w_dict, th_dict, tr_manager,
                       wire_names, top_layer=top_layer, end_mode=12, **options)

        # draw amplifier
        lat_ports, _ = self.draw_integ_amp(fg_duml, seg_lat, fg_dum=0,
                                           fg_sep_load=fg_sep_load, net_prefix='lat_')
        fb_ports, _ = self.draw_integ_amp(fg_duml + fg_latch + fg_sep_out, seg_fb,
                                          fg_dum=0, fg_sep_load=fg_sep_load, net_prefix='fb_')

        vss_warrs, vdd_warrs = self.fill_dummy()

        for name in ('inp', 'inn', 'en1', 'clkp', 'clkn'):
            wname = 'pen1' if name == 'en1' else name
            cur_warr = self.connect_wires([lat_ports[wname], fb_ports[wname]])
            self.add_pin(name, cur_warr, show=show_pins)
        for name in ('pen0', 'nen0'):
            cur_warr = self.connect_wires([lat_ports[name], fb_ports[name]])
            self.add_pin('en0', cur_warr, label='en0:', show=show_pins)

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


class Tap1Main(HybridQDRBase):
    """The DFE tap1 summer main tap.

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

        for name in ('inp', 'inn', 'outp', 'outn', 'bias_clkp'):
            warr = ports[name]
            self.add_pin(name, warr, show=show_pins)
            self._track_info[name] = (warr.track_id.base_index, warr.track_id.width)

        nen0 = ports['nen0']
        self.add_pin('nen0', nen0, show=show_pins)
        self.add_pin('pen0', ports['pen0'], show=show_pins)
        self._track_info['nen0'] = (nen0.track_id.base_index, nen0.track_id.width)

        for name, port_name in (('pen1', 'en1'), ('clkp', 'clkp'), ('clkn', 'clkn')):
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


class Tap1MainRow(TemplateBase):
    """The DFE tap1 summer main tap and clock divider.

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
        self._fg_core = None

    @property
    def sch_params(self):
        # type: () -> Dict[str, Any]
        return self._sch_params

    @property
    def fg_core(self):
        # type: () -> int
        return self._fg_core

    @classmethod
    def get_default_param_values(cls):
        # type: () -> Dict[str, Any]
        return dict(
            div_pos_edge=True,
            fg_min=0,
            is_end=False,
            show_pins=True,
            options=None,
        )

    @classmethod
    def get_params_info(cls):
        # type: () -> Dict[str, str]
        return dict(
            config='Laygo configuration dictionary for the divider.',
            lch='channel length, in meters.',
            ptap_w='NMOS substrate width, in meters/number of fins.',
            ntap_w='PMOS substrate width, in meters/number of fins.',
            w_dict='NMOS/PMOS width dictionary.',
            th_dict='NMOS/PMOS threshold flavor dictionary.',
            seg_main='number of segments dictionary for main tap.',
            seg_div='number of segments dictionary for clock divider.',
            fg_dum='Number of single-sided edge dummy fingers.',
            tr_widths='Track width dictionary.',
            tr_spaces='Track spacing dictionary.',
            div_pos_edge='True if the divider triggers off positive edge of the clock.',
            fg_min='Minimum number of core fingers.',
            is_end='True if this is the end row.',
            show_pins='True to create pin labels.',
            options='other AnalogBase options',
        )

    def draw_layout(self):
        # get parameters
        config = self.params['config']
        seg_div = self.params['seg_div']
        show_pins = self.params['show_pins']
        tr_widths = self.params['tr_widths']
        tr_spaces = self.params['tr_spaces']
        is_end = self.params['is_end']
        div_pos_edge = self.params['div_pos_edge']
        fg_min = self.params['fg_min']

        # get layout masters
        main_params = self.params.copy()
        main_params['show_pins'] = False
        del main_params['config']
        del main_params['seg_div']
        main_params['seg_dict'] = main_params['seg_main']
        del main_params['seg_main']
        del main_params['fg_min']
        if is_end:
            main_params['end_mode'] = 13 if seg_div is None else 9
            div_end_mode = 5
        else:
            main_params['end_mode'] = 12 if seg_div is None else 8
            div_end_mode = 4

        top_layer = HybridQDRBase.get_mos_conn_layer(self.grid.tech_info) + 2
        if seg_div is None:
            d_master = None
            main_params['top_layer'] = top_layer
            m_master = self.new_template(params=main_params, temp_cls=Tap1Main)
            self._fg_core = m_master.layout_info.fg_core
        else:
            m_master = self.new_template(params=main_params, temp_cls=Tap1Main)
            m_tr_info = m_master.track_info
            tr_info = dict(
                VDD=m_tr_info['VDD'],
                VSS=m_tr_info['VSS'],
                q=m_tr_info['outp'],
                qb=m_tr_info['outn'],
                en=m_tr_info['nen0'],
                clk=m_tr_info['clkp'] if div_pos_edge else m_tr_info['clkn'],
            )

            div_params = dict(
                config=config,
                row_layout_info=m_master.row_layout_info,
                seg_dict=seg_div,
                tr_info=tr_info,
                tr_widths=tr_widths,
                tr_spaces=tr_spaces,
                end_mode=div_end_mode,
                show_pins=False,
            )
            d_master = self.new_template(params=div_params, temp_cls=SinClkDivider)
            self._fg_core = m_master.layout_info.fg_core + d_master.laygo_info.core_col

        # compute fg_core, and resize main tap if necessary
        if self._fg_core < fg_min:
            new_fg_tot = m_master.fg_tot + (fg_min - self._fg_core)
            m_master = m_master.new_template_with(fg_min=new_fg_tot)
            self._fg_core = fg_min

        # place instances and set bounding box
        if d_master is None:
            m_inst = self.add_instance(m_master, 'XMAIN', loc=(0, 0), unit_mode=True)
            self.array_box = m_inst.array_box
            self.set_size_from_bound_box(top_layer, m_inst.bound_box)

            # get pins
            vdd = m_inst.get_all_port_pins('VDD')
            vss = m_inst.get_all_port_pins('VSS')
            clkp = m_inst.get_all_port_pins('clkp')
            clkn = m_inst.get_all_port_pins('clkn')
        else:
            # calculate instance placements
            blk_w = self.grid.get_block_size(top_layer, unit_mode=True)[0]
            core_width = d_master.bound_box.width_unit + m_master.bound_box.width_unit
            tot_width = -(-core_width // blk_w) * blk_w
            xl = (tot_width - core_width) // 2

            # place instances
            top_layer = m_master.top_layer
            d_inst = self.add_instance(d_master, 'XDIV', loc=(xl, 0))
            m_inst = self.add_instance(m_master, 'XMAIN', loc=(d_inst.bound_box.right_unit, 0),
                                       unit_mode=True)

            # set size
            res = self.grid.resolution
            bnd_box = BBox(0, 0, tot_width, d_inst.bound_box.height_unit, res, unit_mode=True)
            self.array_box = BBox(0, m_inst.array_box.bottom_unit, tot_width,
                                  m_inst.array_box.top_unit, res, unit_mode=True)
            self.set_size_from_bound_box(top_layer, bnd_box)

            # connect pins between two masters
            vdd = m_inst.get_all_port_pins('VDD')
            vss = m_inst.get_all_port_pins('VSS')
            clkp = m_inst.get_all_port_pins('clkp')
            clkn = m_inst.get_all_port_pins('clkn')

            vdd.extend(d_inst.get_all_port_pins('VDD'))
            vss.extend(d_inst.get_all_port_pins('VSS'))
            vdd = self.connect_wires(vdd)
            vss = self.connect_wires(vss)
            if div_pos_edge:
                clkp.extend(d_inst.get_all_port_pins('clk'))
                clkp = self.connect_wires(clkp)
                clkn = self.extend_wires(clkn, lower=clkp[0].lower)
            else:
                clkn.extend(d_inst.get_all_port_pins('clk'))
                clkn = self.connect_wires(clkn)
                clkp = self.extend_wires(clkp, lower=clkn[0].lower)

            # re-export divider pins
            self.reexport(d_inst.get_port('q'), net_name='div', show=show_pins)
            self.reexport(d_inst.get_port('qb'), net_name='divb', show=show_pins)
            self.reexport(d_inst.get_port('en'), net_name='en_div', show=show_pins)
            self.reexport(d_inst.get_port('scan_s'), net_name='scan_div', show=show_pins)

        self.add_pin('VDD', vdd, show=show_pins)
        self.add_pin('VSS', vss, show=show_pins)
        self.add_pin('clkp', clkp, show=show_pins)
        self.add_pin('clkn', clkn, show=show_pins)

        # re-export tap1 pins
        self.reexport(m_inst.get_port('pen0'), net_name='en0', label='en0:', show=show_pins)
        self.reexport(m_inst.get_port('nen0'), net_name='en0', label='en0:', show=show_pins)
        for name in ('en1', 'outp', 'outn', 'inp', 'inn', 'bias_clkp'):
            self.reexport(m_inst.get_port(name), show=show_pins)

        # set schematic parameters
        self._sch_params = dict(
            div_pos_edge=div_pos_edge,
            main_params=m_master.sch_params,
        )
        if d_master is None:
            self._sch_params['div_params'] = None
        else:
            self._sch_params['div_params'] = d_master.sch_params


class Tap1Summer(TemplateBase):
    """The DFE tap1 Summer.

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
        self._fg_core = None

    @property
    def sch_params(self):
        # type: () -> Dict[str, Any]
        return self._sch_params

    @property
    def fg_core(self):
        # type: () -> int
        return self._fg_core

    @classmethod
    def get_default_param_values(cls):
        # type: () -> Dict[str, Any]
        return dict(
            div_pos_edge=True,
            fg_min=0,
            is_end=False,
            show_pins=True,
            options=None,
        )

    @classmethod
    def get_params_info(cls):
        # type: () -> Dict[str, str]
        return dict(
            config='Laygo configuration dictionary for the divider.',
            lch='channel length, in meters.',
            ptap_w='NMOS substrate width, in meters/number of fins.',
            ntap_w='PMOS substrate width, in meters/number of fins.',
            w_dict='NMOS/PMOS width dictionary.',
            th_dict='NMOS/PMOS threshold flavor dictionary.',
            seg_main='number of segments dictionary for main tap.',
            seg_div='number of segments dictionary for clock divider.',
            seg_fb='number of segments dictionary for tap1 feedback.',
            seg_lat='number of segments dictionary for digital latch.',
            fg_dum='Number of single-sided edge dummy fingers.',
            tr_widths='Track width dictionary.',
            tr_spaces='Track spacing dictionary.',
            div_pos_edge='True if the divider triggers off positive edge of the clock.',
            fg_min='Minimum number of core fingers.',
            is_end='True if this is the end row.',
            show_pins='True to create pin labels.',
            options='other AnalogBase options',
        )

    def draw_layout(self):
        # get parameters
        seg_div = self.params['seg_div']
        show_pins = self.params['show_pins']

        # get layout masters
        main_params = self.params.copy()
        main_params['show_pins'] = False
        del main_params['seg_fb']
        del main_params['seg_lat']
        del main_params['fg_min']

        fb_params = self.params.copy()
        fb_params['show_pins'] = False
        del fb_params['config']
        del fb_params['seg_main']
        del fb_params['seg_div']
        del fb_params['div_pos_edge']
        del fb_params['fg_min']
        del fb_params['is_end']

        # get masters
        m_master = self.new_template(params=main_params, temp_cls=Tap1MainRow)
        f_master = self.new_template(params=fb_params, temp_cls=Tap1FB)

        fg_min = max(f_master.fg_core, m_master.fg_core)
        if f_master.fg_core < fg_min:
            f_master = f_master.new_template_with(fg_min=fg_min)
        if m_master.fg_core < fg_min:
            m_master = m_master.new_template_with(fg_min=fg_min)

        # place instances
        top_layer = m_master.top_layer
        m_inst = self.add_instance(m_master, 'XMAIN', loc=(0, 0), unit_mode=True)
        y0 = m_inst.array_box.top_unit + f_master.array_box.top_unit
        f_inst = self.add_instance(f_master, 'XFB', loc=(0, y0), orient='MX', unit_mode=True)

        # set size
        self.array_box = m_inst.array_box.merge(f_inst.array_box)
        self.set_size_from_bound_box(top_layer, m_inst.bound_box.merge(f_inst.bound_box))

        # export pins in-place
        exp_list = [(m_inst, 'outp', 'outp_m', True), (m_inst, 'outn', 'outn_m', True),
                    (m_inst, 'inp', 'inp', False), (m_inst, 'inn', 'inn', False),
                    (m_inst, 'en0', 'en0', True), (m_inst, 'en1', 'en1', True),
                    (m_inst, 'VDD', 'VDD', True), (m_inst, 'VSS', 'VSS', True),
                    (m_inst, 'clkp', 'clkp', True), (m_inst, 'clkn', 'clkn', True),
                    (m_inst, 'bias_clkp', 'clkp_m', False),
                    (f_inst, 'inp', 'outp_m', True), (f_inst, 'inn', 'outn_m', True),
                    (f_inst, 'fb_clkp', 'clkn_f', False), (f_inst, 'lat_clkp', 'clkn_d', False),
                    (f_inst, 'fb_outp', 'outp_f', False), (f_inst, 'fb_outn', 'outn_f', False),
                    (f_inst, 'lat_outp', 'outp_d', False), (f_inst, 'lat_outn', 'outn_d', False),
                    (f_inst, 'en0', 'en1', True), (f_inst, 'en1', 'en2', False),
                    (f_inst, 'clkp', 'clkn', True), (f_inst, 'clkn', 'clkp', True),
                    (f_inst, 'VDD', 'VDD', True), (f_inst, 'VSS', 'VSS', True),
                    ]
        if seg_div is not None:
            exp_list.extend(((m_inst, name, name, False)
                             for name in ['en_div', 'scan_div', 'div', 'divb']))

        for inst, port, name, vconn in exp_list:
            label = name + ':' if vconn else name
            self.reexport(inst.get_port(port), net_name=name, label=label, show=show_pins)

        # set schematic parameters
        self._sch_params = dict(
            main_params=m_master.sch_params,
            fb_params=f_master.sch_params,
        )
