# -*- coding: utf-8 -*-

"""This module contains miscellaneous LaygoBase generators."""


from typing import TYPE_CHECKING, Dict, Any, Set

from bag.layout.routing.base import TrackManager, TrackID

from abs_templates_ec.laygo.core import LaygoBase

if TYPE_CHECKING:
    from bag.layout.template import TemplateDB


class LaygoDummy(LaygoBase):
    """A dummy laygo cell to test AnalogBase-LaygoBase pitch matching.

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
    **kwargs :
        dictionary of optional parameters.  See documentation of
        :class:`bag.layout.template.TemplateBase` for details.
    """

    def __init__(self, temp_db, lib_name, params, used_names, **kwargs):
        # type: (TemplateDB, str, Dict[str, Any], Set[str], **kwargs) -> None
        LaygoBase.__init__(self, temp_db, lib_name, params, used_names, **kwargs)
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
            row_layout_info='The AnalogBase information dictionary.',
            num_col='Number of laygo olumns.',
            tr_widths='Track width dictionary.',
            tr_spaces='Track spacing dictionary.',
            sup_tids='supply track information.',
            end_mode='The LaygoBase end_mode flag.',
            abut_mode='The left/right abut mode flag.',
            abut_sp='Abutment space.',
            show_pins='True to show pins.',
        )

    @classmethod
    def get_default_param_values(cls):
        # type: () -> Dict[str, Any]
        return dict(
            sup_tids=None,
            end_mode=15,
            abut_mode=0,
            abut_sp=2,
            show_pins=True,
        )

    def draw_layout(self):
        row_layout_info = self.params['row_layout_info']
        num_col = self.params['num_col']
        tr_widths = self.params['tr_widths']
        tr_spaces = self.params['tr_spaces']
        sup_tids = self.params['sup_tids']
        end_mode = self.params['end_mode']
        abut_mode = self.params['abut_mode']
        abut_sp = self.params['abut_sp']
        show_pins = self.params['show_pins']

        hm_layer = self.conn_layer + 1
        xm_layer = hm_layer + 2
        tr_manager = TrackManager(self.grid, tr_widths, tr_spaces, half_space=True)
        hm_w_sup = tr_manager.get_width(hm_layer, 'sup')
        xm_w_sup = tr_manager.get_width(xm_layer, 'sup')

        inc_col = 0
        if abut_mode & 1 != 0:
            # abut on left
            inc_col += abut_sp
            col_start = abut_sp
        else:
            col_start = 0
        if abut_mode & 2 != 0:
            # abut on right
            inc_col += abut_sp

        self.set_rows_direct(row_layout_info, num_col=num_col, end_mode=end_mode)

        # draw substrate
        vss_w, vdd_w = self._draw_substrate(col_start, num_col, num_col - inc_col)

        # fill space
        self.fill_space()

        # connect supply wires
        vss_intv = self.get_track_interval(0, 'ds')
        vdd_intv = self.get_track_interval(self.num_rows - 1, 'ds')
        vss = self._connect_supply(vss_w, vss_intv, hm_w_sup, round_up=False)
        vdd = self._connect_supply(vdd_w, vdd_intv, hm_w_sup, round_up=True)

        if sup_tids is not None:
            vdd = self.connect_to_tracks(vdd, TrackID(xm_layer, sup_tids[1], width=xm_w_sup))
            vss = self.connect_to_tracks(vss, TrackID(xm_layer, sup_tids[0], width=xm_w_sup))

        self.add_pin('VDD', vdd, show=show_pins)
        self.add_pin('VSS', vss, show=show_pins)

        # do max space fill
        for lay_id in range(1, xm_layer):
            self.do_max_space_fill(lay_id)
        self.fill_box = self.bound_box

    def _draw_substrate(self, col_start, col_stop, num_col):
        if col_start > 0:
            self.add_laygo_mos(0, 0, col_start)
            self.add_laygo_mos(self.num_rows - 1, 0, col_start)
        sub_stop = col_start + num_col
        nadd = col_stop - sub_stop
        if nadd > 0:
            self.add_laygo_mos(0, sub_stop, nadd)
            self.add_laygo_mos(self.num_rows - 1, sub_stop, nadd)

        nsub = self.add_laygo_mos(0, col_start, num_col)
        psub = self.add_laygo_mos(self.num_rows - 1, col_start, num_col)
        return nsub['VSS_s'], psub['VDD_s']

    def _connect_supply(self, sup_warr, sup_intv, hm_w_sup, round_up=False):
        # gather list of track indices and wires
        warr_list = sup_warr.to_warr_list()
        min_tid = max_tid = None
        for warr in warr_list:
            tid = warr.track_id.base_index
            if min_tid is None:
                min_tid = max_tid = tid
            else:
                min_tid = min(tid, min_tid)
                max_tid = max(tid, max_tid)

        hm_layer = self.conn_layer + 1
        vm_layer = hm_layer + 1
        sup_idx = self.grid.get_middle_track(sup_intv[0], sup_intv[1] - 1, round_up=round_up)

        xl = self.grid.track_to_coord(self.conn_layer, min_tid, unit_mode=True)
        xr = self.grid.track_to_coord(self.conn_layer, max_tid, unit_mode=True)
        tl = self.grid.coord_to_nearest_track(vm_layer, xl, half_track=True,
                                              mode=1, unit_mode=True)
        tr = self.grid.coord_to_nearest_track(vm_layer, xr, half_track=True,
                                              mode=-1, unit_mode=True)

        num = int((tr - tl + 2) // 2)
        tid = TrackID(vm_layer, tl, num=num, pitch=2)
        sup = self.connect_to_tracks(warr_list, TrackID(hm_layer, sup_idx, width=hm_w_sup))
        return self.connect_to_tracks(sup, tid, min_len_mode=0)
