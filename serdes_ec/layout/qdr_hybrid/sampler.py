# -*- coding: utf-8 -*-

"""This module defines classes for Hybrid-QDR sampler/retimer."""

from typing import TYPE_CHECKING, Dict, Any, Set

from bag.layout.template import TemplateBase

from abs_templates_ec.analog_core.base import AnalogBase, AnalogBaseEnd

from ..laygo.strongarm import SenseAmpStrongArm

from .util import get_row_params

if TYPE_CHECKING:
    from bag.layout.template import TemplateDB


class SenseAmpColumn(TemplateBase):
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
            config='laygo configuration dictionary.',
            w_dict='width dictionary.',
            th_dict='threshold dictionary.',
            seg_dict='number of segments dictionary.',
            tr_widths='Track width dictionary.',
            tr_spaces='Track spacing dictionary.',
            options='other AnalogBase options',
            row_heights='row heights for one summer.',
            vss_tids='VSS tracks information.',
            vdd_tids='VDD tracks information.',
            show_pins='True to draw pin geometries.',
        )

    @classmethod
    def get_default_param_values(cls):
        # type: () -> Dict[str, Any]
        return dict(
            options=None,
            row_heights=None,
            vss_tids=None,
            vdd_tids=None,
            show_pins=True,
        )

    def draw_layout(self):
        config = self.params['config']
        w_dict = self.params['w_dict']
        th_dict = self.params['th_dict']
        seg_dict = self.params['seg_dict']
        tr_widths = self.params['tr_widths']
        tr_spaces = self.params['tr_spaces']
        options = self.params['options']
        row_heights = self.params['row_heights']
        vss_tids = self.params['vss_tids']
        vdd_tids = self.params['vdd_tids']
        show_pins = self.params['show_pins']

        # handle row_heights/substrate tracks
        bot_params, top_params = get_row_params(self.grid, row_heights, vss_tids, vdd_tids)

        top_layer = AnalogBase.get_mos_conn_layer(self.grid.tech_info) + 2
        sa_params = dict(config=config, w_dict=w_dict, th_dict=th_dict, seg_dict=seg_dict,
                         tr_widths=tr_widths, tr_spaces=tr_spaces, top_layer=top_layer,
                         draw_boundaries=True, end_mode=12, show_pins=False, export_probe=False)
        bot_params.update(sa_params)

        # create masters
        bot_master = self.new_template(params=bot_params, temp_cls=SenseAmpStrongArm)
        top_master = bot_master.new_template_with(**top_params)

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
        self.set_size_from_bound_box(top_layer, bot_row.bound_box.merge(top_row.bound_box))
        self.array_box = self.bound_box
