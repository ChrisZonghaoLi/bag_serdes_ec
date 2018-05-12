# -*- coding: utf-8 -*-

"""This module defines classes needed to build the Hybrid-QDR DFE tap1 summer."""

from typing import TYPE_CHECKING, Dict, Any, Set, List, Union, Tuple

from itertools import chain

from bag.layout.util import BBox
from bag.layout.routing import TrackManager, TrackID
from bag.layout.template import TemplateBase

from abs_templates_ec.analog_core.base import AnalogBaseEnd

from ..laygo.divider import SinClkDivider, EnableRetimer
from .base import HybridQDRBaseInfo, HybridQDRBase
from .amp import IntegAmp
from .sampler import DividerColumn


if TYPE_CHECKING:
    from bag.layout.template import TemplateDB


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
            fg_min='Minimum number of fingers.',
            options='other AnalogBase options',
            min_height='Minimum height.',
            sup_tids='supply track information.',
            sch_hp_params='Schematic high-pass filter parameters.',
            show_pins='True to create pin labels.',
        )

    @classmethod
    def get_default_param_values(cls):
        # type: () -> Dict[str, Any]
        return dict(
            fg_min=0,
            options=None,
            min_height=0,
            sup_tids=None,
            sch_hp_params=None,
            show_pins=True,
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
        options = self.params['options']
        min_height = self.params['min_height']
        sup_tids = self.params['sup_tids']
        sch_hp_params = self.params['sch_hp_params']
        show_pins = self.params['show_pins']

        if options is None:
            options = {}
        end_mode = 12

        # get track manager and wire names
        tr_manager = TrackManager(self.grid, tr_widths, tr_spaces, half_space=True)
        wire_names = {
            'tail': dict(g=['clk'], ds=['ntail']),
            'nen': dict(g=['en'], ds=['ntail']),
            'in': dict(g2=['in', 'in']),
            'pen': dict(ds2=['out', 'out'], g=['en', 'en']),
            'load': dict(ds=['ptail'], g=['clk', 'clk']),
        }

        # get total number of fingers
        hm_layer = self.mos_conn_layer + 1
        top_layer = hm_layer + 1
        qdr_info = HybridQDRBaseInfo(self.grid, lch, 0, top_layer=top_layer,
                                     end_mode=end_mode, **options)
        fg_sep_out = qdr_info.get_fg_sep_from_hm_space(tr_manager.get_width(hm_layer, 'out'),
                                                       round_even=True)
        fg_sep_hm = qdr_info.get_fg_sep_from_hm_space(tr_manager.get_width(hm_layer, 1),
                                                      round_even=True)
        fg_sep_hm = max(0, fg_sep_hm)

        main_info = qdr_info.get_integ_amp_info(seg_main, fg_dum=0, fg_sep_hm=fg_sep_hm)
        fb_info = qdr_info.get_integ_amp_info(seg_fb, fg_dum=0, fg_sep_hm=fg_sep_hm)

        fg_main = main_info['fg_tot']
        fg_amp = fg_main + fb_info['fg_tot'] + fg_sep_out
        fg_tot = max(fg_min, fg_amp + 2 * fg_dumr)
        fg_duml = fg_tot - fg_dumr - fg_amp

        self.draw_rows(lch, fg_tot, ptap_w, ntap_w, w_dict, th_dict, tr_manager,
                       wire_names, top_layer=top_layer, end_mode=end_mode,
                       min_height=min_height, **options)

        # draw amplifier
        main_ports, _ = self.draw_integ_amp(fg_duml, seg_main, fg_dum=0,
                                            fg_sep_hm=fg_sep_hm)
        col_main_end = fg_duml + fg_main
        col_fb = col_main_end + fg_sep_out
        col_mid = col_main_end + (fg_sep_out // 2)
        fb_ports, _ = self.draw_integ_amp(col_fb, seg_fb, invert=True,
                                          fg_dum=0, fg_sep_hm=fg_sep_hm)

        w_sup = tr_manager.get_width(hm_layer, 'sup')
        vss_warrs, vdd_warrs = self.fill_dummy(vdd_width=w_sup, vss_width=w_sup,
                                               sup_tids=sup_tids)
        ports_list = [main_ports, fb_ports]

        for name in ('outp', 'outn', 'en2', 'clkp', 'clkn'):
            if name == 'en2':
                wname = 'pen2'
                port_name = 'en<2>'
            else:
                wname = port_name = name
            wlist = [p[wname] for p in ports_list if wname in p]
            cur_warr = self.connect_wires(wlist)
            self.add_pin(port_name, cur_warr, show=show_pins)
        for name in ('pen3', 'nen3'):
            wlist = [p[name] for p in ports_list if name in p]
            cur_warr = self.connect_wires(wlist)
            self.add_pin('en<3>', cur_warr, label='en<3>:', show=show_pins)

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
            hp_params=sch_hp_params,
            m_dum_info=self.get_sch_dummy_info(col_start=0, col_stop=col_mid),
            f_dum_info=self.get_sch_dummy_info(col_start=col_mid, col_stop=None),
        )
        self._fg_tot = fg_tot


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
        self._fg_core_dig = None
        self._en_locs = None
        self._out_tr_info = None
        self._div_tr_info = None
        self._row_layout_info = None

    @property
    def sch_params(self):
        # type: () -> Dict[str, Any]
        return self._sch_params

    @property
    def fg_core(self):
        # type: () -> int
        return self._fg_core

    @property
    def fg_core_dig(self):
        # type: () -> int
        return self._fg_core_dig

    @property
    def en_locs(self):
        # type: () -> List[Union[int, float]]
        return self._en_locs

    @property
    def out_tr_info(self):
        # type: () -> Tuple[Union[int, float], Union[int, float], int]
        return self._out_tr_info

    @property
    def div_tr_info(self):
        # type: () -> Dict[str, Tuple[Union[float, int], int]]
        return self._div_tr_info

    @property
    def row_layout_info(self):
        # type: () -> Dict[str, Any]
        return self._row_layout_info

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
            seg_re='number of segments dictionary for enable retimer.',
            seg_pul='number of segments dictionary for pulse generation.',
            re_dummy='True to connect retimer as dummy.',
            fg_dum='Number of single-sided edge dummy fingers.',
            tr_widths='Track width dictionary.',
            tr_spaces='Track spacing dictionary.',
            div_pos_edge='True if the divider triggers off positive edge of the clock.',
            fg_min='Minimum number of core fingers.',
            fg_min_dig='Minimum number of core digital fingers.',
            options='other AnalogBase options',
            min_height='Minimum height.',
            sup_tids='supply track information.',
            show_pins='True to create pin labels.',
        )

    @classmethod
    def get_default_param_values(cls):
        # type: () -> Dict[str, Any]
        return dict(
            div_pos_edge=True,
            fg_min=0,
            fg_min_dig=0,
            options=None,
            min_height=0,
            sup_tids=None,
            show_pins=True,
        )

    def draw_layout(self):
        # get parameters
        seg_re = self.params['seg_re']
        re_dummy = self.params['re_dummy']
        tr_widths = self.params['tr_widths']
        tr_spaces = self.params['tr_spaces']
        div_pos_edge = self.params['div_pos_edge']
        show_pins = self.params['show_pins']

        l_master, d_master = self._make_masters()

        # calculate instance placements
        top_layer = l_master.top_layer
        blk_w = self.grid.get_block_size(top_layer, unit_mode=True)[0]
        core_width = d_master.bound_box.width_unit + l_master.bound_box.width_unit
        tot_width = -(-core_width // blk_w) * blk_w
        xl = (tot_width - core_width) // 2

        # place instances
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
        clkp = m_inst.get_all_port_pins('clkp')
        clkn = m_inst.get_all_port_pins('clkn')
        vdd = self.connect_wires(list(chain(m_inst.port_pins_iter('VDD'),
                                            d_inst.port_pins_iter('VDD'))))
        vss = self.connect_wires(list(chain(m_inst.port_pins_iter('VSS'),
                                            d_inst.port_pins_iter('VSS'))))
        if seg_re is None:
            div_sch_params = d_master.sch_params
            re_sch_params = None

            # perform connections for divider
            if div_pos_edge:
                clkp.extend(d_inst.port_pins_iter('clk'))
                clkp = self.connect_wires(clkp)[0]
                clkn = self.extend_wires(clkn, lower=clkp.lower_unit, unit_mode=True)
            else:
                clkn.extend(d_inst.port_pins_iter('clk'))
                clkn = self.connect_wires(clkn)[0]
                clkp = self.extend_wires(clkp, lower=clkn.lower_unit, unit_mode=True)

            # re-export divider pins
            self.reexport(d_inst.get_port('q'), net_name='div', show=show_pins)
            self.reexport(d_inst.get_port('qb'), net_name='divb', show=show_pins)
            self.reexport(d_inst.get_port('en'), net_name='en_div', show=show_pins)
            self.reexport(d_inst.get_port('scan_s'), net_name='scan_div', show=show_pins)
        else:
            div_sch_params = None
            re_sch_params = d_master.sch_params

            if re_dummy:
                EnableRetimer.connect_as_dummy(self, d_inst)
            else:
                clkp.extend(d_inst.port_pins_iter('clkp'))
                clkn.extend(d_inst.port_pins_iter('clkn'))
                clkp = self.connect_wires(clkp)
                clkn = self.connect_wires(clkn)
                self.reexport(d_inst.get_port('in'), net_name='en_div', show=show_pins)
                self.reexport(d_inst.get_port('en3'), net_name='en_div3', show=show_pins)
                self.reexport(d_inst.get_port('en2'), net_name='en_div2', show=show_pins)

        self.add_pin('VDD', vdd, show=show_pins)
        self.add_pin('VSS', vss, show=show_pins)
        self.add_pin('clkp', clkp, show=show_pins)
        self.add_pin('clkn', clkn, show=show_pins)

        # re-export tap1 pins
        self.reexport(m_inst.get_port('en<3>'), label='en<3>:', show=show_pins)
        for name in ('en<2>', 'outp', 'outn', 'inp', 'inn', 'biasp'):
            self.reexport(m_inst.get_port(name), show=show_pins)

        # compute metal 5 enable track locations
        tr_manager = TrackManager(self.grid, tr_widths, tr_spaces, half_space=True)
        inp_warr = m_inst.get_pin('inp')
        hm_layer = inp_warr.track_id.layer_id
        vm_layer = hm_layer + 1
        in_w = inp_warr.track_id.width
        tr_w = tr_manager.get_width(vm_layer, 'en')
        in_xl = inp_warr.lower_unit
        via_ext = self.grid.get_via_extensions(hm_layer, in_w, tr_w, unit_mode=True)[0]
        sp_le = self.grid.get_line_end_space(hm_layer, in_w, unit_mode=True)
        ntr, tr_locs = tr_manager.place_wires(vm_layer, ['en'] * 4)
        tr_xr = in_xl - sp_le - via_ext
        tr_right = self.grid.find_next_track(vm_layer, tr_xr, tr_width=tr_w, half_track=True,
                                             mode=-1, unit_mode=True)
        self._en_locs = [tr_idx + tr_right - tr_locs[-1] for tr_idx in tr_locs]

        self._sch_params = dict(
            div_pos_edge=div_pos_edge,
            lat_params=l_master.sch_params,
            div_params=div_sch_params,
            pul_params=None,
            re_params=re_sch_params,
            re_dummy=re_dummy,
        )
        outp_tid = m_inst.get_pin('outp').track_id
        self._out_tr_info = (outp_tid.base_index, m_inst.get_pin('outn').track_id.base_index,
                             outp_tid.width)
        self._row_layout_info = l_master.row_layout_info

    def _make_masters(self):
        dig_end_mode = 4
        dig_abut_mode = 2

        # get parameters
        config = self.params['config']
        seg_div = self.params['seg_div']
        seg_re = self.params['seg_re']
        fg_dum = self.params['fg_dum']
        tr_widths = self.params['tr_widths']
        tr_spaces = self.params['tr_spaces']
        div_pos_edge = self.params['div_pos_edge']
        fg_min = self.params['fg_min']
        fg_min_dig = self.params['fg_min_dig']

        # get layout masters
        lat_params = self.params.copy()
        del lat_params['config']
        del lat_params['seg_div']
        del lat_params['seg_lat']
        del lat_params['fg_min']
        del lat_params['fg_dum']
        lat_params['seg_dict'] = self.params['seg_lat']
        lat_params['show_pins'] = False
        lat_params['end_mode'] = 8
        lat_params['fg_duml'] = lat_params['fg_dumr'] = fg_dum

        l_master = self.new_template(params=lat_params, temp_cls=IntegAmp)
        m_tr_info = l_master.track_info
        tr_info = dict(
            VDD=m_tr_info['VDD'],
            VSS=m_tr_info['VSS'],
            q=m_tr_info['inp'],
            qb=m_tr_info['inn'],
            en=m_tr_info['nen3'],
            clkp=m_tr_info['clkp'],
            clkn=m_tr_info['clkn'],
        )
        self._div_tr_info = tr_info

        if seg_re is None:
            seg_dig = seg_div
            dig_cls = SinClkDivider
        else:
            seg_dig = seg_re
            dig_cls = EnableRetimer

        dig_params = dict(
            config=config,
            row_layout_info=l_master.row_layout_info,
            seg_dict=seg_dig,
            tr_info=tr_info,
            tr_widths=tr_widths,
            tr_spaces=tr_spaces,
            fg_min=fg_min_dig,
            end_mode=dig_end_mode,
            abut_mode=dig_abut_mode,
            div_pos_edge=div_pos_edge,
            show_pins=False,
            laygo_edger=l_master.lr_edge_info[0],
        )
        d_master = self.new_template(params=dig_params, temp_cls=dig_cls)

        self._fg_core_dig = d_master.laygo_info.core_col
        self._fg_core = l_master.layout_info.fg_core + self._fg_core_dig
        # compute fg_core, and resize main tap if necessary
        if self._fg_core < fg_min:
            fg_inc = fg_min - self._fg_core
            fg_duml = fg_dum + fg_inc
            l_master = l_master.new_template_with(fg_duml=fg_duml)
            self._fg_core = fg_min

        return l_master, d_master


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
        self._fg_tot = None
        self._fg_core = None
        self._en_locs = None
        self._data_tr_info = None
        self._div_tr_info = None
        self._sum_row_info = None
        self._lat_row_info = None

    @property
    def sch_params(self):
        # type: () -> Dict[str, Any]
        return self._sch_params

    @property
    def fg_tot(self):
        # type: () -> int
        return self._fg_tot

    @property
    def fg_core(self):
        # type: () -> int
        return self._fg_core

    @property
    def en_locs(self):
        # type: () -> List[Union[int, float]]
        return self._en_locs

    @property
    def data_tr_info(self):
        # type: () -> Tuple[Union[int, float], Union[int, float], int]
        return self._data_tr_info

    @property
    def div_tr_info(self):
        # type: () -> Dict[str, Tuple[Union[float, int], int]]
        return self._div_tr_info

    @property
    def sum_row_info(self):
        # type: () -> Dict[str, Any]
        return self._sum_row_info

    @property
    def lat_row_info(self):
        # type: () -> Dict[str, Any]
        return self._lat_row_info

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
            fg_dig='Number of fingers of digital block.',
            tr_widths='Track width dictionary.',
            tr_spaces='Track spacing dictionary.',
            options='other AnalogBase options',
            row_heights='row heights.',
            sup_tids='supply tracks information for a summer.',
            sch_hp_params='Schematic high-pass filter parameters.',
            show_pins='True to create pin labels.',
        )

    @classmethod
    def get_default_param_values(cls):
        # type: () -> Dict[str, Any]
        return dict(
            options=None,
            row_heights=None,
            sup_tids=None,
            sch_hp_params=None,
            show_pins=True,
        )

    def draw_layout(self):
        # get parameters
        tr_widths = self.params['tr_widths']
        tr_spaces = self.params['tr_spaces']
        show_pins = self.params['show_pins']

        tr_manager = TrackManager(self.grid, tr_widths, tr_spaces, half_space=True)
        l_master, m_master = self._make_masters(tr_manager)

        # place instances
        top_layer = m_master.top_layer
        m_inst = self.add_instance(m_master, 'XMAIN', loc=(0, 0), unit_mode=True)
        y0 = m_inst.array_box.top_unit + l_master.array_box.top_unit
        l_inst = self.add_instance(l_master, 'XLAT', loc=(0, y0), orient='MX', unit_mode=True)

        # set size
        self.array_box = m_inst.array_box.merge(l_inst.array_box)
        bnd_box = m_inst.bound_box.merge(l_inst.bound_box)
        self.set_size_from_bound_box(top_layer, bnd_box)
        self.add_cell_boundary(bnd_box)

        # export pins in-place
        exp_list = [(m_inst, 'outp', 'outp_m', True), (m_inst, 'outn', 'outn_m', True),
                    (m_inst, 'inp', 'inp', False), (m_inst, 'inn', 'inn', False),
                    (m_inst, 'fbp', 'fbp', False), (m_inst, 'fbn', 'fbn', False),
                    (m_inst, 'en<3>', 'en<3>', True), (m_inst, 'en<2>', 'en<2>', True),
                    (m_inst, 'VDD', 'VDD', True), (m_inst, 'VSS', 'VSS', True),
                    (m_inst, 'clkp', 'clkp', True), (m_inst, 'clkn', 'clkn', True),
                    (m_inst, 'biasp_m', 'biasp_m', False), (m_inst, 'biasp_f', 'biasp_f', False),
                    (l_inst, 'inp', 'outp_m', True), (l_inst, 'inn', 'outn_m', True),
                    (l_inst, 'outp', 'outp_d', False), (l_inst, 'outn', 'outn_d', False),
                    (l_inst, 'en<3>', 'en<2>', True), (l_inst, 'en<2>', 'en<1>', False),
                    (l_inst, 'clkp', 'clkn', True), (l_inst, 'clkn', 'clkp', True),
                    (l_inst, 'VDD', 'VDD', True), (l_inst, 'VSS', 'VSS', True),
                    (l_inst, 'biasp', 'biasn_d', False),
                    ]

        for inst, port_name, name, vconn in exp_list:
            port = inst.get_port(port_name)
            label = name + ':' if vconn else name
            self.reexport(port, net_name=name, label=label, show=show_pins)
            if inst is m_inst and (port_name == 'outp' or port_name == 'outn'):
                self.reexport(port, net_name=port_name + '_main', show=False)

        self._en_locs = self._get_en_locs(l_inst, tr_manager)

        # set schematic parameters
        l_outp_tid = l_inst.get_pin('outp').track_id
        self._sch_params = dict(
            sum_params=m_master.sch_params,
            lat_params=l_master.sch_params,
        )
        self._fg_tot = m_master.fg_tot
        self._data_tr_info = (l_outp_tid.base_index, l_inst.get_pin('outn').track_id.base_index,
                              l_outp_tid.width)
        m_tr_info = l_master.track_info
        tr_info = dict(
            VDD=m_tr_info['VDD'],
            VSS=m_tr_info['VSS'],
            q=m_tr_info['inp'],
            qb=m_tr_info['inn'],
            en=m_tr_info['nen3'],
            clkp=m_tr_info['clkp'],
            clkn=m_tr_info['clkn'],
        )
        self._div_tr_info = tr_info
        self._sum_row_info = m_master.row_layout_info
        self._lat_row_info = l_master.row_layout_info

    def _get_en_locs(self, l_inst, tr_manager):

        # compute metal 5 enable track locations
        inp_warr = l_inst.get_pin('inp')
        hm_layer = inp_warr.track_id.layer_id
        vm_layer = hm_layer + 1
        in_w = inp_warr.track_id.width
        tr_w = tr_manager.get_width(vm_layer, 'en')
        in_xl = inp_warr.lower_unit
        via_ext = self.grid.get_via_extensions(hm_layer, in_w, tr_w, unit_mode=True)[0]
        sp_le = self.grid.get_line_end_space(hm_layer, in_w, unit_mode=True)
        ntr, tr_locs = tr_manager.place_wires(vm_layer, ['en'] * 4)
        tr_xr = in_xl - sp_le - via_ext
        tr_right = self.grid.find_next_track(vm_layer, tr_xr, tr_width=tr_w, half_track=True,
                                             mode=-1, unit_mode=True)
        return [tr_idx + tr_right - tr_locs[-1] for tr_idx in tr_locs]

    def _make_masters(self, tr_manager):
        # get parameters
        seg_lat = self.params['seg_lat']
        fg_dum = self.params['fg_dum']
        fg_dig = self.params['fg_dig']
        row_heights = self.params['row_heights']
        sup_tids = self.params['sup_tids']

        sum_params = self.params.copy()
        lat_params = self.params.copy()
        lat_params['show_pins'] = sum_params['show_pins'] = False
        if row_heights is None:
            lat_params['min_height'] = sum_params['min_height'] = 0
            sum_params['sup_tids'] = None
        else:
            sum_params['min_height'] = row_heights[0]
            lat_params['min_height'] = row_heights[1]
            if sup_tids is None:
                lat_params['sup_tids'] = sum_params['sup_tids'] = None
            else:
                sum_params['sup_tids'] = sup_tids[0]

        m_master = self.new_template(params=sum_params, temp_cls=Tap1SummerRow)

        top_layer = m_master.top_layer
        if row_heights is not None and sup_tids is not None:
            sup_w = tr_manager.get_width(top_layer, 'sup')
            lat_params['vss_tid'] = (sup_tids[1][0], sup_w)
            lat_params['vdd_tid'] = (sup_tids[1][1], sup_w)

        lat_params['seg_dict'] = seg_lat
        lat_params['fg_duml'] = lat_params['fg_dumr'] = fg_dum
        lat_params['top_layer'] = top_layer
        lat_params['end_mode'] = 12
        l_master = self.new_template(params=lat_params, temp_cls=IntegAmp)

        fg_tot_lat = fg_dig + l_master.fg_tot
        if m_master.fg_tot > fg_tot_lat:
            lat_params['fg_duml'] = fg_dum + (m_master.fg_tot - fg_tot_lat)
            l_master = self.new_template(params=lat_params, temp_cls=IntegAmp)
        elif fg_tot_lat > m_master.fg_tot:
            sum_params['fg_min'] = fg_tot_lat
            m_master = self.new_template(params=sum_params, temp_cls=Tap1SummerRow)

        return l_master, m_master


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
        self._in_tr_info = None
        self._out_tr_info = None
        self._data_tr_info = None
        self._div_tr_info = None
        self._sum_row_info = None
        self._lat_row_info = None
        self._blockage_intvs = None

    @property
    def sch_params(self):
        # type: () -> Dict[str, Any]
        return self._sch_params

    @property
    def in_tr_info(self):
        # type: () -> Tuple[Union[float, int], Union[float, int], int]
        return self._in_tr_info

    @property
    def out_tr_info(self):
        # type: () -> Tuple[Union[float, int], Union[float, int], int]
        return self._out_tr_info

    @property
    def data_tr_info(self):
        # type: () -> Tuple[Union[float, int], Union[float, int], int]
        return self._data_tr_info

    @property
    def div_tr_info(self):
        # type: () -> Dict[str, Tuple[Union[float, int], int]]
        return self._div_tr_info

    @property
    def sum_row_info(self):
        # type: () -> Dict[str, Any]
        return self._sum_row_info

    @property
    def lat_row_info(self):
        # type: () -> Dict[str, Any]
        return self._lat_row_info

    @property
    def blockage_intvs(self):
        return self._blockage_intvs

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
            fg_dum='Number of single-sided edge dummy fingers.',
            tr_widths='Track width dictionary.',
            tr_spaces='Track spacing dictionary.',
            options='other AnalogBase options',
            row_heights='row heights for one summer.',
            sup_tids='supply tracks information for a summer.',
            sch_hp_params='Schematic high-pass filter parameters.',
            show_pins='True to create pin labels.',
        )

    @classmethod
    def get_default_param_values(cls):
        # type: () -> Dict[str, Any]
        return dict(
            options=None,
            row_heights=None,
            sup_tids=None,
            sch_hp_params=None,
            show_pins=True,
        )

    def draw_layout(self):
        # get parameters
        tr_widths = self.params['tr_widths']
        tr_spaces = self.params['tr_spaces']
        show_pins = self.params['show_pins']

        sum_master, end_row_master, div_master = self._make_masters()

        end_row_box = end_row_master.array_box
        sum_arr_box = sum_master.array_box

        # place instances
        vm_layer = top_layer = sum_master.top_layer
        bot_row = self.add_instance(end_row_master, 'XROWB', loc=(0, 0), unit_mode=True)
        ycur = end_row_box.top_unit
        inst1 = self.add_instance(sum_master, 'X1', loc=(0, ycur), unit_mode=True)
        ycur += sum_arr_box.top_unit + sum_arr_box.top_unit
        inst2 = self.add_instance(sum_master, 'X2', loc=(0, ycur), orient='MX', unit_mode=True)
        inst0 = self.add_instance(sum_master, 'X0', loc=(0, ycur), unit_mode=True)
        ycur += sum_arr_box.top_unit + sum_arr_box.top_unit
        inst3 = self.add_instance(sum_master, 'X3', loc=(0, ycur), orient='MX', unit_mode=True)
        ycur += end_row_box.top_unit
        top_row = self.add_instance(end_row_master, 'XROWT', loc=(0, ycur), orient='MX',
                                    unit_mode=True)
        inst_list = [inst0, inst1, inst2, inst3]

        tr_manager = TrackManager(self.grid, tr_widths, tr_spaces, half_space=True)

        # re-export supply pins
        vdd_list = list(chain(*(inst.port_pins_iter('VDD') for inst in inst_list)))
        vss_list = list(chain(*(inst.port_pins_iter('VSS') for inst in inst_list)))
        self.add_pin('VDD', vdd_list, show=show_pins)
        self.add_pin('VSS', vss_list, show=show_pins)

        # draw wires
        # compute output wire tracks
        xr = vdd_list[0].upper_unit
        tidx0 = self.grid.find_next_track(vm_layer, xr, mode=1, unit_mode=True)
        _, out_locs = tr_manager.place_wires(vm_layer, [1, 'out', 'out', 1, 'out', 'out',
                                                        1, 'out', 'out', 1], start_idx=tidx0)

        # re-export ports, and gather wires
        outp_warrs = [[], [], [], []]
        outn_warrs = [[], [], [], []]
        en_warrs = [[], [], [], []]
        biasf_warrs = []
        clk_warrs = [[], []]
        biasd_warrs = []
        biasm_warrs = []
        for idx, inst in enumerate(inst_list):
            pidx = (idx + 1) % 4
            nidx = (idx - 1) % 4
            outp_warrs[idx].extend(inst.port_pins_iter('outp_m'))
            outn_warrs[idx].extend(inst.port_pins_iter('outn_m'))
            outp_warrs[pidx].extend(inst.port_pins_iter('fbp'))
            outn_warrs[pidx].extend(inst.port_pins_iter('fbn'))
            biasf_warrs.extend(inst.port_pins_iter('biasp_f'))
            biasm_warrs.extend(inst.port_pins_iter('biasp_m'))
            biasd_warrs.extend(inst_list[pidx].port_pins_iter('biasn_d'))
            for off in range(4):
                en_pin = 'en<%d>' % off
                en_idx = (off + idx + 1) % 4
                if inst.has_port(en_pin):
                    en_warrs[en_idx].extend(inst.port_pins_iter(en_pin))
            if inst.has_port('div'):
                if idx == 2:
                    idxp, idxn = 3, 1
                else:
                    idxp, idxn = 2, 0
                en_warrs[idxp].extend(inst.port_pins_iter('div'))
                en_warrs[idxn].extend(inst.port_pins_iter('divb'))

            self.reexport(inst.get_port('inp'), net_name='inp<%d>' % pidx, show=show_pins)
            self.reexport(inst.get_port('inn'), net_name='inn<%d>' % pidx, show=show_pins)
            self.reexport(inst.get_port('outp_main'), net_name='outp<%d>' % idx, show=show_pins)
            self.reexport(inst.get_port('outn_main'), net_name='outn<%d>' % idx, show=show_pins)
            self.reexport(inst.get_port('outp_d'), net_name='outp_d<%d>' % nidx, show=show_pins)
            self.reexport(inst.get_port('outn_d'), net_name='outn_d<%d>' % nidx, show=show_pins)
            if idx % 2 == 1:
                clk_warrs[0].extend(inst.port_pins_iter('clkp'))
                clk_warrs[1].extend(inst.port_pins_iter('clkn'))
            else:
                clk_warrs[1].extend(inst.port_pins_iter('clkp'))
                clk_warrs[0].extend(inst.port_pins_iter('clkn'))

        # connect output wires
        out_map = [4, 4, 1, 1]
        vm_w_out = tr_manager.get_width(vm_layer, 'out')
        for outp, outn, idx in zip(outp_warrs, outn_warrs, out_map):
            self.connect_differential_tracks(outp, outn, vm_layer, out_locs[idx],
                                             out_locs[idx + 1], width=vm_w_out)

        # draw enable wires
        en_locs = sum_master.en_locs
        vm_w_en = tr_manager.get_width(vm_layer, 'en')
        for tr_idx, en_warr in zip(en_locs, en_warrs):
            self.connect_to_tracks(en_warr, TrackID(vm_layer, tr_idx, width=vm_w_en))

        # draw clock/bias_f wires
        vm_w_clk = tr_manager.get_width(vm_layer, 'clk')
        start_idx0 = en_locs[3] - (vm_w_en - 1) / 2
        ntr = out_locs[0] + 1 - start_idx0
        clk_locs = tr_manager.spread_wires(vm_layer, ['en', 1, 'clk', 'clk', 'clk', 'clk', 1],
                                           ntr, ('clk', ''), alignment=1, start_idx=start_idx0)

        clkn, clkp = self.connect_differential_tracks(clk_warrs[1], clk_warrs[0], vm_layer,
                                                      clk_locs[2], clk_locs[5], width=vm_w_clk)
        bf0, bf3 = self.connect_differential_tracks(biasf_warrs[0], biasf_warrs[3], vm_layer,
                                                    clk_locs[3], clk_locs[4], width=vm_w_clk)
        bf2, bf1 = self.connect_differential_tracks(biasf_warrs[2], biasf_warrs[1], vm_layer,
                                                    clk_locs[3], clk_locs[4], width=vm_w_clk)
        self.add_pin('clkp', clkp, show=show_pins)
        self.add_pin('clkn', clkn, show=show_pins)
        self.add_pin('bias_f<0>', bf0, show=show_pins, edge_mode=1)
        self.add_pin('bias_f<1>', bf1, show=show_pins, edge_mode=-1)
        self.add_pin('bias_f<2>', bf2, show=show_pins, edge_mode=-1)
        self.add_pin('bias_f<3>', bf3, show=show_pins, edge_mode=1)

        # compute bias_m/bias_d wires locations
        shield_tidr = tr_manager.get_next_track(vm_layer, en_locs[0], 'en', 1, up=False)
        sp_clk = clk_locs[3] - clk_locs[2]
        sp_clk_shield = clk_locs[2] - clk_locs[1]
        right_tidx = shield_tidr - sp_clk_shield
        bias_locs = [right_tidx + idx * sp_clk for idx in range(-3, 1, 1)]
        shield_tidl = bias_locs[0] - sp_clk_shield
        # draw shields
        self._blockage_intvs = []
        sh_tid = TrackID(vm_layer, shield_tidl, num=2, pitch=shield_tidr - shield_tidl)
        sh_warrs = self.connect_to_tracks(vss_list, sh_tid, unit_mode=True)
        tr_lower, tr_upper = sh_warrs.lower_unit, sh_warrs.upper_unit
        sh_box = sh_warrs.get_bbox_array(self.grid).get_overall_bbox()
        self._blockage_intvs.append(sh_box.get_interval('x', unit_mode=True))
        self.add_pin('VSS', sh_warrs, show=show_pins)

        sh_pitch = out_locs[3] - out_locs[0]
        out_sh_tid = TrackID(vm_layer, out_locs[0] + sh_pitch, num=2, pitch=sh_pitch)
        sh_warrs = self.connect_to_tracks(vdd_list, out_sh_tid, track_lower=tr_lower,
                                          track_upper=tr_upper, unit_mode=True)
        self.add_pin('VDD', sh_warrs, show=show_pins)

        clk_sh_tid = TrackID(vm_layer, clk_locs[1], num=2, pitch=out_locs[0] - clk_locs[1])
        sh_warrs = self.connect_to_tracks(vdd_list, clk_sh_tid, track_lower=tr_lower,
                                          track_upper=tr_upper, unit_mode=True)
        sh_box = sh_warrs.get_bbox_array(self.grid).get_overall_bbox()
        self._blockage_intvs.append(sh_box.get_interval('x', unit_mode=True))
        self.add_pin('VDD', sh_warrs, show=show_pins)
        self.add_pin('VDD_ext', sh_warrs, show=False)

        bm0, bm3 = self.connect_differential_tracks(biasm_warrs[0], biasm_warrs[3], vm_layer,
                                                    bias_locs[0], bias_locs[3], width=vm_w_clk)
        bm2, bm1 = self.connect_differential_tracks(biasm_warrs[2], biasm_warrs[1], vm_layer,
                                                    bias_locs[0], bias_locs[3], width=vm_w_clk)
        bd2, bd3 = self.connect_differential_tracks(biasd_warrs[2], biasd_warrs[3], vm_layer,
                                                    bias_locs[1], bias_locs[2], width=vm_w_clk)
        bd0, bd1 = self.connect_differential_tracks(biasd_warrs[0], biasd_warrs[1], vm_layer,
                                                    bias_locs[1], bias_locs[2], width=vm_w_clk)
        self.add_pin('bias_m<0>', bm0, show=show_pins, edge_mode=1)
        self.add_pin('bias_m<1>', bm1, show=show_pins, edge_mode=-1)
        self.add_pin('bias_m<2>', bm2, show=show_pins, edge_mode=-1)
        self.add_pin('bias_m<3>', bm3, show=show_pins, edge_mode=1)
        self.add_pin('bias_d<0>', bd0, show=show_pins, edge_mode=-1)
        self.add_pin('bias_d<1>', bd1, show=show_pins, edge_mode=-1)
        self.add_pin('bias_d<2>', bd2, show=show_pins, edge_mode=1)
        self.add_pin('bias_d<3>', bd3, show=show_pins, edge_mode=1)

        # set size
        bnd_box = bot_row.bound_box.merge(top_row.bound_box)
        bnd_xr = self.grid.track_to_coord(vm_layer, out_locs[0] + 2 * sh_pitch + 0.5,
                                          unit_mode=True)
        bnd_box = bnd_box.extend(x=bnd_xr, unit_mode=True)
        self.set_size_from_bound_box(top_layer, bnd_box)
        self.array_box = bnd_box
        self.add_cell_boundary(bnd_box)

        # mark blockages
        res = self.grid.resolution
        for xl, xu in self._blockage_intvs:
            self.mark_bbox_used(vm_layer, BBox(xl, bnd_box.bottom_unit, xu, bnd_box.top_unit,
                                               res, unit_mode=True))

        # draw en_div/scan wires
        """
        tr_scan = shield_tidl - 1
        tr_endiv = tr_scan - sp_clk_shield
        scan_tid = TrackID(vm_layer, tr_scan)
        endiv_tid = TrackID(vm_layer, tr_endiv, width=vm_w_clk)
        scan3 = self.connect_to_tracks(inst2.get_pin('scan_div'),
                                       scan_tid, min_len_mode=1)
        scan2 = self.connect_to_tracks(inst0.get_pin('scan_div'),
                                       scan_tid, min_len_mode=-1)
        endiv3 = self.connect_to_tracks(inst2.get_pin('en_div'),
                                        endiv_tid, min_len_mode=1)
        endiv2 = self.connect_to_tracks(inst0.get_pin('en_div'),
                                        endiv_tid, min_len_mode=-1)
        self.add_pin('scan_div<3>', scan3, show=show_pins)
        self.add_pin('scan_div<2>', scan2, show=show_pins)
        self.add_pin('en_div<3>', endiv3, show=show_pins)
        self.add_pin('en_div<2>', endiv2, show=show_pins)
        """
        # set schematic parameters
        self._sch_params = dict(
            sum_params=sum_master.sch_params['sum_params'],
            lat_params=sum_master.sch_params['lat_params'],
            div_params=div_master.sch_params,
        )
        inp = sum_master.get_port('inp').get_pins()[0].track_id
        inn = sum_master.get_port('inn').get_pins()[0].track_id
        outp_m = sum_master.get_port('outp_m').get_pins()[0].track_id
        outn_m = sum_master.get_port('outn_m').get_pins()[0].track_id
        self._in_tr_info = (inp.base_index, inn.base_index, inp.width)
        self._out_tr_info = (outp_m.base_index, outn_m.base_index, outp_m.width)
        self._data_tr_info = sum_master.data_tr_info
        self._div_tr_info = sum_master.div_tr_info
        self._sum_row_info = sum_master.sum_row_info
        self._lat_row_info = sum_master.lat_row_info

    def _make_masters(self):
        # get parameters
        config = self.params['config']
        lch = self.params['lch']
        seg_div = self.params['seg_div']
        tr_widths = self.params['tr_widths']
        tr_spaces = self.params['tr_spaces']
        sup_tids = self.params['sup_tids']
        options = self.params['options']

        fg_dig = DividerColumn.get_num_col(seg_div, 1)

        # make masters
        sum_params = self.params.copy()
        sum_params['fg_dig'] = fg_dig
        sum_params['seg_pul'] = None
        sum_params['div_pos_edge'] = False
        sum_params['show_pins'] = False
        sum_master = self.new_template(params=sum_params, temp_cls=Tap1Summer)

        end_row_params = dict(
            lch=lch,
            fg=sum_master.fg_tot,
            sub_type='ptap',
            threshold=self.params['th_dict']['tail'],
            top_layer=sum_master.top_layer,
            end_mode=0b11,
            guard_ring_nf=0,
            options=self.params['options'],
        )
        end_row_master = self.new_template(params=end_row_params, temp_cls=AnalogBaseEnd)

        div_params = dict(
            config=config,
            sum_row_info=sum_master.sum_row_info,
            lat_row_info=sum_master.lat_row_info,
            seg_dict=seg_div,
            tr_widths=tr_widths,
            tr_spaces=tr_spaces,
            div_tr_info=sum_master.div_tr_info,
            sup_tids=sup_tids,
            options=options,
            show_pins=False,
        )
        div_master = self.new_template(params=div_params, temp_cls=DividerColumn)

        return sum_master, end_row_master, div_master
