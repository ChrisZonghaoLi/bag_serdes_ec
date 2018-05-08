# -*- coding: utf-8 -*-

"""This module defines classes for Hybrid-QDR sampler/retimer."""

from typing import TYPE_CHECKING, Dict, Any, Set, Tuple, Union

from itertools import chain

from bag.layout.util import BBox
from bag.layout.routing.base import TrackManager, TrackID
from bag.layout.template import TemplateBase

from abs_templates_ec.analog_core.base import AnalogBase, AnalogBaseEnd

from digital_ec.layout.stdcells.core import StdDigitalTemplate
from digital_ec.layout.stdcells.inv import InvChain
from digital_ec.layout.stdcells.latch import DFlipFlopCK2, LatchCK2

from ..laygo.misc import LaygoDummy
from ..laygo.strongarm import SenseAmpStrongArm
from ..laygo.divider import SinClkDivider

if TYPE_CHECKING:
    from bag.layout.template import TemplateDB


class SenseAmpColumn(TemplateBase):
    """A column of StrongArm sense amplifiers.

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

    # input index list
    in_idx_list = [1, 0, 1, 2, 0, 3, 2, 3]
    # input type list
    in_type_list = ['dlev', 'data', 'data', 'dlev'] * 2

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
            config='laygo configuration dictionary.',
            w_dict='width dictionary.',
            th_dict='threshold dictionary.',
            seg_dict='number of segments dictionary.',
            tr_widths='Track width dictionary.',
            tr_spaces='Track spacing dictionary.',
            row_heights='row heights for one summer.',
            sup_tids='supply tracks information.',
            clk_tidx='sense amplifier clock track index.',
            options='other AnalogBase options',
            show_pins='True to draw pin geometries.',
        )

    @classmethod
    def get_default_param_values(cls):
        # type: () -> Dict[str, Any]
        return dict(
            clk_tidx=None,
            options=None,
            show_pins=True,
        )

    def draw_layout(self):
        config = self.params['config']
        w_dict = self.params['w_dict']
        th_dict = self.params['th_dict']
        seg_dict = self.params['seg_dict']
        tr_widths = self.params['tr_widths']
        tr_spaces = self.params['tr_spaces']
        row_heights = self.params['row_heights']
        sup_tids = self.params['sup_tids']
        clk_tidx = self.params['clk_tidx']
        options = self.params['options']
        show_pins = self.params['show_pins']

        # handle row_heights/substrate tracks
        top_layer = AnalogBase.get_mos_conn_layer(self.grid.tech_info) + 2
        bot_params = dict(config=config, w_dict=w_dict, th_dict=th_dict, seg_dict=seg_dict,
                          tr_widths=tr_widths, tr_spaces=tr_spaces, top_layer=top_layer,
                          draw_boundaries=True, end_mode=12, show_pins=False, export_probe=False,
                          sup_tids=sup_tids[0], min_height=row_heights[0], clk_tidx=clk_tidx)

        # create masters
        bot_master = self.new_template(params=bot_params, temp_cls=SenseAmpStrongArm)
        top_master = bot_master.new_template_with(min_height=row_heights[1], sup_tids=sup_tids[1])

        end_row_params = dict(
            lch=config['lch'],
            fg=bot_master.fg_tot,
            sub_type='ptap',
            threshold=th_dict['tail'],
            top_layer=top_layer,
            end_mode=0b11,
            guard_ring_nf=0,
            options=options,
        )
        end_row_master = self.new_template(params=end_row_params, temp_cls=AnalogBaseEnd)
        eayt = end_row_master.array_box.top_unit

        # place instances
        inst_list = []
        bayt, tayt = bot_master.array_box.top_unit, top_master.array_box.top_unit
        bot_row = self.add_instance(end_row_master, 'XROWB', loc=(0, 0), unit_mode=True)
        ycur = eayt
        for idx in range(4):
            is_even = idx % 2 == 0
            if is_even:
                m0, m1 = bot_master, top_master
            else:
                m0, m1 = top_master, bot_master
            binst = self.add_instance(m0, 'X%d' % (idx * 2), loc=(0, ycur),
                                      orient='R0', unit_mode=True)
            ycur += bayt + tayt
            tinst = self.add_instance(m1, 'X%d' % (idx * 2 + 1), loc=(0, ycur),
                                      orient='MX', unit_mode=True)
            inst_list.append(binst)
            inst_list.append(tinst)
        ycur += eayt
        top_row = self.add_instance(end_row_master, 'XROWT', loc=(0, ycur), orient='MX',
                                    unit_mode=True)

        # set size
        self.array_box = bnd_box = bot_row.bound_box.merge(top_row.bound_box)
        self.set_size_from_bound_box(top_layer, bnd_box)
        bnd_yc = bnd_box.yc_unit

        # reexport pins
        vss_list, vdd_list = [], []
        mid_en_warrs = [None, None, None, None]
        for inst, in_idx, in_type in zip(inst_list, self.in_idx_list, self.in_type_list):
            self.reexport(inst.get_port('inp'), net_name='inp_%s<%d>' % (in_type, in_idx),
                          show=show_pins)
            self.reexport(inst.get_port('inn'), net_name='inn_%s<%d>' % (in_type, in_idx),
                          show=show_pins)
            vss_list.append(inst.get_pin('VSS'))
            vdd_list.append(inst.get_pin('VDD'))
            out_idx = (in_idx - 2) % 4
            self.reexport(inst.get_port('out'), net_name='sa_%s<%d>' % (in_type, out_idx),
                          show=show_pins)
            en_name = 'en<%d>' % out_idx
            en_warr = inst.get_pin('clk')
            self.add_pin(en_name, en_warr, label=en_name + ':', show=show_pins)
            if mid_en_warrs[out_idx] is None:
                mid_en_warrs[out_idx] = en_warr
            else:
                yc_cur = self.grid.track_to_coord(en_warr.layer_id, en_warr.track_id.base_index,
                                                  unit_mode=True)
                mid_warr = mid_en_warrs[out_idx]
                yc_mid = self.grid.track_to_coord(mid_warr.layer_id, mid_warr.track_id.base_index,
                                                  unit_mode=True)
                if abs(yc_cur - bnd_yc) < abs(yc_mid - bnd_yc):
                    mid_en_warrs[out_idx] = en_warr

        for idx, en_warr in enumerate(mid_en_warrs):
            en_name = 'en<%d>' % idx
            self.add_pin('mid_' + en_name, en_warr, label=en_name + ':', show=False)

        self.add_pin('VSS', vss_list, label='VSS:', show=show_pins)
        self.add_pin('VDD', vdd_list, label='VDD:', show=show_pins)

        self._sch_params = bot_master.sch_params


class DividerColumn(TemplateBase):
    """A column of clock dividers.

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
        self._sa_clk_tidx = None

    @property
    def sch_params(self):
        # type: () -> Dict[str, Any]
        return self._sch_params

    @property
    def fg_tot(self):
        # type: () -> int
        return self._fg_tot

    @property
    def sa_clk_tidx(self):
        return self._sa_clk_tidx

    @classmethod
    def get_params_info(cls):
        # type: () -> Dict[str, str]
        return dict(
            config='laygo configuration dictionary.',
            sum_row_info='Summer row AnalogBase layout information dictionary.',
            lat_row_info='Latch row AnalogBase layout information dictionary.',
            seg_dict='Number of segments dictionary.',
            tr_widths='Track width dictionary.',
            tr_spaces='Track spacing dictionary.',
            div_tr_info='divider track information dictionary.',
            sup_tids='supply tracks information.',
            options='other AnalogBase options.',
            right_edge_info='If not None, abut on right edge.',
            show_pins='True to draw pin geometries.',
        )

    @classmethod
    def get_default_param_values(cls):
        # type: () -> Dict[str, Any]
        return dict(
            options=None,
            right_edge_info=None,
            show_pins=True,
        )

    def draw_layout(self):
        config = self.params['config']
        sum_row_info = self.params['sum_row_info']
        lat_row_info = self.params['lat_row_info']
        seg_dict = self.params['seg_dict']
        tr_widths = self.params['tr_widths']
        tr_spaces = self.params['tr_spaces']
        div_tr_info = self.params['div_tr_info']
        sup_tids = self.params['sup_tids']
        options = self.params['options']
        right_edge_info = self.params['right_edge_info']
        show_pins = self.params['show_pins']

        # create masters
        if right_edge_info is None:
            abut_mode = 0
            end_mode = 12
            draw_end_row = True
        else:
            abut_mode = 2
            end_mode = 4
            draw_end_row = False

        div_params = dict(config=config, row_layout_info=lat_row_info, seg_dict=seg_dict,
                          tr_widths=tr_widths, tr_spaces=tr_spaces, tr_info=div_tr_info, fg_min=0,
                          end_mode=end_mode, abut_mode=abut_mode, div_pos_edge=False,
                          laygo_edger=right_edge_info, show_pins=False)

        div3_master = self.new_template(params=div_params, temp_cls=SinClkDivider)
        div_params['div_pos_edge'] = True
        div2_master = self.new_template(params=div_params, temp_cls=SinClkDivider)
        self._fg_tot = div3_master.fg_tot
        self._sa_clk_tidx = div3_master.sa_clk_tidx

        dums_params = dict(config=config, row_layout_info=sum_row_info, num_col=self._fg_tot,
                           tr_widths=tr_widths, tr_spaces=tr_spaces, sup_tids=sup_tids[0],
                           end_mode=end_mode, abut_mode=abut_mode, laygo_edger=right_edge_info,
                           show_pins=False)
        dums_master = self.new_template(params=dums_params, temp_cls=LaygoDummy)
        duml_master = dums_master.new_template_with(row_layout_info=lat_row_info,
                                                    sup_tids=sup_tids[1])

        top_layer = div3_master.top_layer
        if draw_end_row:
            end_row_params = dict(
                lch=config['lch'],
                fg=self._fg_tot,
                sub_type='ptap',
                threshold=sum_row_info['row_prop_list'][0]['threshold'],
                top_layer=sum_row_info['top_layer'],
                end_mode=0b11,
                guard_ring_nf=0,
                options=options,
            )
            end_row_master = self.new_template(params=end_row_params, temp_cls=AnalogBaseEnd)
            bot_row = self.add_instance(end_row_master, 'XROWB', loc=(0, 0), unit_mode=True)
            ycur = eayt = end_row_master.array_box.top_unit
            bnd_box = bot_row.bound_box
        else:
            bnd_box = BBox(0, 0, 0, 0, self.grid.resolution, unit_mode=True)
            end_row_master = None
            ycur = eayt = 0

        # place instances
        vdd_list = []
        vss_list = []
        bayt = dums_master.array_box.top_unit
        tayt = duml_master.array_box.top_unit
        botp = topn = None
        for idx in range(4):
            is_even = idx % 2 == 0
            if is_even:
                m0, m1 = dums_master, duml_master
                if idx == 2:
                    m1 = div2_master
            else:
                m0, m1 = duml_master, dums_master
                if idx == 1:
                    m0 = div3_master
            binst = self.add_instance(m0, 'X%d' % (idx * 2), loc=(0, ycur),
                                      orient='R0', unit_mode=True)
            if m0 is div3_master:
                botp = binst
            ycur += bayt + tayt
            tinst = self.add_instance(m1, 'X%d' % (idx * 2 + 1), loc=(0, ycur),
                                      orient='MX', unit_mode=True)
            if m1 is div2_master:
                topn = tinst

            bnd_box = bnd_box.merge(tinst.bound_box)
            for inst in (binst, tinst):
                vdd_list.append(inst.get_pin('VDD'))
                vss_list.append(inst.get_pin('VSS'))

        if end_row_master is not None:
            ycur += eayt
            top_row = self.add_instance(end_row_master, 'XROWT', loc=(0, ycur), orient='MX',
                                        unit_mode=True)
            bnd_box = bnd_box.merge(top_row.bound_box)

        # set size
        self.array_box = bnd_box
        self.set_size_from_bound_box(top_layer, bnd_box)

        # export pins
        self.add_pin('VDD', vdd_list, label='VDD:', show=show_pins)
        self.add_pin('VSS', vss_list, label='VSS:', show=show_pins)
        self.reexport(topn.get_port('clk'), net_name='clkp', show=show_pins)
        self.reexport(topn.get_port('en'), net_name='en_div<2>', show=show_pins)
        self.reexport(topn.get_port('scan_s'), net_name='scan_div<2>', show=show_pins)
        self.reexport(topn.get_port('q'), net_name='en<2>', show=show_pins)
        self.reexport(topn.get_port('qb'), net_name='en<0>', show=show_pins)
        self.reexport(botp.get_port('clk'), net_name='clkn', show=show_pins)
        self.reexport(botp.get_port('en'), net_name='en_div<3>', show=show_pins)
        self.reexport(botp.get_port('scan_s'), net_name='scan_div<3>', show=show_pins)
        self.reexport(botp.get_port('q'), net_name='en<3>', show=show_pins)
        self.reexport(botp.get_port('qb'), net_name='en<1>', show=show_pins)

        self._sch_params = div3_master.sch_params


class Retimer(StdDigitalTemplate):
    """The retimer template.

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
        # type: (TemplateDB, str, Dict[str, Any], Set[str], **Any) -> None
        StdDigitalTemplate.__init__(self, temp_db, lib_name, params, used_names, **kwargs)
        self._sch_params = None
        self._ncol = None
        self._lr_vm_tidx = None

    @property
    def sch_params(self):
        # type: () -> Dict[str, Any]
        return self._sch_params

    @property
    def num_cols(self):
        # type: () -> int
        return self._ncol

    @property
    def lr_vm_tidx(self):
        # type: () -> Tuple[Union[float, int], Union[float, int]]
        return self._lr_vm_tidx

    @classmethod
    def get_params_info(cls):
        # type: () -> Dict[str, str]
        return dict(
            config='laygo configuration dictionary.',
            seg_dict='number of segments dictionary.',
            tr_widths='Track width dictionary.',
            tr_spaces='Track spacing dictionary.',
            delay_ck3='True to delay phase 3.',
            ncol_min='Minimum number of columns.',
            wp='pmos width.',
            wn='nmos width.',
            row_layout_info='Row layout information dictionary.',
            show_pins='True to draw pin geometries.',
        )

    @classmethod
    def get_default_param_values(cls):
        # type: () -> Dict[str, Any]
        return dict(
            delay_ck3=True,
            ncol_min=0,
            wp=None,
            wn=None,
            row_layout_info=None,
            show_pins=True,
        )

    def draw_layout(self):
        blk_sp = 2

        config = self.params['config']
        seg_dict = self.params['seg_dict']
        tr_widths = self.params['tr_widths']
        tr_spaces = self.params['tr_spaces']
        delay_ck3 = self.params['delay_ck3']
        ncol_min = self.params['ncol_min']
        row_layout_info = self.params['row_layout_info']
        show_pins = self.params['show_pins']

        base_params = dict(
            config=config,
            seg=seg_dict['latch'],
            tr_widths=tr_widths,
            tr_spaces=tr_spaces,
            wp=self.params['wp'],
            wn=self.params['wn'],
            row_layout_info=row_layout_info,
            show_pins=False,
        )

        # setup floorplan
        lat0_master = self.new_template(params=base_params, temp_cls=LatchCK2)
        base_params['row_layout_info'] = row_layout_info = lat0_master.row_layout_info
        self.initialize(row_layout_info, 4)

        # compute track locations
        hm_layer = self.conn_layer + 1
        ym_layer = hm_layer + 1
        tr_manager = TrackManager(self.grid, tr_widths, tr_spaces, half_space=True)
        clk0_tidx = lat0_master.get_port('clkb').get_pins()[0].track_id.base_index
        clk1_tidx = tr_manager.get_next_track(ym_layer, clk0_tidx, 'clk', 'clk', up=False)
        clk2_tidx = tr_manager.get_next_track(ym_layer, clk1_tidx, 'clk', 'clk', up=False)
        clk3_tidx = tr_manager.get_next_track(ym_layer, clk2_tidx, 'clk', 'clk', up=False)

        # make masters
        base_params['sig_locs'] = {'clkb': clk1_tidx}
        lat1_master = self.new_template(params=base_params, temp_cls=LatchCK2)
        lat_out_tidx = lat1_master.get_port('out_hm').get_pins()[0].track_id.base_index
        base_params['seg_list'] = seg_dict['buf']
        base_params['sig_locs'] = {'in': lat_out_tidx}
        buf_master = self.new_template(params=base_params, temp_cls=InvChain)
        base_params['seg'] = seg_dict['dff']
        base_params['sig_locs'] = {'clk': clk2_tidx}
        ff2_master = self.new_template(params=base_params, temp_cls=DFlipFlopCK2)
        if delay_ck3:
            base_params['sig_locs'] = {'clk': clk3_tidx}
            inst3_master = self.new_template(params=base_params, temp_cls=DFlipFlopCK2)
        else:
            inst3_master = buf_master

        # set size
        tap_ncol = self.sub_columns
        ff_ncol = ff2_master.num_cols
        lat_ncol = lat0_master.num_cols
        buf_ncol = buf_master.num_cols
        inst_ncol = max(ff_ncol, lat_ncol + blk_sp + buf_ncol)
        ncol = max(ncol_min, inst_ncol + 2 * blk_sp + 2 * tap_ncol)
        self.set_digital_size(ncol)

        # draw taps and get supplies
        vdd_list, vss_list = [], []
        for cidx in (0, tap_ncol + inst_ncol + 2 * blk_sp):
            for ridx in range(4):
                tap = self.add_substrate_tap((cidx, ridx))
                vdd_list.extend(tap.port_pins_iter('VDD'))
                vss_list.extend(tap.port_pins_iter('VSS'))
        vdd = self.connect_wires(vdd_list)
        vss = self.connect_wires(vss_list)

        # draw instances
        cidx = tap_ncol + blk_sp
        if delay_ck3:
            inst3 = self.add_digital_block(inst3_master, (cidx, 3))
        else:
            inst3 = self.add_digital_block(inst3_master, (ncol - tap_ncol - blk_sp - buf_ncol, 3))
        ff2 = self.add_digital_block(ff2_master, (cidx, 2))
        lat1 = self.add_digital_block(lat1_master, (cidx, 1))
        buf1 = self.add_digital_block(buf_master, (cidx + lat_ncol + blk_sp, 1))
        lat0 = self.add_digital_block(lat0_master, (cidx, 0))
        out_insts = [lat0, lat1, ff2, inst3]
        self.fill_space()

        self.connect_wires([lat1.get_pin('out_hm'), buf1.get_pin('in')])

        # export input/output/clk
        xm_layer = self.conn_layer + 3
        num_x_tracks = self.get_num_x_tracks(xm_layer, half_int=True)
        tr_idx = (num_x_tracks // 2) / 2
        for idx, inst in enumerate(out_insts):
            tid = self.make_x_track_id(xm_layer, idx, tr_idx)
            out_inst = buf1 if idx == 1 else inst
            warr = self.connect_to_tracks(out_inst.get_pin('out'), tid, min_len_mode=1)
            cur_tidx = warr.track_id.base_index
            if self._lr_vm_tidx is None:
                self._lr_vm_tidx = [cur_tidx, cur_tidx]
            else:
                self._lr_vm_tidx[1] = max(self._lr_vm_tidx[1], cur_tidx)
            self.add_pin('out<%d>' % idx, warr, show=show_pins)
            self.reexport(inst.get_port('in'), net_name='in<%d>' % idx, show=show_pins)
            if inst.has_port('clk'):
                if idx % 2 == 0:
                    clk_name = 'clk<2>'
                    clkb_name = 'clk<0>'
                else:
                    clk_name = 'clk<3>'
                    clkb_name = 'clk<1>'
                if idx < 2:
                    clkb = inst.get_pin('clkb', layer=ym_layer)
                    cur_tidx = clkb.track_id.base_index
                    self._lr_vm_tidx[0] = min(cur_tidx, self._lr_vm_tidx[0])
                    self.add_pin(clk_name, inst.get_pin('nclk'), label=clk_name + ':',
                                 show=show_pins)
                    self.add_pin(clkb_name, clkb, label=clkb_name + ':', show=show_pins)
                else:
                    clk = inst.get_pin('clk', layer=ym_layer)
                    cur_tidx = clk.track_id.base_index
                    self._lr_vm_tidx[0] = min(cur_tidx, self._lr_vm_tidx[0])
                    self.add_pin(clk_name, clk, label=clk_name + ':', show=show_pins)
                    self.add_pin(clkb_name, inst.get_pin('clkb_hm'), label=clkb_name + ':',
                                 show=show_pins)

        self.add_pin('VDD', vdd, show=show_pins)
        self.add_pin('VSS', vss, show=show_pins)

        self._sch_params = dict(
            ff_params=ff2_master.sch_params,
            lat_params=lat0_master.sch_params,
            buf_params=buf_master.sch_params,
            delay_ck3=delay_ck3,
        )
        self._ncol = ncol


class RetimerClkBuffer(StdDigitalTemplate):
    """The retimer clock buffer.

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
        # type: (TemplateDB, str, Dict[str, Any], Set[str], **Any) -> None
        StdDigitalTemplate.__init__(self, temp_db, lib_name, params, used_names, **kwargs)
        self._sch_params = None
        self._ncol = None
        self._r_vm_tidx = None

    @property
    def sch_params(self):
        # type: () -> Dict[str, Any]
        return self._sch_params

    @property
    def num_cols(self):
        # type: () -> int
        return self._ncol

    @property
    def r_vm_tidx(self):
        return self._r_vm_tidx

    @classmethod
    def get_params_info(cls):
        # type: () -> Dict[str, str]
        return dict(
            config='laygo configuration dictionary.',
            seg_list='clock buffer chain segments list.',
            tr_widths='Track width dictionary.',
            tr_spaces='Track spacing dictionary.',
            ncol_min='Minimum number of columns.',
            wp='pmos width.',
            wn='nmos width.',
            show_pins='True to draw pin geometries.',
        )

    @classmethod
    def get_default_param_values(cls):
        # type: () -> Dict[str, Any]
        return dict(
            ncol_min=0,
            wp=None,
            wn=None,
            show_pins=True,
        )

    def draw_layout(self):
        blk_sp = 2

        seg_list = self.params['seg_list']
        ncol_min = self.params['ncol_min']
        show_pins = self.params['show_pins']

        base_params = self.params.copy()
        base_params['show_pins'] = False
        buf_master = self.new_template(params=base_params, temp_cls=InvChain)

        tap_ncol = self.sub_columns
        buf_ncol = buf_master.num_cols
        ncol = max(ncol_min, 2 * tap_ncol + 2 * blk_sp + buf_ncol)
        self.initialize(buf_master.row_layout_info, 2, ncol)

        if len(seg_list) % 2 == 0:
            in0 = 'en<1>'
            in1 = 'en<3>'
        else:
            in0 = 'en<3>'
            in1 = 'en<1>'

        # draw taps and get supplies
        vdd_list, vss_list = [], []
        for cidx in (0, ncol - tap_ncol):
            for ridx in range(2):
                tap = self.add_substrate_tap((cidx, ridx))
                vdd_list.extend(tap.port_pins_iter('VDD'))
                vss_list.extend(tap.port_pins_iter('VSS'))
        vdd = self.connect_wires(vdd_list)
        vss = self.connect_wires(vss_list)
        self.add_pin('VDD', vdd, show=show_pins)
        self.add_pin('VSS', vss, show=show_pins)

        # draw instances
        cidx = ncol - tap_ncol - blk_sp - buf_ncol
        buf0 = self.add_digital_block(buf_master, (cidx, 0))
        buf1 = self.add_digital_block(buf_master, (cidx, 1))
        self.fill_space()

        # export output
        xm_layer = self.conn_layer + 3
        num_x_tracks = self.get_num_x_tracks(xm_layer, half_int=True)
        tr_idx = (num_x_tracks // 2) / 2
        for idx, inst, out_name, in_name in [(0, buf0, 'des_clkb', in0),
                                             (1, buf1, 'des_clk', in1)]:
            tid = self.make_x_track_id(xm_layer, idx, tr_idx)
            out_warr = inst.get_pin('out')
            self._r_vm_tidx = out_warr.track_id.base_index
            warr = self.connect_to_tracks(out_warr, tid, min_len_mode=1)
            self.add_pin(out_name, warr, show=show_pins)
            self.add_pin(in_name, inst.get_pin('in'), show=show_pins)

        self._sch_params = buf_master.sch_params
        self._ncol = ncol


class RetimerColumn(StdDigitalTemplate):
    """A class that wraps a given standard cell with proper boundaries.

    This class is usually used just for layout debugging (i.e. DRC checking).

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
        # type: (TemplateDB, str, Dict[str, Any], Set[str], **Any) -> None
        StdDigitalTemplate.__init__(self, temp_db, lib_name, params, used_names, **kwargs)
        self._sch_params = None
        self._sig_locs = None
        self._xsup = None

    @property
    def sch_params(self):
        # type: () -> Dict[str, Any]
        return self._sch_params

    @property
    def sig_locs(self):
        return self._sig_locs

    @property
    def xsup(self):
        # type: () -> int
        return self._xsup

    @classmethod
    def get_params_info(cls):
        # type: () -> Dict[str, str]
        return dict(
            config='laygo configuration dictionary.',
            seg_dict='number of segments dictionary.',
            tr_widths='Track width dictionary.',
            tr_spaces='Track spacing dictionary.',
            wp='pmos widths.',
            wn='nmos widths.',
            show_pins='True to draw pin geometries.',
        )

    @classmethod
    def get_default_param_values(cls):
        # type: () -> Dict[str, Any]
        return dict(
            wp=None,
            wn=None,
            show_pins=True,
        )

    def draw_layout(self):
        seg_dict = self.params['seg_dict']
        tr_widths = self.params['tr_widths']
        tr_spaces = self.params['tr_spaces']
        show_pins = self.params['show_pins']

        # make masters.  Make sure they have same number of columns
        blk_params = self.params.copy()
        blk_params['delay_ck3'] = True
        blk_params['show_pins'] = False
        dlev_master = self.new_template(params=blk_params, temp_cls=Retimer)
        blk_params['ncol_min'] = ncol_min = dlev_master.num_cols
        blk_params['seg_list'] = seg_dict['clk']
        buf_master = self.new_template(params=blk_params, temp_cls=RetimerClkBuffer)
        if buf_master.num_cols > ncol_min:
            ncol_min = buf_master.num_cols
            dlev_master = dlev_master.new_template_with(ncol_min=ncol_min)

        data_master = dlev_master.new_template_with(delay_ck3=False)
        if data_master.num_cols > ncol_min:
            ncol_min = data_master.num_cols
            dlev_master = dlev_master.new_template_with(ncol_min=ncol_min)
            buf_master = buf_master.new_template_with(ncol_min=ncol_min)

        ncol, nrow_retime = data_master.digital_size
        nrow_buf = buf_master.digital_size[1]
        nrow_tot = nrow_retime * 2 + nrow_buf
        self.initialize(data_master.row_layout_info, nrow_tot, ncol,
                        draw_boundaries=True, end_mode=15)

        data_inst = self.add_digital_block(data_master, (0, nrow_tot - 1))
        buf_inst = self.add_digital_block(buf_master, (0, nrow_retime))
        dlev_inst = self.add_digital_block(dlev_master, (0, nrow_retime - 1))
        self.fill_space()

        # export clock buffer pins
        for name in ('des_clk', 'des_clkb'):
            self.reexport(buf_inst.get_port(name), show=show_pins)

        # export retimer pins, and connect/export clock wires
        hm_layer = self.conn_layer + 1
        vm_layer = hm_layer + 1
        for idx in range(4):
            suf = '<%d>' % idx
            pin_name = 'out' + suf
            self.add_pin('data<%d>' % ((idx + 1) % 4), data_inst.get_pin(pin_name), show=show_pins)
            self.add_pin('dlev' + suf, dlev_inst.get_pin(pin_name), show=show_pins)
            pin_name = 'in' + suf
            self.add_pin('sa_data' + suf, data_inst.get_pin(pin_name), show=show_pins)
            self.add_pin('sa_dlev' + suf, dlev_inst.get_pin(pin_name), show=show_pins)

            clk_name = 'clk' + suf
            en_name = 'en' + suf
            hm_en_warrs = []
            vm_en_warrs = []
            hm_en_warrs.extend(buf_inst.port_pins_iter(en_name))
            hm_en_warrs.extend(data_inst.port_pins_iter(clk_name, layer=hm_layer))
            hm_en_warrs.extend(dlev_inst.port_pins_iter(clk_name, layer=hm_layer))
            vm_en_warrs.extend(data_inst.port_pins_iter(clk_name, layer=vm_layer))
            vm_en_warrs.extend(dlev_inst.port_pins_iter(clk_name, layer=vm_layer))
            en = self.connect_to_track_wires(hm_en_warrs, vm_en_warrs)[0]
            self.add_pin(en_name, en, show=show_pins)

        # compute routing/supply tracks
        l_vm_tidx = min(data_inst.translate_master_track(vm_layer, data_master.lr_vm_tidx[0]),
                        dlev_inst.translate_master_track(vm_layer, dlev_master.lr_vm_tidx[0]))
        r_vm_tidx = max(data_inst.translate_master_track(vm_layer, data_master.lr_vm_tidx[1]),
                        dlev_inst.translate_master_track(vm_layer, dlev_master.lr_vm_tidx[1]),
                        buf_inst.translate_master_track(vm_layer, buf_master.r_vm_tidx))

        tr_manager = TrackManager(self.grid, tr_widths, tr_spaces, half_space=True)
        sup_w = tr_manager.get_width(vm_layer, 'sup')
        _, r_locs = tr_manager.place_wires(vm_layer, ['sig', 'sup', 'sup'])
        deltar = r_vm_tidx - r_locs[0]
        _, l_locs = tr_manager.place_wires(vm_layer, ['sup'] + ['sig'] * 8 + ['sup', 'clk'])
        deltal = l_vm_tidx - l_locs[-1]
        self._sig_locs = tuple((l_locs[idx] + deltal for idx in range(1, 9)))
        vdd_tid = [TrackID(vm_layer, l_locs[-2] + deltal, width=sup_w),
                   TrackID(vm_layer, r_locs[1] + deltar, width=sup_w)]
        vssl_tidx = l_locs[0] + deltal
        vss_tid = [TrackID(vm_layer, vssl_tidx, width=sup_w),
                   TrackID(vm_layer, r_locs[-1] + deltar, width=sup_w)]

        self._xsup = self.grid.track_to_coord(vm_layer, vssl_tidx, unit_mode=True)

        # connect supplies
        vdd_list, vss_list = [], []
        for inst in (data_inst, dlev_inst, buf_inst):
            vdd_list.extend(inst.port_pins_iter('VDD'))
            vss_list.extend(inst.port_pins_iter('VSS'))

        for idx in range(2):
            vdd_warr = self.connect_to_tracks(vdd_list, vdd_tid[idx])
            vss_warr = self.connect_to_tracks(vss_list, vss_tid[idx])
            if idx == 1:
                self.add_pin('VDDR', vdd_warr, label='VDD', show=show_pins)
                self.add_pin('VSSR', vss_warr, label='VSS', show=show_pins)
            else:
                self.add_pin('VDDL', vdd_warr, label='VDD', show=show_pins)
                self.add_pin('VSSL', vss_warr, label='VSS', show=show_pins)

        self._sch_params = data_master.sch_params.copy()
        del self._sch_params['delay_ck3']
        self._sch_params['clk_params'] = buf_master.sch_params


class SamplerColumn(TemplateBase):
    """A class that wraps a given standard cell with proper boundaries.

    This class is usually used just for layout debugging (i.e. DRC checking).

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
        # type: (TemplateDB, str, Dict[str, Any], Set[str], **Any) -> None
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
            config='laygo configuration dictionary.',
            sa_params='sense amplifier parameters.',
            div_params='divider parameters.',
            re_params='retimer parameters.',
            tr_widths='Track width dictionary.',
            tr_spaces='Track spacing dictionary.',
            row_heights='row heights for one summer.',
            sup_tids='supply tracks information.',
            sum_row_info='Summer row AnalogBase layout information dictionary.',
            lat_row_info='Latch row AnalogBase layout information dictionary.',
            div_tr_info='divider track information dictionary.',
            options='other AnalogBase options',
            show_pins='True to draw pin geometries.',
        )

    @classmethod
    def get_default_param_values(cls):
        # type: () -> Dict[str, Any]
        return dict(
            options=None,
            show_pins=True,
        )

    def draw_layout(self):
        config = self.params['config']
        sa_params = self.params['sa_params']
        div_params = self.params['div_params']
        re_params = self.params['re_params']
        tr_widths = self.params['tr_widths']
        tr_spaces = self.params['tr_spaces']
        row_heights = self.params['row_heights']
        sup_tids = self.params['sup_tids']
        sum_row_info = self.params['sum_row_info']
        lat_row_info = self.params['lat_row_info']
        div_tr_info = self.params['div_tr_info']
        options = self.params['options']
        show_pins = self.params['show_pins']

        div_params = div_params.copy()
        div_params['config'] = config
        div_params['sum_row_info'] = sum_row_info
        div_params['lat_row_info'] = lat_row_info
        div_params['tr_widths'] = tr_widths
        div_params['tr_spaces'] = tr_spaces
        div_params['div_tr_info'] = div_tr_info
        div_params['sup_tids'] = sup_tids
        div_params['options'] = options
        div_params['show_pins'] = False
        div_master = self.new_template(params=div_params, temp_cls=DividerColumn)

        # create masters
        sa_params = sa_params.copy()
        sa_params['config'] = config
        sa_params['tr_widths'] = tr_widths
        sa_params['tr_spaces'] = tr_spaces
        sa_params['row_heights'] = row_heights
        sa_params['sup_tids'] = sup_tids
        sa_params['clk_tidx'] = div_master.sa_clk_tidx
        sa_params['options'] = options
        sa_params['show_pins'] = False
        sa_master = self.new_template(params=sa_params, temp_cls=SenseAmpColumn)

        re_params = re_params.copy()
        re_params['config'] = config
        re_params['show_pins'] = False
        re_master = self.new_template(params=re_params, temp_cls=RetimerColumn)

        # place sensamp and divider
        sa_inst = self.add_instance(sa_master, 'XSA', unit_mode=True)
        x0 = sa_inst.bound_box.right_unit
        div_inst = self.add_instance(div_master, 'XDIV', loc=(x0, 0), unit_mode=True)
        div_box = div_inst.bound_box
        x0 = div_box.right_unit

        # compute retimer placement
        vm_layer = re_master.conn_layer + 2
        tr_manager = TrackManager(self.grid, tr_widths, tr_spaces, half_space=True)

        tr0 = self.grid.coord_to_nearest_track(vm_layer, x0, half_track=True,
                                               mode=1, unit_mode=True)
        sup_loc = tr_manager.place_wires(vm_layer, ['sup'], start_idx=tr0)[1][0]

        xsup_targ = self.grid.track_to_coord(vm_layer, sup_loc, unit_mode=True)
        re_x0 = xsup_targ - re_master.xsup
        div_h = div_box.height_unit
        re_h = re_master.bound_box.height_unit
        y0 = (div_h - re_h) // 2
        re_inst = self.add_instance(re_master, 'XRE', loc=(re_x0, y0), unit_mode=True)

        # set size
        top_layer = sa_master.top_layer
        blk_w = self.grid.get_block_size(top_layer, unit_mode=True)[0]
        xr = -(-re_inst.bound_box.right_unit // blk_w) * blk_w
        self.array_box = bnd_box = sa_inst.bound_box.extend(x=xr, unit_mode=True)
        self.set_size_from_bound_box(top_layer, bnd_box)
        self.add_cell_boundary(bnd_box)

        # connect senseamp outputs
        tr_w = tr_manager.get_width(vm_layer, 'out')
        self._connect_io(sa_inst, re_inst, re_master.sig_locs, tr_w, vm_layer, show_pins)

        # connect supplies
        vdd_list = self._connect_supply(sa_inst, div_inst, re_inst, show_pins)

        # connect enable wires
        ym_layer = vm_layer + 2
        self._connect_clk(ym_layer, tr_manager, vdd_list, sa_inst, div_inst, re_inst, show_pins)

        # export retimer outputs
        for name in re_inst.port_names_iter():
            if name.startswith('data') or name.startswith('dlev') or name.startswith('des_clk'):
                self.reexport(re_inst.get_port(name), show=show_pins)

        self._sch_params = dict(
            sa_params=sa_master.sch_params,
            div_params=div_master.sch_params,
            re_params=re_master.sch_params,
        )

    def _connect_supply(self, sa_inst, div_inst, re_inst, show_pins):
        re_box = re_inst.bound_box
        re_yb, re_yt = re_box.bottom_unit, re_box.top_unit
        vddi_list = []
        vssi_list = []
        vddo_list = []
        vsso_list = []
        for pin in chain(sa_inst.port_pins_iter('VDD'), div_inst.port_pins_iter('VDD')):
            yc = self.grid.track_to_coord(pin.layer_id, pin.track_id.base_index, unit_mode=True)
            if yc < re_yb or yc > re_yt:
                vddo_list.append(pin)
            else:
                vddi_list.append(pin)
        for pin in chain(sa_inst.port_pins_iter('VSS'), div_inst.port_pins_iter('VSS')):
            yc = self.grid.track_to_coord(pin.layer_id, pin.track_id.base_index, unit_mode=True)
            if yc < re_yb or yc > re_yt:
                vsso_list.append(pin)
            else:
                vssi_list.append(pin)

        re_vdd = re_inst.get_all_port_pins('VDDR')
        re_vss = re_inst.get_all_port_pins('VSSR')
        vdd_warrs = self.connect_to_track_wires(re_vdd, vddo_list)
        vss_warrs = self.connect_to_track_wires(re_vss, vsso_list)
        re_vdd = re_inst.get_all_port_pins('VDDL')
        re_vss = re_inst.get_all_port_pins('VSSL')
        vdd_warrs.extend(self.connect_to_track_wires(re_vdd, vddi_list))
        vss_warrs.extend(self.connect_to_track_wires(re_vss, vssi_list))
        self.connect_to_track_wires(re_vdd, vddo_list)
        self.connect_to_track_wires(re_vss, vsso_list)
        self.add_pin('VDD', vdd_warrs, show=show_pins)
        self.add_pin('VSS', vss_warrs, show=show_pins)
        return vdd_warrs

    def _connect_clk(self, ym_layer, tr_manager, vdd_list, sa_inst, div_inst, re_inst, show_pins):
        xc = div_inst.get_pin('en<0>').middle_unit
        tr0 = self.grid.coord_to_nearest_track(ym_layer, xc, half_track=True, mode=-1,
                                               unit_mode=True)

        wtype_list = [1, 'clk', 'clk', 1, 'clk', 'clk', 'clk', 'clk', 1, 'clk']
        locs = tr_manager.place_wires(ym_layer, wtype_list)[1]
        dtr = tr0 - self.grid.get_middle_track(locs[5], locs[6], round_up=False)

        # connect enable signals
        tr_lower = tr_upper = self.bound_box.yc_unit
        tr_w = tr_manager.get_width(ym_layer, 'clk')
        for idx in range(4):
            en_name = 'en<%d>' % idx
            en_list = sa_inst.get_all_port_pins(en_name)
            en_list.extend(div_inst.port_pins_iter(en_name))
            ym_tr = self.connect_to_tracks(en_list, TrackID(ym_layer, locs[idx + 4] + dtr,
                                                            width=tr_w))
            tr_lower = min(tr_lower, ym_tr.lower_unit)
            tr_upper = max(tr_upper, ym_tr.upper_unit)
            en_re = re_inst.get_pin(en_name)
            self.connect_to_track_wires([ym_tr, en_re], sa_inst.get_pin('mid_en<%d>' % idx))

        # connect scan/enable signals
        scan_tid = TrackID(ym_layer, dtr + locs[-2], width=1)
        en_tid = TrackID(ym_layer, dtr + locs[-1], width=tr_w)
        for name, tid in (('scan_div<2>', scan_tid), ('scan_div<3>', scan_tid),
                          ('en_div<2>', en_tid), ('en_div<3>', en_tid)):
            warr = self.connect_to_tracks(div_inst.get_pin(name), tid, min_len_mode=0)
            self.add_pin(name, warr, show=show_pins)

        # connect shields
        sh_tid = TrackID(ym_layer, dtr + locs[0], num=2, pitch=locs[3] - locs[0])
        vdd_warrs = self.connect_to_tracks(vdd_list, sh_tid, track_lower=tr_lower,
                                           track_upper=tr_upper, unit_mode=True)
        self.add_pin('VDD', vdd_warrs, show=show_pins)

        # connect clocks
        clkp = div_inst.get_pin('clkp')
        clkn = div_inst.get_pin('clkn')
        clkp, clkn = self.connect_differential_tracks(clkp, clkn, ym_layer, dtr + locs[1],
                                                      dtr + locs[2], width=tr_w)
        self.add_pin('clkp', clkp, show=show_pins)
        self.add_pin('clkn', clkn, show=show_pins)

    def _connect_io(self, sa_inst, re_inst, sig_locs_m, tr_w, vm_layer, show_pins):
        tr_off = 0
        for idx in range(4):
            suf = '<%d>' % idx
            for name in ('sa_dlev', 'sa_data'):
                pname = name + suf
                tr_idx = re_inst.translate_master_track(vm_layer, sig_locs_m[tr_off])
                tr_off += 1
                tid = TrackID(vm_layer, tr_idx, width=tr_w)
                self.connect_to_tracks([sa_inst.get_pin(pname), re_inst.get_pin(pname)], tid)
            for name in ('inp_data', 'inn_data', 'inp_dlev', 'inn_dlev'):
                self.reexport(sa_inst.get_port(name + suf), show=show_pins)
