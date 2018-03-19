# -*- coding: utf-8 -*-

"""This module defines classes needed to build the DFE tap1 summer."""

from typing import TYPE_CHECKING, Dict, Any, Set, List, Union

from itertools import chain

from bag.layout.util import BBox
from bag.layout.routing import TrackManager, TrackID
from bag.layout.template import TemplateBase

from .base import HybridQDRBaseInfo, HybridQDRBase
from .laygo import SinClkDivider

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


class Tap1SummerRow(HybridQDRBase):
    """The DFE tap1 summer row.

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
            seg_fb='number of segments dictionary for feedback tap.',
            fg_dum='Number of single-sided edge dummy fingers.',
            tr_widths='Track width dictionary.',
            tr_spaces='Track spacing dictionary.',
            fg_min='Minimum number of core fingers.',
            is_end='True if this is the end row.',
            show_pins='True to create pin labels.',
            options='other AnalogBase options',
        )

    def draw_layout(self):
        lch = self.params['lch']
        ptap_w = self.params['ptap_w']
        ntap_w = self.params['ntap_w']
        w_dict = self.params['w_dict']
        th_dict = self.params['th_dict']
        seg_main = self.params['seg_main']
        seg_fb = self.params['seg_fb']
        fg_dumr = self.params['fg_dum']
        tr_widths = self.params['tr_widths']
        tr_spaces = self.params['tr_spaces']
        fg_min = self.params['fg_min']
        is_end = self.params['is_end']
        show_pins = self.params['show_pins']
        options = self.params['options']

        if options is None:
            options = {}
        end_mode = 13 if is_end else 12

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
                                     end_mode=end_mode, **options)
        fg_sep_out = qdr_info.get_fg_sep_from_hm_space(tr_manager.get_width(hm_layer, 'out'),
                                                       round_even=True)
        fg_sep_load = qdr_info.get_fg_sep_from_hm_space(tr_manager.get_width(hm_layer, 'en'),
                                                        round_even=True)
        fg_sep_load = max(0, fg_sep_load - 2)

        main_info = qdr_info.get_integ_amp_info(seg_main, fg_dum=0, fg_sep_load=fg_sep_load)
        fb_info = qdr_info.get_integ_amp_info(seg_fb, fg_dum=0, fg_sep_load=fg_sep_load)

        fg_main = main_info['fg_tot']
        fg_amp = fg_main + fb_info['fg_tot'] + fg_sep_out
        fg_tot = fg_amp + 2 * fg_dumr
        self._fg_core = qdr_info.get_placement_info(fg_tot).core_fg
        if self._fg_core < fg_min:
            fg_tot += (fg_min - self._fg_core)
            self._fg_core = fg_min
        fg_duml = fg_tot - fg_dumr - fg_amp

        self.draw_rows(lch, fg_tot, ptap_w, ntap_w, w_dict, th_dict, tr_manager,
                       wire_names, top_layer=top_layer, end_mode=12, **options)

        # draw amplifier
        main_ports, _ = self.draw_integ_amp(fg_duml, seg_main, fg_dum=0,
                                            fg_sep_load=fg_sep_load, net_suffix='_m')
        fb_ports, _ = self.draw_integ_amp(fg_duml + fg_main + fg_sep_out, seg_fb, invert=True,
                                          fg_dum=0, fg_sep_load=fg_sep_load, net_suffix='_f')

        vss_warrs, vdd_warrs = self.fill_dummy()
        ports_list = [main_ports, fb_ports]

        for name in ('outp', 'outn', 'en1', 'clkp', 'clkn'):
            if name == 'en1':
                wname = 'pen1'
                port_name = 'en<1>'
            else:
                wname = port_name = name
            wlist = [p[wname] for p in ports_list if wname in p]
            cur_warr = self.connect_wires(wlist)
            self.add_pin(port_name, cur_warr, show=show_pins)
        for name in ('pen0', 'nen0'):
            wlist = [p[name] for p in ports_list if name in p]
            cur_warr = self.connect_wires(wlist)
            self.add_pin('en<0>', cur_warr, label='en<0>:', show=show_pins)

        self.add_pin('biasp_m', main_ports['biasp'], show=show_pins)
        self.add_pin('biasp_f', fb_ports['biasp'], show=show_pins)
        self.add_pin('inp', main_ports['inp'], show=show_pins)
        self.add_pin('inn', main_ports['inn'], show=show_pins)
        self.add_pin('fbp', fb_ports['inp'], show=show_pins)
        self.add_pin('fbn', fb_ports['inn'], show=show_pins)

        self.add_pin('VSS', vss_warrs, show=show_pins)
        self.add_pin('VDD', vdd_warrs, show=show_pins)

        # set properties
        self._sch_params = dict(
            lch=lch,
            w_dict=w_dict,
            th_dict=th_dict,
            seg_main=seg_main,
            seg_fb=seg_fb,
            dum_info=self.get_sch_dummy_info(),
        )


class Tap1LatchRow(TemplateBase):
    """The DFE tap2 latch and divider/reset pulse generation.

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
        self._en_locs = None

    @property
    def sch_params(self):
        # type: () -> Dict[str, Any]
        return self._sch_params

    @property
    def fg_core(self):
        # type: () -> int
        return self._fg_core

    @property
    def en_locs(self):
        # type: () -> List[Union[int, float]]
        return self._en_locs

    @classmethod
    def get_default_param_values(cls):
        # type: () -> Dict[str, Any]
        return dict(
            div_pos_edge=True,
            fg_min=0,
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
            seg_lat='number of segments dictionary for tap2 latch.',
            seg_div='number of segments dictionary for clock divider.',
            seg_pul='number of segments dictionary for pulse generation.',
            fg_dum='Number of single-sided edge dummy fingers.',
            tr_widths='Track width dictionary.',
            tr_spaces='Track spacing dictionary.',
            div_pos_edge='True if the divider triggers off positive edge of the clock.',
            fg_min='Minimum number of core fingers.',
            show_pins='True to create pin labels.',
            options='other AnalogBase options',
        )

    def draw_layout(self):
        # get parameters
        config = self.params['config']
        seg_div = self.params['seg_div']
        seg_pul = self.params['seg_pul']
        show_pins = self.params['show_pins']
        tr_widths = self.params['tr_widths']
        tr_spaces = self.params['tr_spaces']
        div_pos_edge = self.params['div_pos_edge']
        fg_min = self.params['fg_min']

        no_dig = (seg_div is None and seg_pul is None)

        # get layout masters
        lat_params = self.params.copy()
        lat_params['show_pins'] = False
        del lat_params['config']
        del lat_params['seg_div']
        lat_params['seg_dict'] = lat_params['seg_lat']
        del lat_params['seg_lat']
        del lat_params['fg_min']
        lat_params['end_mode'] = 12 if no_dig else 8
        dig_end_mode = 4

        top_layer = HybridQDRBase.get_mos_conn_layer(self.grid.tech_info) + 2
        if no_dig:
            d_master = None
            lat_params['top_layer'] = top_layer
            l_master = self.new_template(params=lat_params, temp_cls=IntegAmp)
            self._fg_core = l_master.layout_info.fg_core
        else:
            l_master = self.new_template(params=lat_params, temp_cls=IntegAmp)
            m_tr_info = l_master.track_info
            tr_info = dict(
                VDD=m_tr_info['VDD'],
                VSS=m_tr_info['VSS'],
                q=m_tr_info['inp'],
                qb=m_tr_info['inn'],
                en=m_tr_info['nen0'],
                clk=m_tr_info['clkp'] if div_pos_edge else m_tr_info['clkn'],
            )

            if seg_pul is None:
                seg_dig = seg_div
                dig_cls = SinClkDivider
            else:
                seg_dig = seg_pul
                dig_cls = SinClkDivider

            dig_params = dict(
                config=config,
                row_layout_info=l_master.row_layout_info,
                seg_dict=seg_dig,
                tr_info=tr_info,
                tr_widths=tr_widths,
                tr_spaces=tr_spaces,
                end_mode=dig_end_mode,
                show_pins=False,
            )
            d_master = self.new_template(params=dig_params, temp_cls=dig_cls)
            self._fg_core = l_master.layout_info.fg_core + d_master.laygo_info.core_col

        # compute fg_core, and resize main tap if necessary
        if self._fg_core < fg_min:
            new_fg_tot = l_master.fg_tot + (fg_min - self._fg_core)
            l_master = l_master.new_template_with(fg_min=new_fg_tot)
            self._fg_core = fg_min

        # place instances and set bounding box
        if d_master is None:
            m_inst = self.add_instance(l_master, 'XLAT', loc=(0, 0), unit_mode=True)
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
            core_width = d_master.bound_box.width_unit + l_master.bound_box.width_unit
            tot_width = -(-core_width // blk_w) * blk_w
            xl = (tot_width - core_width) // 2

            # place instances
            top_layer = l_master.top_layer
            d_inst = self.add_instance(d_master, 'XDIG', loc=(xl, 0))
            m_inst = self.add_instance(l_master, 'XLAT', loc=(d_inst.bound_box.right_unit, 0),
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
            if seg_pul is None:
                # perform connections for divider
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
            else:
                # perform connections for pulse generation
                pass

        self.add_pin('VDD', vdd, show=show_pins)
        self.add_pin('VSS', vss, show=show_pins)
        self.add_pin('clkp', clkp, show=show_pins)
        self.add_pin('clkn', clkn, show=show_pins)

        # re-export tap1 pins
        self.reexport(m_inst.get_port('en<0>'), label='en<0>:', show=show_pins)
        for name in ('en<1>', 'outp', 'outn', 'inp', 'inn', 'biasp'):
            self.reexport(m_inst.get_port(name), show=show_pins)

        # compute metal 5 enable track locations
        tr_manager = TrackManager(self.grid, tr_widths, tr_spaces, half_space=True)
        inp_warr = m_inst.get_all_port_pins('inp')[0]
        hm_layer = inp_warr.track_id.layer_id
        vm_layer = hm_layer + 1
        in_w = inp_warr.track_id.width
        tr_w = tr_manager.get_width(vm_layer, 'clk')
        in_xl = int(round(inp_warr.lower / self.grid.resolution))
        via_ext = self.grid.get_via_extensions(hm_layer, in_w, tr_w, unit_mode=True)[0]
        sp_le = self.grid.get_line_end_space(hm_layer, in_w, unit_mode=True)
        ntr, tr_locs = tr_manager.place_wires(vm_layer, ['clk'] * 4)
        tr_xr = in_xl - sp_le - via_ext
        tr_right = self.grid.find_next_track(vm_layer, tr_xr, tr_width=tr_w, half_track=True,
                                             mode=-1, unit_mode=True)
        self._en_locs = [tr_idx + tr_right - tr_locs[-1] for tr_idx in tr_locs]

        # set schematic parameters
        self._sch_params = dict(
            div_pos_edge=div_pos_edge,
            lat_params=l_master.sch_params,
        )
        if d_master is None:
            self._sch_params['div_params'] = self._sch_params['pul_params'] = None
        elif seg_div is None:
            self._sch_params['div_params'] = None
            self._sch_params['pul_params'] = d_master.sch_params
        else:
            self._sch_params['div_params'] = d_master.sch_params
            self._sch_params['pul_params'] = None


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
        self._en_locs = None

    @property
    def sch_params(self):
        # type: () -> Dict[str, Any]
        return self._sch_params

    @property
    def fg_core(self):
        # type: () -> int
        return self._fg_core

    @property
    def en_locs(self):
        # type: () -> List[Union[int, float]]
        return self._en_locs

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
            seg_fb='number of segments dictionary for tap1 feedback.',
            seg_lat='number of segments dictionary for digital latch.',
            seg_div='number of segments dictionary for clock divider.',
            seg_pul='number of segments dictionary for pulse generation.',
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
        fg_min = self.params['fg_min']
        show_pins = self.params['show_pins']

        # get layout masters
        main_params = self.params.copy()
        main_params['show_pins'] = False
        del main_params['config']
        del main_params['seg_lat']
        del main_params['seg_div']
        del main_params['seg_pul']
        del main_params['div_pos_edge']

        lat_params = self.params.copy()
        lat_params['show_pins'] = False
        del lat_params['seg_main']
        del lat_params['seg_fb']
        del lat_params['is_end']

        # get masters
        if seg_div is None:
            l_master = self.new_template(params=lat_params, temp_cls=Tap1LatchRow)
            main_params['fg_min'] = max(fg_min, l_master.fg_core)
            m_master = self.new_template(params=main_params, temp_cls=Tap1SummerRow)
        else:
            m_master = self.new_template(params=main_params, temp_cls=Tap1SummerRow)
            lat_params['fg_min'] = max(fg_min, m_master.fg_core)
            l_master = self.new_template(params=lat_params, temp_cls=Tap1LatchRow)

        self._fg_core = max(fg_min, l_master.fg_core, m_master.fg_core)
        if l_master.fg_core < self._fg_core:
            l_master = l_master.new_template_with(fg_min=self._fg_core)
        if m_master.fg_core < self._fg_core:
            m_master = m_master.new_template_with(fg_min=self._fg_core)

        # place instances
        top_layer = m_master.top_layer
        m_inst = self.add_instance(m_master, 'XMAIN', loc=(0, 0), unit_mode=True)
        y0 = m_inst.array_box.top_unit + l_master.array_box.top_unit
        l_inst = self.add_instance(l_master, 'XLAT', loc=(0, y0), orient='MX', unit_mode=True)

        # set size
        self.array_box = m_inst.array_box.merge(l_inst.array_box)
        self.set_size_from_bound_box(top_layer, m_inst.bound_box.merge(l_inst.bound_box))

        # export pins in-place
        exp_list = [(m_inst, 'outp', 'outp_m', True), (m_inst, 'outn', 'outn_m', True),
                    (m_inst, 'inp', 'inp', False), (m_inst, 'inn', 'inn', False),
                    (m_inst, 'fbp', 'fbp', False), (m_inst, 'fbn', 'fbn', False),
                    (m_inst, 'en<0>', 'en<0>', True), (m_inst, 'en<1>', 'en<1>', True),
                    (m_inst, 'VDD', 'VDD', True), (m_inst, 'VSS', 'VSS', True),
                    (m_inst, 'clkp', 'clkp', True), (m_inst, 'clkn', 'clkn', True),
                    (m_inst, 'biasp_m', 'biasp_m', False), (m_inst, 'biasp_f', 'biasp_f', False),
                    (l_inst, 'inp', 'outp_m', True), (l_inst, 'inn', 'outn_m', True),
                    (l_inst, 'outp', 'outp_d', False), (l_inst, 'outn', 'outn_d', False),
                    (l_inst, 'en<0>', 'en<1>', True), (l_inst, 'en<1>', 'en<2>', False),
                    (l_inst, 'clkp', 'clkn', True), (l_inst, 'clkn', 'clkp', True),
                    (l_inst, 'VDD', 'VDD', True), (l_inst, 'VSS', 'VSS', True),
                    (l_inst, 'biasp', 'biasn_d', False),
                    ]
        if seg_div is not None:
            exp_list.extend(((l_inst, name, name, False)
                             for name in ['en_div', 'scan_div', 'div', 'divb']))

        for inst, port_name, name, vconn in exp_list:
            port = inst.get_port(port_name)
            label = name + ':' if vconn else name
            self.reexport(port, net_name=name, label=label, show=show_pins)
            if inst is m_inst:
                if port_name == 'outp' or port_name == 'outn':
                    self.reexport(port, net_name=port_name + '_main', show=False)

        self._en_locs = l_master.en_locs

        # set schematic parameters
        self._sch_params = dict(
            sum_params=m_master.sch_params,
            lat_params=l_master.sch_params,
        )


class Tap1Column(TemplateBase):
    """The column of DFE tap1 summers.

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
            seg_fb='number of segments dictionary for tap1 feedback.',
            seg_lat='number of segments dictionary for digital latch.',
            seg_div='number of segments dictionary for clock divider.',
            seg_pul='number of segments dictionary for pulse generation.',
            fg_dum='Number of single-sided edge dummy fingers.',
            tr_widths='Track width dictionary.',
            tr_spaces='Track spacing dictionary.',
            show_pins='True to create pin labels.',
            options='other AnalogBase options',
        )

    def draw_layout(self):
        # get parameters
        show_pins = self.params['show_pins']
        tr_widths = self.params['tr_widths']
        tr_spaces = self.params['tr_spaces']

        res = self.grid.resolution

        # make masters
        div_params = self.params.copy()
        div_params['seg_pul'] = None
        div_params['div_pos_edge'] = True
        div_params['is_end'] = False
        div_params['show_pins'] = False

        divn_master = self.new_template(params=div_params, temp_cls=Tap1Summer)
        divp_master = divn_master.new_template_with(div_pos_edge=False)
        fg_min = divp_master.fg_core

        end_params = self.params.copy()
        end_params['seg_div'] = None
        end_params['fg_min'] = fg_min
        end_params['is_end'] = True
        end_params['show_pins'] = False

        endt_master = self.new_template(params=end_params, temp_cls=Tap1Summer)
        if endt_master.fg_core > fg_min:
            fg_min = endt_master.fg_core
            divn_master = divn_master.new_template_with(fg_min=fg_min)
            divp_master = divp_master.new_template_with(fg_min=fg_min)
        endb_master = endt_master.new_template_with(seg_pul=None)

        # place instances
        vm_layer = top_layer = endt_master.top_layer
        inst2 = self.add_instance(endb_master, 'X2', loc=(0, 0), unit_mode=True)
        ycur = inst2.array_box.top_unit + divn_master.array_box.top_unit
        inst1 = self.add_instance(divn_master, 'X1', loc=(0, ycur), orient='MX', unit_mode=True)
        ycur = inst1.array_box.top_unit
        inst3 = self.add_instance(divp_master, 'X3', loc=(0, ycur), unit_mode=True)
        ycur = inst3.array_box.top_unit + endt_master.array_box.top_unit
        inst0 = self.add_instance(endt_master, 'X0', loc=(0, ycur), orient='MX', unit_mode=True)
        inst_list = [inst0, inst1, inst2, inst3]

        # set size
        self.set_size_from_bound_box(top_layer, inst2.bound_box.merge(inst0.bound_box))
        self.array_box = self.bound_box

        tr_manager = TrackManager(self.grid, tr_widths, tr_spaces, half_space=True)

        # re-export supply pins
        vdd_list = list(chain(*(inst.get_all_port_pins('VDD') for inst in inst_list)))
        vss_list = list(chain(*(inst.get_all_port_pins('VSS') for inst in inst_list)))
        self.add_pin('VDD', vdd_list, label='VDD:', show=show_pins)
        self.add_pin('VSS', vss_list, label='VSS:', show=show_pins)

        # draw wires
        # compute output wire tracks
        xr = int(round(vdd_list[0].upper / res))
        tidx0 = self.grid.find_next_track(vm_layer, xr, mode=1, unit_mode=True)
        _, out_locs = tr_manager.place_wires(vm_layer, [1, 'out', 'out', 1, 'out', 'out',
                                                        1, 'out', 'out', 1], start_idx=tidx0)

        # re-export ports, and gather wires
        outp_warrs = [[], [], [], []]
        outn_warrs = [[], [], [], []]
        en_warrs = [[], [], [], []]
        for idx, inst in enumerate(inst_list):
            pidx = (idx - 1) % 4
            nidx = (idx + 1) % 4
            outp_warrs[idx].extend(inst.get_all_port_pins('outp_m'))
            outn_warrs[idx].extend(inst.get_all_port_pins('outn_m'))
            outp_warrs[pidx].extend(inst.get_all_port_pins('fbp'))
            outn_warrs[pidx].extend(inst.get_all_port_pins('fbn'))
            for off in range(4):
                en_pin = 'en<%d>' % off
                en_idx = (idx + off) % 4
                if inst.has_port(en_pin):
                    en_warrs[en_idx].extend(inst.get_all_port_pins(en_pin))
            if inst.has_port('div'):
                if idx == 3:
                    idxp, idxn = 0, 2
                else:
                    idxp, idxn = 1, 3
                en_warrs[idxp].extend(inst.get_all_port_pins('div'))
                en_warrs[idxn].extend(inst.get_all_port_pins('divb'))

            self.reexport(inst.get_port('inp'), net_name='inp<%d>' % pidx, show=show_pins)
            self.reexport(inst.get_port('inn'), net_name='inn<%d>' % pidx, show=show_pins)
            self.reexport(inst.get_port('outp_main'), net_name='outp<%d>' % idx, show=show_pins)
            self.reexport(inst.get_port('outn_main'), net_name='outn<%d>' % idx, show=show_pins)
            self.reexport(inst.get_port('outp_d'), net_name='outp_d<%d>' % nidx, show=show_pins)
            self.reexport(inst.get_port('outn_d'), net_name='outp_d<%d>' % nidx, show=show_pins)
            self.reexport(inst.get_port('biasp_f'), net_name='bias_f<%d>' % idx, show=show_pins)
            if idx % 2 == 0:
                self.reexport(inst.get_port('biasp_m'), show=show_pins)
                self.reexport(inst.get_port('biasn_d'), show=show_pins)
            else:
                self.reexport(inst.get_port('biasp_m'), net_name='biasn_m', show=show_pins)
                self.reexport(inst.get_port('biasn_d'), net_name='biasp_d', show=show_pins)

        # connect output wires and draw shields
        out_map = [1, 7, 4, 7]
        vm_w_out = tr_manager.get_width(vm_layer, 'out')
        tr_lower = tr_upper = None
        for outp, outn, idx in zip(outp_warrs, outn_warrs, out_map):
            trp, trn = self.connect_differential_tracks(outp, outn, vm_layer, out_locs[idx],
                                                        out_locs[idx + 1], width=vm_w_out)
            if tr_lower is None:
                tr_lower = trp.lower
                tr_upper = trp.upper
            else:
                tr_lower = min(tr_lower, trp.lower)
                tr_upper = max(tr_upper, trp.upper)

        shield_pitch = out_locs[3] - out_locs[0]
        self.connect_to_tracks(vdd_list, TrackID(vm_layer, out_locs[0], num=4, pitch=shield_pitch),
                               track_lower=tr_lower, track_upper=tr_upper)

        # draw enable wires
        tr_w = tr_manager.get_width(vm_layer, 'clk')
        for tr_idx, en_warr in zip(divp_master.en_locs, en_warrs):
            self.connect_to_tracks(en_warr, TrackID(vm_layer, tr_idx, width=tr_w))
