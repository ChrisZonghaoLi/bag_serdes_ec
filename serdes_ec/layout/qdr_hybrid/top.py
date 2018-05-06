# -*- coding: utf-8 -*-

"""This module defines classes needed to build the Hybrid-QDR FFE/DFE summer."""

from typing import TYPE_CHECKING, Dict, Any, Set

from bag.layout.util import BBox
from bag.layout.template import TemplateBase

from analog_ec.layout.dac.rladder.top import RDACArray

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
            fill_w='supply fill wire width.',
            fill_sp='supply fill spacing.',
            fill_margin='space between supply fill and others.',
            fill_config='Fill configuration dictionary.',
            ana_options='other AnalogBase options',
            sch_hp_params='schematic high-pass parameters.',
            show_pins='True to create pin labels.',
        )

    @classmethod
    def get_default_param_values(cls):
        # type: () -> Dict[str, Any]
        return dict(
            fill_w=2,
            fill_sp=1,
            fill_margin=0,
            ana_options=None,
            show_pins=True,
        )

    def draw_layout(self):
        ml, mt, mb = 30000, 20000, 20000

        fill_config = self.params['fill_config']
        sch_hp_params = self.params['sch_hp_params']
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

        self._sch_params = master.sch_params.copy()
        self._sch_params['hp_params'] = sch_hp_params


class RXTop(TemplateBase):
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
            fe_params='RX frontend parameters.',
            dac_params='RX DAC parameters.',
            fill_config='fill configuration dictionary.',
            bias_config='bias configuration dictionary.',
            fill_orient_mode='fill orientation mode.',
            show_pins='True to show pins.',
        )

    @classmethod
    def get_default_param_values(cls):
        # type: () -> Dict[str, Any]
        return dict(
            fill_orient_mode=0,
            show_pins=True,
        )

    def draw_layout(self):
        fe_params = self.params['fe_params'].copy()
        dac_params = self.params['dac_params'].copy()
        fill_config = self.params['fill_config']
        bias_config = self.params['bias_config']
        fill_orient_mode = self.params['fill_orient_mode']
        show_pins = self.params['show_pins']

        fe_params['fill_config'] = dac_params['fill_config'] = fill_config
        fe_params['bias_config'] = dac_params['bias_config'] = bias_config
        fe_params['fill_orient_mode'] = fill_orient_mode
        dac_params['fill_orient_mode'] = fill_orient_mode ^ 2
        fe_params['show_pins'] = dac_params['show_pins'] = False

        master_fe = self.new_template(params=fe_params, temp_cls=RXFrontend)
        master_dac = self.new_template(params=dac_params, temp_cls=RDACArray)
        box_fe = master_fe.bound_box
        box_dac = master_dac.bound_box

        top_layer = master_dac.top_layer
        w_fe = box_fe.width_unit
        w_dac = box_dac.width_unit
        w_tot = max(w_fe, w_dac)
        x_fe = w_tot - w_fe
        x_dac = w_tot - w_dac
        h_tot = box_fe.height_unit + box_dac.height_unit

        inst_fe = self.add_instance(master_fe, 'XFE', loc=(x_fe, 0), unit_mode=True)
        inst_dac = self.add_instance(master_dac, 'XDAC', loc=(x_dac, h_tot), orient='MX',
                                     unit_mode=True)

        bnd_box = inst_dac.bound_box.extend(x=0, y=0, unit_mode=True)
        self.set_size_from_bound_box(top_layer, bnd_box)
        self.array_box = bnd_box
        self.add_cell_boundary(bnd_box)

        for name in inst_dac.port_names_iter():
            if name.startswith('bias_'):
                self.reexport(inst_dac.get_port(name), show=show_pins)
        for name in inst_fe.port_names_iter():
            self.reexport(inst_fe.get_port(name), show=show_pins)

        self._sch_params = dict(
            fe_params=master_fe.sch_params,
            dac_params=master_dac.sch_params,
        )
