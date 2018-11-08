# -*- coding: utf-8 -*-

"""This package defines various passives template classes.
"""

from typing import TYPE_CHECKING, Dict, Set, Any, Tuple, Union

from itertools import chain

from bag.util.search import BinaryIterator
from bag.layout.util import BBox
from bag.layout.routing.base import TrackID, TrackManager
from bag.layout.template import TemplateBase

from abs_templates_ec.analog_core.base import AnalogBaseInfo, AnalogBase

from .passives import CMLResLoad

if TYPE_CHECKING:
    from bag.layout.template import TemplateDB


class CMLGmPMOS(AnalogBase):
    """PMOS gm cell for a CML driver.

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
        AnalogBase.__init__(self, temp_db, lib_name, params, used_names, **kwargs)
        self._sch_params = None
        self._ibias_em_specs = None

    @property
    def sch_params(self):
        # type: () -> Dict[str, Any]
        return self._sch_params

    @property
    def ibias_em_specs(self):
        # type: () -> Dict[str, Any]
        return self._ibias_em_specs

    @classmethod
    def get_params_info(cls):
        # type: () -> Dict[str, str]
        return dict(
            lch='channel length, in meters.',
            ntap_w='PMOS substrate width, in meters/number of fins.',
            w='pmos width, in meters/number of fins.',
            fg_ref='number of current mirror reference fingers per segment.',
            threshold='transistor threshold flavor.',
            out_xc_list='output coordinates on ym layer.',
            supply_tracks='supply track indices on ym layer.',
            em_specs='EM specs per segment.',
            tr_widths='Track width dictionary.',
            tr_spaces='Track spacing dictionary.',
            tot_width='Total width in resolution units.',
            guard_ring_nf='Guard ring width in number of fingers.  0 for no guard ring.',
            show_pins='True to draw pins.',
        )

    @classmethod
    def get_default_param_values(cls):
        return dict(
            guard_ring_nf=0,
            show_pins=True,
        )

    def draw_layout(self):
        lch = self.params['lch']
        ntap_w = self.params['ntap_w']
        w = self.params['w']
        fg_ref = self.params['fg_ref']
        threshold = self.params['threshold']
        out_xc_list = self.params['out_xc_list']
        supply_tracks = self.params['supply_tracks']
        em_specs = self.params['em_specs']
        tr_widths = self.params['tr_widths']
        tr_spaces = self.params['tr_spaces']
        tot_width = self.params['tot_width']
        guard_ring_nf = self.params['guard_ring_nf']
        show_pins = self.params['show_pins']

        # get AnalogBaseInfo
        hm_layer = self.mos_conn_layer + 1
        ym_layer = hm_layer + 1
        layout_info = AnalogBaseInfo(self.grid, lch, guard_ring_nf, top_layer=ym_layer,
                                     half_blk_y=False)

        # compute total number of fingers to achieve target width.
        bin_iter = BinaryIterator(2, None, step=2)
        while bin_iter.has_next():
            fg_cur = bin_iter.get_next()
            w_cur = layout_info.get_placement_info(fg_cur).tot_width
            if w_cur < tot_width:
                bin_iter.save()
                bin_iter.up()
            elif w_cur > tot_width:
                bin_iter.down()
            else:
                bin_iter.save()
                break

        fg_tot = bin_iter.get_last_save()
        # find number of tracks needed for output tracks from EM specs
        hm_tr_w_out = self.grid.get_min_track_width(hm_layer, **em_specs)
        hm_tr_sp_out = self.grid.get_num_space_tracks(hm_layer, hm_tr_w_out, half_space=True)
        hm_w = self.grid.get_track_width(hm_layer, hm_tr_w_out, unit_mode=True)
        ym_tr_w = self.grid.get_min_track_width(ym_layer, bot_w=hm_w, **em_specs, unit_mode=True)

        # construct track width/space dictionary from EM specs
        tr_manager = TrackManager(self.grid, tr_widths, tr_spaces, half_space=True)
        tr_w_dict = {
            'in': {hm_layer: tr_manager.get_width(hm_layer, 'in')},
            'out': {hm_layer: hm_tr_w_out, ym_tr_w: ym_tr_w},
        }
        tr_sp_dict = {
            ('in', 'out'): {hm_layer: max(hm_tr_sp_out,
                                          tr_manager.get_space(hm_layer, ('in', 'out')))},
        }
        tr_manager = TrackManager(self.grid, tr_w_dict, tr_sp_dict, half_space=True)

        pw_list = [w, w, w]
        pth_list = [threshold, threshold, threshold]
        wire_names = dict(
            nch=[],
            pch=[
                dict(ds=['out'],
                     g=['in'],
                     ),
                dict(g=['out'],
                     ds=['out'],
                     ds2=['out'],
                     ),
                dict(g=['in'],
                     ds=['out']),
            ],
        )
        # draw transistor rows
        self.draw_base(lch, fg_tot, ntap_w, ntap_w, [], [], pw_list, pth_list,
                       tr_manager=tr_manager, wire_names=wire_names,
                       p_orientations=['MX', 'R0', 'R0'], guard_ring_nf=guard_ring_nf,
                       pgr_w=ntap_w, ngr_w=ntap_w, top_layer=ym_layer, half_blk_y=False)

        outn_tid = self.get_wire_id('pch', 0, 'ds', wire_name='out')
        inp_tid = self.get_wire_id('pch', 0, 'g', wire_name='in')
        bias_tid = self.get_wire_id('pch', 1, 'g', wire_name='out')
        vdd_tid = self.get_wire_id('pch', 1, 'ds', wire_name='out')
        tail_tid = self.get_wire_id('pch', 1, 'ds2', wire_name='out')
        inn_tid = self.get_wire_id('pch', 2, 'g', wire_name='in')
        outp_tid = self.get_wire_id('pch', 2, 'ds', wire_name='out')

        out_pitch = out_xc_list[1] - out_xc_list[0]
        sd_pitch = layout_info.sd_pitch_unit
        if out_pitch % sd_pitch != 0:
            raise ValueError('Oops')
        fg = out_pitch // sd_pitch - fg_ref

        # draw transistors and connect
        inp_list = []
        inn_list = []
        tail_list = []
        bias_list = []
        vdd_m_list = []
        outp_list = []
        outn_list = []
        layout_info = self.layout_info
        num_out = len(out_xc_list)
        for idx, xc in enumerate(out_xc_list):
            ym_idx = self.grid.coord_to_track(ym_layer, xc, unit_mode=True)
            vtid = TrackID(ym_layer, ym_idx, width=ym_tr_w)
            # find column index that centers on given track index
            x_coord = self.grid.track_to_coord(ym_layer, ym_idx, unit_mode=True)
            col_center = layout_info.coord_to_col(x_coord, unit_mode=True)
            col_idx = col_center - (fg // 2)
            # draw transistors
            if idx == 0:
                mref = self.draw_mos_conn('pch', 1, col_idx - fg_ref, fg_ref, 2, 0,
                                          d_net='ibias', diode_conn=True, gate_pref_loc='d')
                bias_list.append(mref['g'])
                bias_list.append(mref['d'])
                vdd_m_list.append(mref['s'])

            mtop = self.draw_mos_conn('pch', 2, col_idx, fg, 2, 0, s_net='ioutp', d_net='tail')
            mbot = self.draw_mos_conn('pch', 0, col_idx, fg, 0, 2, s_net='ioutn', d_net='tail')
            mtail = self.draw_mos_conn('pch', 1, col_idx, fg, 2, 0, gate_pref_loc='s',
                                       s_net='', d_net='tail')
            mref = self.draw_mos_conn('pch', 1, col_idx + fg, fg_ref, 2, 0, gate_pref_loc='d',
                                      diode_conn=True, d_net='ibias')
            # connect
            inp_list.append(mbot['g'])
            inn_list.append(mtop['g'])
            bias_list.append(mref['g'])
            bias_list.append(mref['d'])
            bias_list.append(mtail['g'])
            tail_list.append(mtop['d'])
            tail_list.append(mbot['d'])
            tail_list.append(mtail['d'])
            vdd_m_list.append(mtail['s'])
            vdd_m_list.append(mref['s'])

            outp_h = self.connect_to_tracks(mtop['s'], outp_tid)
            outp_list.append(outp_h)
            self.add_pin('ioutp', self.connect_to_tracks(outp_h, vtid), show=show_pins)
            outn_h = self.connect_to_tracks(mbot['s'], outn_tid)
            outn_list.append(outn_h)
            self.add_pin('ioutn', self.connect_to_tracks(outn_h, vtid), show=show_pins)

        self.connect_wires(outp_list)
        self.connect_wires(outn_list)
        self.add_pin('inp', self.connect_to_tracks(inp_list, inp_tid,
                                                   track_lower=0, unit_mode=True), show=show_pins)
        self.add_pin('inn', self.connect_to_tracks(inn_list, inn_tid,
                                                   track_lower=0, unit_mode=True), show=show_pins)
        ibias = self.connect_to_tracks(bias_list, bias_tid, track_lower=0, unit_mode=True)
        self.add_pin('ibias', ibias, show=show_pins)
        self.connect_to_tracks(tail_list, tail_tid, track_lower=ibias.lower_unit,
                               track_upper=ibias.upper_unit, unit_mode=True)
        vdd_m = self.connect_to_tracks(vdd_m_list, vdd_tid)

        _, vdd_warrs = self.fill_dummy()
        vdd_warrs.append(vdd_m)
        right_tidx = 0
        for tidx in supply_tracks:
            vtid = TrackID(ym_layer, tidx, width=ym_tr_w)
            right_tidx = max(right_tidx, tidx)
            self.add_pin('VDD', self.connect_to_tracks(vdd_warrs, vtid), show=show_pins)
        for xc in out_xc_list:
            tidx = self.grid.coord_to_track(ym_layer, xc, unit_mode=True)
            vtid = TrackID(ym_layer, tidx, width=ym_tr_w)
            self.add_pin('VDD', self.connect_to_tracks(vdd_m, vtid), show=show_pins)

        self.fill_box = bnd_box = self.bound_box
        for lay in range(1, self.top_layer):
            self.do_max_space_fill(lay, bnd_box, fill_pitch=3)

        self._sch_params = dict(
            lch=lch,
            w_dict={'in': w, 'tail': w},
            th_dict={'in': threshold, 'tail': threshold},
            seg_dict={'in': fg * num_out, 'tail': fg * num_out, 'ref': fg_ref * (num_out + 1)},
            dum_info=self.get_sch_dummy_info(),
        )
        ratio = fg * num_out / (fg_ref * (num_out + 1))
        scale = num_out / ratio
        self._ibias_em_specs = em_specs.copy()
        for key in ['idc', 'iac_rms', 'iac_peak']:
            if key in em_specs:
                self._ibias_em_specs[key] *= scale


class CMLAmpPMOS(TemplateBase):
    """A PMOS CML driver.

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
        self._ibias_em_specs = None
        self._in_tid = None

    @property
    def sch_params(self):
        # type: () -> Dict[str, Any]
        return self._sch_params

    @property
    def ibias_em_specs(self):
        # type: () -> Dict[str, Any]
        return self._ibias_em_specs

    @property
    def in_tid(self):
        # type: () -> Tuple[Union[float, int], int]
        return self._in_tid

    @classmethod
    def get_params_info(cls):
        # type: () -> Dict[str, str]
        return dict(
            res_params='load resistor parameters.',
            gm_params='gm parameters.',
            em_specs='EM specs per segment.',
            tr_widths='Track width dictionary.',
            tr_spaces='Track spacing dictionary.',
            top_layer='top level layer.',
            ext_mode='output extension mode.',
            show_pins='True to draw pins.',
        )

    @classmethod
    def get_default_param_values(cls):
        # type: () -> Dict[str, Any]
        return dict(
            ext_mode=0,
            show_pins=True,
        )

    def draw_layout(self):
        # type: () -> None
        top_layer = self.params['top_layer']
        em_specs = self.params['em_specs']
        ext_mode = self.params['ext_mode']
        show_pins = self.params['show_pins']

        if self.grid.get_direction(top_layer) != 'x':
            raise ValueError('This generator only works for horizontal top level layer.')

        master_res, master_gm = self._make_masters()

        res_box = master_res.bound_box
        gm_box = master_gm.bound_box
        # get location/bounding box quantization
        blk_w, blk_h = self.grid.get_block_size(top_layer, unit_mode=True, half_blk_y=False)
        res_h = res_box.height_unit
        gm_h = gm_box.height_unit
        core_w = res_box.width_unit
        core_h = 2 * res_h + gm_h
        tot_w = -(-core_w // blk_w) * blk_w
        tot_h = -(-core_h // blk_h) * blk_h
        dx = (tot_w - core_w) // 2
        dy = (tot_h - core_h) // 2
        # place instances
        loc = (dx, dy + res_h)
        res_bot = self.add_instance(master_res, 'XRB', loc, orient='MX', unit_mode=True)
        gm = self.add_instance(master_gm, 'XGM', loc, unit_mode=True)
        res_top = self.add_instance(master_res, 'XRT', (dx, dy + res_h + gm_h), unit_mode=True)

        # set size
        self.fill_box = fill_box = res_bot.fill_box.merge(res_top.fill_box)
        self.array_box = bnd_box = BBox(0, 0, tot_w, tot_h, self.grid.resolution, unit_mode=True)
        self.set_size_from_bound_box(top_layer, bnd_box)
        self.add_cell_boundary(bnd_box)

        # re-export pins
        for name in ['inp', 'inn', 'ibias']:
            self.reexport(gm.get_port(name), show=show_pins)

        # connect outputs and supplies to upper layer
        outp_list = list(chain(res_top.port_pins_iter('out'), gm.port_pins_iter('ioutp')))
        outn_list = list(chain(res_bot.port_pins_iter('out'), gm.port_pins_iter('ioutn')))
        outp_list = self.connect_wires(outp_list)[0].to_warr_list()
        outn_list = self.connect_wires(outn_list)[0].to_warr_list()
        vdd_list = gm.get_all_port_pins('VDD')
        vsst_list = res_top.get_all_port_pins('VSS')
        vssb_list = res_bot.get_all_port_pins('VSS')
        for warrs, name, v_mode in [(outp_list, 'outp', 1), (outn_list, 'outn', -1),
                                    (vdd_list, 'VDD', 0), (vsst_list, 'VSS', 1),
                                    (vssb_list, 'VSS', -1)]:
            lay_id = warrs[0].layer_id
            xc_list = sorted((self.grid.track_to_coord(lay_id, w.track_id.base_index,
                                                       unit_mode=True) for w in warrs))
            warrs = CMLResLoad.connect_up_layers(self, lay_id, warrs, xc_list, top_layer, em_specs,
                                                 v_mode=v_mode)
            lbl = 'VSS:' if name == 'VSS' else name
            if ext_mode > 0:
                warrs = self.extend_wires(warrs, upper=self.bound_box.right_unit,
                                          unit_mode=True)
            elif ext_mode < 0:
                warrs = self.extend_wires(warrs, lower=self.bound_box.left_unit,
                                          unit_mode=True)
            self.add_pin(name, warrs, label=lbl, show=show_pins)

        # do fill
        ym_layer = vdd_list[0].layer_id
        for lay in range(ym_layer, top_layer + 1):
            self.do_max_space_fill(lay, fill_box, fill_pitch=3)

        # schematic parameters
        self._sch_params = dict(
            res_params=master_res.sch_params,
            gm_params=master_gm.sch_params,
        )
        # properties
        self._ibias_em_specs = master_gm.ibias_em_specs
        inn = gm.get_pin('inn')
        hm_layer = inn.layer_id
        tr0 = self.grid.find_next_track(hm_layer, self.bound_box.yc_unit, half_track=True,
                                        mode=1, unit_mode=True)
        self._in_tid = (inn.track_id.base_index - tr0, inn.width)

    def _make_masters(self):
        res_params = self.params['res_params']
        gm_params = self.params['gm_params']
        em_specs = self.params['em_specs']
        tr_widths = self.params['tr_widths']
        tr_spaces = self.params['tr_spaces']

        gm_params = gm_params.copy()
        res_params = res_params.copy()

        tr_manager = TrackManager(self.grid, tr_widths, tr_spaces, half_space=True)

        hm_layer = AnalogBase.get_mos_conn_layer(self.grid.tech_info) + 1
        sub_tr_w = tr_manager.get_width(hm_layer, 'sup')
        res_params['sub_lch'] = gm_params['lch']
        res_params['sub_type'] = 'ptap'
        res_params['threshold'] = gm_params['threshold']
        res_params['em_specs'] = em_specs
        res_params['sub_tr_w'] = sub_tr_w
        res_params['show_pins'] = False

        master_res = self.new_template(params=res_params, temp_cls=CMLResLoad)

        gm_params['out_xc_list'] = master_res.out_xc_list
        gm_params['supply_tracks'] = master_res.sup_tracks
        gm_params['em_specs'] = em_specs
        gm_params['tr_widths'] = tr_widths
        gm_params['tr_spaces'] = tr_spaces
        gm_params['tot_width'] = master_res.bound_box.width_unit
        gm_params['show_pins'] = False

        master_gm = self.new_template(params=gm_params, temp_cls=CMLGmPMOS)

        return master_res, master_gm
