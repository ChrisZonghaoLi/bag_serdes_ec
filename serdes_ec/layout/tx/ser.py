# -*- coding: utf-8 -*-

"""This module defines layout generator for the TX serializer."""

from typing import TYPE_CHECKING, Dict, Set, Any

import yaml

from bag.layout.util import BBox
from bag.layout.routing.base import TrackManager
from bag.layout.template import TemplateBase, BlackBoxTemplate

from ..qdr_hybrid.sampler import DividerColumn

if TYPE_CHECKING:
    from bag.layout.template import TemplateDB


class Serializer32(TemplateBase):
    """32-to-1 serializer built with primitives.

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

    @property
    def sch_params(self):
        return self._sch_params

    @classmethod
    def get_params_info(cls):
        return dict(
            ser16_fname='16-to-1 serializer configuration file.',
            mux_fname='2-to-1 mux configuration file.',
            div_params='divider parameters.',
            tr_widths='Track width dictionary.',
            tr_spaces='Track spacing dictionary.',
            show_pins='True to draw pin layouts.',
        )

    @classmethod
    def get_default_param_values(cls):
        return dict(
            show_pins=True,
        )

    def draw_layout(self):
        tr_widths = self.params['tr_widths']
        tr_spaces = self.params['tr_spaces']
        show_pins = self.params['show_pins']

        tr_manager = TrackManager(self.grid, tr_widths, tr_spaces, half_space=True)

        # make masters and get information
        master_ser, master_mux, master_div = self._make_masters()
        hm_layer = master_ser.top_layer + 1
        top_layer = ym_layer = hm_layer + 1
        box_ser = master_ser.bound_box
        box_mux = master_mux.bound_box
        box_div = master_div.bound_box
        h_ser = box_ser.height_unit
        h_div = box_div.height_unit
        h_mux = box_mux.height_unit

        # compute horizontal placement
        w_blk, h_blk = self.grid.get_block_size(top_layer, unit_mode=True)
        ntr, clk_locs = tr_manager.place_wires(ym_layer, ['sh', 'clk', 'clk', 'sh'])
        w_route = ntr * self.grid.get_track_pitch(ym_layer, unit_mode=True)
        x_ser = 0
        x_route = x_ser + box_ser.width_unit
        x_div = -(-(x_route + w_route) // w_blk) * w_blk
        x_mux = x_div + box_div.width_unit
        w_tot = x_mux + box_mux.width_unit
        w_tot = -(-w_tot // w_blk) * w_blk

        # compute vertical placement
        h_tot = max(2 * h_ser, h_div, h_mux)
        y_div = (h_tot - h_div) // 2
        y_mux = (h_tot - h_mux) // 2

        # place masters
        inst_serb = self.add_instance(master_ser, 'XSERB', loc=(x_ser, 0), unit_mode=True)
        inst_sert = self.add_instance(master_ser, 'XSERT', loc=(x_ser, h_tot), orient='MX',
                                      unit_mode=True)
        inst_div = self.add_instance(master_div, 'XDIV', loc=(x_div, y_div), unit_mode=True)
        inst_mux = self.add_instance(master_mux, 'XMUX', loc=(x_mux, y_mux), unit_mode=True)

        # set size
        res = self.grid.resolution
        self.array_box = bnd_box = BBox(0, 0, w_tot, h_tot, res, unit_mode=True)
        self.set_size_from_bound_box(top_layer, bnd_box)
        self.add_cell_boundary(bnd_box)

        self._sch_params = dict(

        )

    def _make_masters(self):
        ser16_fname = self.params['ser16_fname']
        mux_fname = self.params['mux_fname']
        div_params = self.params['div_params']
        tr_widths = self.params['tr_widths']
        tr_spaces = self.params['tr_spaces']

        with open(ser16_fname, 'r') as f:
            ser_params = yaml.load(f)
        with open(mux_fname, 'r') as f:
            mux_params = yaml.load(f)

        ser_params['show_pins'] = False
        master_ser = self.new_template(params=ser_params, temp_cls=BlackBoxTemplate)

        mux_params['show_pins'] = False
        master_mux = self.new_template(params=mux_params, temp_cls=BlackBoxTemplate)

        div_params['show_pins'] = False
        div_params['tr_widths'] = tr_widths
        div_params['tr_spaces'] = tr_spaces
        master_div = self.new_template(params=div_params, temp_cls=DividerColumn)

        return master_ser, master_mux, master_div
