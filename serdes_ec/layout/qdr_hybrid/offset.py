# -*- coding: utf-8 -*-

"""This module defines classes for Hybrid-QDR offset cancellation/dlev."""

from typing import TYPE_CHECKING, Dict, Any, Set

from bag.layout.routing import TrackManager
from bag.layout.template import TemplateBase

from abs_templates_ec.analog_core.base import AnalogBaseEnd

from analog_ec.layout.passives.filter.highpass import HighPassDiff

if TYPE_CHECKING:
    from bag.layout.template import TemplateDB


class HighPassColumn(TemplateBase):
    """A column of differential high-pass RC filters..

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
            w='unit resistor width, in meters.',
            h_unit='total height, in resolution units.',
            lch='channel length, in meters.',
            ptap_w='NMOS substrate width, in meters/number of fins.',
            threshold='the substrate threshold flavor.',
            top_layer='The top layer ID',
            nser='number of resistors in series in a branch.',
            ndum='number of dummy resistors.',
            tr_widths='Track width dictionary.',
            tr_spaces='Track spacing dictionary.',
            res_type='Resistor intent',
            res_options='Configuration dictionary for ResArrayBase.',
            cap_spx='Capacitor horizontal separation, in resolution units.',
            cap_spy='Capacitor vertical space from resistor ports, in resolution units.',
            cap_margin='Capacitor space from edge, in resolution units.',
            ana_options='other AnalogBase options',
            show_pins='True to show pins.',
        )

    @classmethod
    def get_default_param_values(cls):
        # type: () -> Dict[str, Any]
        return dict(
            res_type='standard',
            res_options=None,
            cap_spx=0,
            cap_spy=0,
            cap_margin=0,
            ana_options=None,
            show_pins=True,
        )

    def draw_layout(self):
        w = self.params['w']
        h_unit = self.params['h_unit']
        lch = self.params['lch']
        ptap_w = self.params['ptap_w']
        threshold = self.params['threshold']
        top_layer = self.params['top_layer']
        nser = self.params['nser']
        ndum = self.params['ndum']
        tr_widths = self.params['tr_widths']
        tr_spaces = self.params['tr_spaces']
        res_type = self.params['res_type']
        res_options = self.params['res_options']
        cap_spx = self.params['cap_spx']
        cap_spy = self.params['cap_spy']
        cap_margin = self.params['cap_margin']
        ana_options = self.params['ana_options']
        show_pins = self.params['show_pins']

        tr_manager = TrackManager(self.grid, tr_widths, tr_spaces, half_space=True)
        sub_tr_w = tr_manager.get_width(top_layer - 1, 'sup')

        rc_params = dict(w=w, h_unit=h_unit, sub_w=ptap_w, sub_lch=lch, sub_type='ptap',
                         threshold=threshold, top_layer=top_layer, nser=nser, ndum=ndum,
                         res_type=res_type, res_options=res_options, cap_spx=cap_spx,
                         cap_spy=cap_spy, cap_margin=cap_margin, end_mode=12, sub_tr_w=sub_tr_w,
                         show_pins=False)
        master = self.new_template(params=rc_params, temp_cls=HighPassDiff)
        fg_sub = master.fg_sub

        # place instances
        if fg_sub > 0:
            end_params = dict(lch=lch, fg=fg_sub, sub_type='ptap', threshold=threshold,
                              top_layer=top_layer, end_mode=0b11, guard_ring_nf=0,
                              options=ana_options,)
            end_master = self.new_template(params=end_params, temp_cls=AnalogBaseEnd)
            end_row_box = end_master.array_box

            bot_inst = self.add_instance(end_master, 'XROWB', loc=(0, 0), unit_mode=True)
            ycur = end_row_box.top_unit
            ycur, inst_list = self._place_instances(ycur, master)
            ycur += end_row_box.top_unit
            top_inst = self.add_instance(end_master, 'XROWT', loc=(0, ycur), orient='MX',
                                         unit_mode=True)
            bound_box = bot_inst.bound_box.merge(top_inst.bound_box)
        else:
            _, inst_list = self._place_instances(0, master)
            bound_box = inst_list[0].bound_box.merge(inst_list[-1].bound_box)

        # set size
        self.set_size_from_bound_box(top_layer, bound_box)
        self.array_box = bound_box

    def _place_instances(self, ycur, master):
        inst_list = []
        for idx in range(4):
            if idx % 2 == 0:
                orient = 'R0'
            else:
                orient = 'MX'
                ycur += master.array_box.top_unit
            inst = self.add_instance(master, 'X%d' % idx, loc=(0, ycur), orient=orient,
                                     unit_mode=True)
            inst_list.append(inst)
            if idx % 2 == 0:
                ycur += master.array_box.top_unit

        return ycur, inst_list
