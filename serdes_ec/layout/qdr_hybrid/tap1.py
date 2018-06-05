# -*- coding: utf-8 -*-

"""This module defines classes needed to build the Hybrid-QDR DFE tap1 summer."""

from typing import TYPE_CHECKING, Dict, Any, Set, List, Union, Tuple

from itertools import chain

from bag.layout.util import BBox
from bag.layout.routing import TrackManager, TrackID
from bag.layout.template import TemplateBase

from abs_templates_ec.analog_core.base import AnalogBaseEnd

from .base import HybridQDRBaseInfo, HybridQDRBase
from .amp import IntegAmp
from ..laygo.divider import DividerGroup

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
        # TODO: find this properly.  We need to check if there are fg=2, gate on source
        # TODO: transistors, and if they need larger spacing
        fg_sep_out = 4
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

        # do max space fill
        bnd_box = self.bound_box
        for lay_id in range(1, hm_layer):
            self.do_max_space_fill(lay_id, bound_box=bnd_box, fill_pitch=1.5)
        self.fill_box = bnd_box

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
        self._left_edge_info = None
        self._div_grp_loc = None

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

    @property
    def left_edge_info(self):
        return self._left_edge_info

    @property
    def div_grp_loc(self):
        # type: () -> Tuple[int, int]
        return self._div_grp_loc

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

        ml_margin, mr_margin = m_master.layout_info.edge_margins
        m_arr_box = m_master.array_box
        m_bnd_box = m_master.bound_box
        # place instances
        top_layer = m_master.top_layer
        m_inst = self.add_instance(m_master, 'XMAIN', loc=(0, 0), unit_mode=True)
        y_lat = m_arr_box.top_unit + l_master.array_box.top_unit
        x_lat = m_bnd_box.right_unit - mr_margin - l_master.array_box.right_unit
        l_inst = self.add_instance(l_master, 'XLAT', loc=(x_lat, y_lat),
                                   orient='MX', unit_mode=True)
        self._div_grp_loc = (ml_margin, m_arr_box.top_unit)

        # set size
        l_bnd_box = l_inst.bound_box
        self.array_box = m_arr_box.extend(y=l_inst.array_box.top_unit, unit_mode=True)
        self.fill_box = bnd_box = m_bnd_box.extend(y=l_bnd_box.top_unit, unit_mode=True)
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

        for lay_id in range(1, top_layer - 1):
            self.do_max_space_fill(lay_id, bound_box=l_bnd_box, fill_pitch=1.5)

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
        en3_info = m_tr_info['nen3']
        tr_info = dict(
            VDD=m_tr_info['VDD'],
            VSS=m_tr_info['VSS'],
            q=m_tr_info['inp'],
            qb=m_tr_info['inn'],
            en=(en3_info[0] - 2, en3_info[1]),
            clkp=m_tr_info['clkp'],
            clkn=m_tr_info['clkn'],
            inp=m_tr_info['inp'],
            inn=m_tr_info['inn'],
            outp=m_tr_info['outp'],
            outn=m_tr_info['outn'],
            foot=m_tr_info['foot'],
            tail=m_tr_info['tail'],
        )
        self._div_tr_info = tr_info
        self._sum_row_info = m_master.row_layout_info
        self._lat_row_info = l_master.row_layout_info
        self._left_edge_info = l_master.lr_edge_info[0]

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

        ym_layer = m_master.top_layer
        if row_heights is not None and sup_tids is not None:
            sup_w = tr_manager.get_width(ym_layer - 1, 'sup')
            lat_params['vss_tid'] = (sup_tids[1][0], sup_w)
            lat_params['vdd_tid'] = (sup_tids[1][1], sup_w)

        lat_params['seg_dict'] = seg_lat
        lat_params['fg_duml'] = lat_params['fg_dumr'] = fg_dum
        lat_params['top_layer'] = None
        lat_params['end_mode'] = 8
        lat_params['sch_hp_params'] = None
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
            seg_div_tap1='number of segments dictionary for clock divider.',
            fg_dum='Number of single-sided edge dummy fingers.',
            tr_widths='Track width dictionary.',
            tr_spaces='Track spacing dictionary.',
            options='other AnalogBase options',
            row_heights='row heights for one summer.',
            sup_tids='supply tracks information for a summer.',
            sch_hp_params='Schematic high-pass filter parameters.',
            show_pins='True to create pin labels.',
            export_probe='True to export probe ports.',
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
            export_probe=False,
        )

    def draw_layout(self):
        # get parameters
        tr_widths = self.params['tr_widths']
        tr_spaces = self.params['tr_spaces']
        show_pins = self.params['show_pins']
        export_probe = self.params['export_probe']

        sum_master, end_row_master, div2_master, div3_master = self._make_masters()

        end_row_box = end_row_master.array_box
        sum_arr_box = sum_master.array_box

        # place instances
        vm_layer = top_layer = sum_master.top_layer
        bot_row = self.add_instance(end_row_master, 'XROWB', loc=(0, 0), unit_mode=True)
        y1 = ycur = end_row_box.top_unit
        inst1 = self.add_instance(sum_master, 'X1', loc=(0, ycur), unit_mode=True)
        ycur += sum_arr_box.top_unit + sum_arr_box.top_unit
        inst2 = self.add_instance(sum_master, 'X2', loc=(0, ycur), orient='MX', unit_mode=True)
        inst0 = self.add_instance(sum_master, 'X0', loc=(0, ycur), unit_mode=True)
        y3 = ycur = ycur + sum_arr_box.top_unit + sum_arr_box.top_unit
        inst3 = self.add_instance(sum_master, 'X3', loc=(0, ycur), orient='MX', unit_mode=True)
        ycur += end_row_box.top_unit
        top_row = self.add_instance(end_row_master, 'XROWT', loc=(0, ycur), orient='MX',
                                    unit_mode=True)
        inst_list = [inst0, inst1, inst2, inst3]
        self.fill_box = inst1.fill_box.merge(inst3.fill_box)
        blockage_y = [0, top_row.bound_box.top_unit]

        div_grp_x0, div_grp_y0 = sum_master.div_grp_loc
        div_grp_x = div_grp_x0 - div3_master.array_box.left_unit
        div_grp_y3 = div_grp_y0 + y1
        div_grp_y2 = y3 - div_grp_y0
        div3_inst = self.add_instance(div3_master, 'XDIV3', loc=(div_grp_x, div_grp_y3),
                                      unit_mode=True)
        div2_inst = self.add_instance(div2_master, 'XDIV2', loc=(div_grp_x, div_grp_y2),
                                      orient='MX', unit_mode=True)

        tr_manager = TrackManager(self.grid, tr_widths, tr_spaces, half_space=True)

        # re-export supply pins
        vdd_list = list(chain(div3_inst.port_pins_iter('VDD'),
                              div2_inst.port_pins_iter('VDD'),
                              *(inst.port_pins_iter('VDD') for inst in inst_list)))
        vss_list = list(chain(div3_inst.port_pins_iter('VSS'),
                              div2_inst.port_pins_iter('VSS'),
                              *(inst.port_pins_iter('VSS') for inst in inst_list)))
        vdd_list = self.connect_wires(vdd_list)
        vss_list = self.connect_wires(vss_list)
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
        en_warrs = [[div2_inst.get_pin('qb')], [div3_inst.get_pin('qb')],
                    [div2_inst.get_pin('q')], [div3_inst.get_pin('q')]]
        biasf_warrs = []
        clk_warrs = [list(chain(div2_inst.port_pins_iter('clkp'),
                                div3_inst.port_pins_iter('clkp'))),
                     list(chain(div2_inst.port_pins_iter('clkn'),
                                div3_inst.port_pins_iter('clkn')))]
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
        for en_idx, (tr_idx, en_warr) in enumerate(zip(en_locs, en_warrs)):
            en_warr = self.connect_to_tracks(en_warr, TrackID(vm_layer, tr_idx, width=vm_w_en))
            if export_probe:
                self.add_pin('en<%d>' % en_idx, en_warr, show=show_pins)

        # draw clock/bias_f wires
        vm_w_clk = tr_manager.get_width(vm_layer, 'clk')
        start_idx0 = en_locs[3] - (vm_w_en - 1) / 2
        ntr = out_locs[0] + 1 - start_idx0
        try:
            clk_locs = tr_manager.spread_wires(vm_layer, ['en', 1, 'clk', 'clk', 'clk', 'clk', 1],
                                               ntr, ('clk', ''), alignment=1, start_idx=start_idx0)
        except ValueError:
            sp_min = self.grid.get_num_space_tracks(vm_layer, vm_w_clk, half_space=True)
            clk_locs = tr_manager.spread_wires(vm_layer, ['en', 1, 'clk', 'clk', 'clk', 'clk', 1],
                                               ntr, ('clk', ''), alignment=1, start_idx=start_idx0,
                                               sp_override={('clk', 'clk'): {vm_layer: sp_min}})

        clkn, clkp = self.connect_differential_tracks(clk_warrs[1], clk_warrs[0], vm_layer,
                                                      clk_locs[2], clk_locs[5], width=vm_w_clk)
        bf0, bf3 = self.connect_differential_tracks(biasf_warrs[0], biasf_warrs[3], vm_layer,
                                                    clk_locs[3], clk_locs[4], width=vm_w_clk)
        bf2, bf1 = self.connect_differential_tracks(biasf_warrs[2], biasf_warrs[1], vm_layer,
                                                    clk_locs[3], clk_locs[4], width=vm_w_clk)
        self.add_pin('clkp', clkp, show=show_pins)
        self.add_pin('clkn', clkn, show=show_pins)
        self.add_pin('bias_f<0>', bf0, show=show_pins, edge_mode=1)
        blockage_y[1] = min(blockage_y[1], bf0.lower_unit)
        self.add_pin('bias_f<1>', bf1, show=show_pins, edge_mode=-1)
        blockage_y[0] = max(blockage_y[0], bf1.upper_unit)
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
        blockage_y[1] = min(blockage_y[1], bm0.lower_unit)
        self.add_pin('bias_m<1>', bm1, show=show_pins, edge_mode=-1)
        blockage_y[0] = max(blockage_y[0], bm1.upper_unit)
        self.add_pin('bias_m<2>', bm2, show=show_pins, edge_mode=-1)
        self.add_pin('bias_m<3>', bm3, show=show_pins, edge_mode=1)
        self.add_pin('bias_d<0>', bd0, show=show_pins, edge_mode=-1)
        self.add_pin('bias_d<1>', bd1, show=show_pins, edge_mode=-1)
        blockage_y[0] = max(blockage_y[0], bd1.upper_unit)
        self.add_pin('bias_d<2>', bd2, show=show_pins, edge_mode=1)
        blockage_y[1] = min(blockage_y[1], bd2.lower_unit)
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
            self.mark_bbox_used(vm_layer, BBox(xl, bnd_box.bottom_unit, xu, blockage_y[0],
                                               res, unit_mode=True))
            self.mark_bbox_used(vm_layer, BBox(xl, blockage_y[1], xu, bnd_box.top_unit,
                                               res, unit_mode=True))
        # draw en_div/scan wires
        tr_scan = shield_tidl - 1
        tr_en2 = tr_scan - sp_clk_shield
        tr_en_div = tr_en2 - sp_clk_shield
        scan_tid = TrackID(vm_layer, tr_scan)
        en2_tid = TrackID(vm_layer, tr_en2, width=vm_w_clk)
        en_div_tid = TrackID(vm_layer, tr_en_div)
        scan3 = self.connect_to_tracks(div3_inst.get_pin('scan_s'), scan_tid, min_len_mode=1)
        scan2 = self.connect_to_tracks(div2_inst.get_pin('scan_s'), scan_tid, min_len_mode=-1)
        self.add_pin('scan_div<3>', scan3, show=show_pins)
        self.add_pin('scan_div<2>', scan2, show=show_pins)
        self.connect_to_tracks([div3_inst.get_pin('en2'), div2_inst.get_pin('en2')], en2_tid)
        en_div = self.connect_to_tracks(div3_inst.get_pin('in'), en_div_tid, min_len_mode=1)
        self.add_pin('en_div', en_div, show=show_pins)

        # set schematic parameters
        self._sch_params = dict(
            sum_params=sum_master.sch_params['sum_params'],
            lat_params=sum_master.sch_params['lat_params'],
            div_params=div3_master.sch_params,
            export_probe=export_probe,
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
        seg_div = self.params['seg_div_tap1']
        tr_widths = self.params['tr_widths']
        tr_spaces = self.params['tr_spaces']
        options = self.params['options']

        fg_dig = DividerGroup.get_num_col(seg_div, 1)

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
            options=options,
        )
        end_row_master = self.new_template(params=end_row_params, temp_cls=AnalogBaseEnd)

        div_params = dict(
            config=config,
            lat_row_info=sum_master.lat_row_info,
            seg_dict=seg_div,
            tr_widths=tr_widths,
            tr_spaces=tr_spaces,
            div_tr_info=sum_master.div_tr_info,
            re_out_type='in',
            re_in_type='foot',
            laygo_edger=sum_master.left_edge_info,
            re_dummy=False,
            show_pins=False,
        )
        div3_master = self.new_template(params=div_params, temp_cls=DividerGroup)
        div_params['re_dummy'] = True
        div_params['clk_inverted'] = True
        div2_master = self.new_template(params=div_params, temp_cls=DividerGroup)

        return sum_master, end_row_master, div2_master, div3_master
