# -*- coding: utf-8 -*-

"""This module defines layout generator for the TX datapath."""

from typing import TYPE_CHECKING, Dict, Set, Any

import yaml

from bag.layout.util import BBox
from bag.layout.routing.base import TrackManager
from bag.layout.template import TemplateBase, BlackBoxTemplate

from ..analog.cml import CMLAmpPMOS
from .ser import Serializer32

if TYPE_CHECKING:
    from bag.layout.template import TemplateDB


class TXDatapath(TemplateBase):
    """TX datapath, which consists of serializer and output driver.

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
            esd_fname='ESD diode configuration file name.',
            ser_params='serializer parameters.',
            amp_params='amplifier parameters.',
            tr_widths='Track width dictionary.',
            tr_spaces='Track spacing dictionary.',
            fill_config='fill configuration dictionary.',
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
        fill_config = self.params['fill_config']
        show_pins = self.params['show_pins']

        tr_manager = TrackManager(self.grid, tr_widths, tr_spaces, half_space=True)

        # make masters and get information
        master_ser, master_amp, master_esd = self._make_masters()
        ym_layer = master_ser.top_layer
        top_layer = master_amp.top_layer
        box_ser = master_ser.bound_box
        box_amp = master_amp.bound_box
        box_esd = master_esd.bound_box
        h_ser = box_ser.height_unit
        h_amp = box_amp.height_unit
        h_esd = box_esd.height_unit

        # compute horizontal placement
        w_blk, h_blk = self.grid.get_block_size(top_layer, unit_mode=True)
        x_ser = 0
        x_amp = -(-(x_ser + box_ser.width_unit) // w_blk) * w_blk
        x_esd = x_amp + box_amp.width_unit
        w_tot = -(-(x_esd + box_esd.width_unit) // w_blk) * w_blk

        # compute vertical placement
        h_tot = -(-max(h_ser, h_amp, 2 * h_esd) // h_blk) * h_blk
        y_ser = (h_tot - h_ser) // 2
        y_amp = (h_tot - h_amp) // 2
        y_esd = h_tot // 2

        # place masters
        ser = self.add_instance(master_ser, 'XSER', loc=(x_ser, y_ser), unit_mode=True)
        amp = self.add_instance(master_amp, 'XAMP', loc=(x_ser, y_amp), unit_mode=True)
        esdt = self.add_instance(master_esd, 'XESDT', loc=(x_esd, y_esd), unit_mode=True)
        esdb = self.add_instance(master_esd, 'XESDB', loc=(x_esd, y_esd), orient='MX',
                                 unit_mode=True)

        # set size
        res = self.grid.resolution
        self.array_box = bnd_box = BBox(0, 0, w_tot, h_tot, res, unit_mode=True)
        self.set_size_from_bound_box(top_layer, bnd_box)
        self.add_cell_boundary(bnd_box)

        self._sch_params = dict(
            ser_params=master_ser.sch_params,
            amp_params=master_amp.sch_params,
            esd_params=master_esd.sch_params,
        )

    def _make_masters(self):
        esd_fname = self.params['esd_fname']
        ser_params = self.params['ser_params'].copy()
        amp_params = self.params['amp_params'].copy()
        tr_widths = self.params['tr_widths']
        tr_spaces = self.params['tr_spaces']
        fill_config = self.params['fill_config']

        with open(esd_fname, 'r') as f:
            esd_params = yaml.load(f)

        ser_params['tr_widths'] = tr_widths
        ser_params['tr_spaces'] = tr_spaces
        ser_params['fill_config'] = fill_config
        ser_params['show_pins'] = False
        master_ser = self.new_template(params=ser_params, temp_cls=Serializer32)

        amp_params['tr_widths'] = tr_widths
        amp_params['tr_spaces'] = tr_spaces
        amp_params['show_pins'] = False
        master_amp = self.new_template(params=amp_params, temp_cls=CMLAmpPMOS)

        esd_params['show_pins'] = False
        master_esd = self.new_template(params=esd_params, temp_cls=BlackBoxTemplate)

        return master_ser, master_amp, master_esd
