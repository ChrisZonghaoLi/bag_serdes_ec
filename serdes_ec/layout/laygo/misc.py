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
            end_mode='The LaygoBase end_mode flag.',
            show_pins='True to show pins.',
        )

    @classmethod
    def get_default_param_values(cls):
        # type: () -> Dict[str, Any]
        return dict(
            end_mode=15,
            show_pins=True,
        )

    def draw_layout(self):
        row_layout_info = self.params['row_layout_info']
        num_col = self.params['num_col']
        tr_widths = self.params['tr_widths']
        tr_spaces = self.params['tr_spaces']
        end_mode = self.params['end_mode']
        show_pins = self.params['show_pins']

        tr_manager = TrackManager(self.grid, tr_widths, tr_spaces, half_space=True)

        self.set_rows_direct(row_layout_info, num_col=num_col, end_mode=end_mode)

        # draw substrate
        nsub = self.add_laygo_mos(0, 0, num_col)
        psub = self.add_laygo_mos(self.num_rows - 1, 0, num_col)
        vss_w, vdd_w = nsub['VSS_s'], psub['VDD_s']

        # fill space
        self.fill_space()

        # connect supply wires
        vss_intv = self.get_track_interval(0, 'ds')
        vdd_intv = self.get_track_interval(self.num_rows - 1, 'ds')
        vss = self._connect_supply(vss_w, vss_intv, tr_manager, round_up=False)
        vdd = self._connect_supply(vdd_w, vdd_intv, tr_manager, round_up=True)
        self.add_pin('VDD', vdd, show=show_pins)
        self.add_pin('VSS', vss, show=show_pins)

    def _connect_supply(self, sup_warr, sup_intv, tr_manager, round_up=False):
        # gather list of track indices and wires
        warr_list = sup_warr.to_warr_list()

        hm_layer = self.conn_layer + 1
        vm_layer = hm_layer + 1
        sup_w = tr_manager.get_width(hm_layer, 'sup')
        sup_idx = self.grid.get_middle_track(sup_intv[0], sup_intv[1] - 1, round_up=round_up)

        xl = self.laygo_info.col_to_coord(0, 's', unit_mode=True)
        xr = self.laygo_info.col_to_coord(self.laygo_size[0], 's', unit_mode=True)
        tl = self.grid.coord_to_nearest_track(vm_layer, xl, half_track=True,
                                              mode=1, unit_mode=True)
        tr = self.grid.coord_to_nearest_track(vm_layer, xr, half_track=True,
                                              mode=-1, unit_mode=True)

        num = int((tr - tl) // 2)
        tid = TrackID(vm_layer, tl, num=num, pitch=2)
        sup = self.connect_to_tracks(warr_list, TrackID(hm_layer, sup_idx, width=sup_w))
        return self.connect_to_tracks(sup, tid, min_len_mode=0)
