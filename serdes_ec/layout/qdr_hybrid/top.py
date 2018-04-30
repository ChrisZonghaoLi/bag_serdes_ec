# -*- coding: utf-8 -*-

"""This module defines classes needed to build the Hybrid-QDR FFE/DFE summer."""

from typing import TYPE_CHECKING, Dict, Any, Set

from bag.layout.util import BBox
from bag.layout.template import TemplateBase

from .datapath import RXDatapath

if TYPE_CHECKING:
    from bag.layout.template import TemplateDB


class RXFrontend(TemplateBase):
    """The receiver datapath.

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
    def get_params_info(cls):
        # type: () -> Dict[str, str]
        return dict(
            config='Laygo configuration dictionary for the divider.',
            ptap_w='NMOS substrate width, in meters/number of fins.',
            ntap_w='PMOS substrate width, in meters/number of fins.',
            sum_params='summer parameters dictionary.',
            hp_params='highpass filter parameters dictionary.',
            samp_params='sampler parameters dictionary.',
            fg_dum='Number of single-sided edge dummy fingers.',
            tr_widths='Track width dictionary.',
            tr_spaces='Track spacing dictionary.',
            fill_config='Fill configuration dictionary.',
            ana_options='other AnalogBase options',
            show_pins='True to create pin labels.',
        )

    @classmethod
    def get_default_param_values(cls):
        # type: () -> Dict[str, Any]
        return dict(
            ana_options=None,
            show_pins=True,
        )

    def draw_layout(self):
        ml, mt, mb = 30000, 20000, 20000

        fill_config = self.params['fill_config']
        show_pins = self.params['show_pins']

        params = self.params.copy()
        params['show_pins'] = False
        master = self.new_template(params=params, temp_cls=RXDatapath)
        top_layer = master.top_layer
        bnd_box = master.bound_box
        blk_w, blk_h = self.grid.get_fill_size(top_layer, fill_config, unit_mode=True)
        tot_w = -(-(bnd_box.width_unit + ml) // blk_w) * blk_w
        tot_h = -(-(bnd_box.height_unit + mt + mb) // blk_h) * blk_h
        x0 = tot_w - bnd_box.width_unit
        y0 = (tot_h - bnd_box.height_unit) // 2
        inst = self.add_instance(master, 'XDATA', loc=(x0, y0), unit_mode=True)
        bnd_box = BBox(0, 0, tot_w, tot_h, self.grid.resolution, unit_mode=True)
        self.set_size_from_bound_box(master.top_layer, bnd_box)
        self.array_box = bnd_box
        self.add_cell_boundary(bnd_box)

        for name in inst.port_names_iter():
            self.reexport(inst.get_port(name), show=show_pins)

        self._sch_params = master.sch_params
