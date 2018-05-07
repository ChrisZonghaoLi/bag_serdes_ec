# -*- coding: utf-8 -*-

"""This module defines classes needed to build the Hybrid-QDR FFE/DFE summer."""

from typing import TYPE_CHECKING, Dict, Any, Set

from bag.layout.util import BBox
from bag.layout.template import TemplateBase

from analog_ec.layout.dac.rladder.top import RDACArray
from analog_ec.layout.passives.filter.highpass import HighPassArrayClk

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
            dp_params='datapath parameters.',
            hp_params='high-pass filter array parameters.',
            tr_widths='Track width dictionary.',
            tr_spaces='Track spacing dictionary.',
            fill_config='Fill configuration dictionary.',
            show_pins='True to create pin labels.',
        )

    @classmethod
    def get_default_param_values(cls):
        # type: () -> Dict[str, Any]
        return dict(
            show_pins=True,
        )

    def draw_layout(self):
        ml = 30000
        fill_config = self.params['fill_config']
        show_pins = self.params['show_pins']

        dp_master, hpx_master, hp1_master = self._make_masters()

        # place masters
        hp_h = hpx_master.bound_box.height_unit
        hpx_w = hpx_master.bound_box.width_unit
        hp1_w = hp1_master.bound_box.width_unit

        top_layer = dp_master.top_layer
        bnd_box = dp_master.bound_box
        blk_w, blk_h = self.grid.get_fill_size(top_layer, fill_config, unit_mode=True)
        dp_h = bnd_box.height_unit
        tot_w = -(-(bnd_box.width_unit + ml) // blk_w) * blk_w
        tot_h = -(-(dp_h + 2 * hp_h) // blk_h) * blk_h
        x0 = tot_w - bnd_box.width_unit
        y0 = (tot_h - dp_h) // (2 * blk_h) * blk_h
        dp_inst = self.add_instance(dp_master, 'XDP', loc=(x0, y0), unit_mode=True)
        x_hpx = x0 + dp_master.x_tapx[1] - hpx_w
        x_hp1 = max(x_hpx + hpx_w, x0 + dp_master.x_tap1[1] - hp1_w)
        hpx_inst = self.add_instance(hpx_master, 'XHPXB', loc=(x_hpx, 0), unit_mode=True)
        hp1_inst = self.add_instance(hp1_master, 'XHP1B', loc=(x_hp1, 0), unit_mode=True)

        bnd_box = BBox(0, 0, tot_w, tot_h, self.grid.resolution, unit_mode=True)
        self.set_size_from_bound_box(dp_master.top_layer, bnd_box)
        self.array_box = bnd_box
        self.add_cell_boundary(bnd_box)

        for name in dp_inst.port_names_iter():
            self.reexport(dp_inst.get_port(name), show=show_pins)

        self._sch_params = dp_master.sch_params.copy()

    def _make_masters(self):
        dp_params = self.params['dp_params']
        hp_params = self.params['hp_params']
        tr_widths = self.params['tr_widths']
        tr_spaces = self.params['tr_spaces']

        dp_params = dp_params.copy()
        dp_params['tr_widths'] = tr_widths
        dp_params['tr_spaces'] = tr_spaces
        dp_params['show_pins'] = False
        dp_master = self.new_template(params=dp_params, temp_cls=RXDatapath)

        hp_params = hp_params.copy()
        hp_params['narr'] = dp_master.num_hp_tapx
        hp_params['tr_widths'] = tr_widths
        hp_params['tr_spaces'] = tr_spaces
        hp_params['show_pins'] = False
        hpx_master = self.new_template(params=hp_params, temp_cls=HighPassArrayClk)

        hp_params['narr'] = dp_master.num_hp_tap1
        hp1_master = self.new_template(params=hp_params, temp_cls=HighPassArrayClk)

        return dp_master, hpx_master, hp1_master


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
