# -*- coding: utf-8 -*-

"""This module defines classes for Hybrid-QDR sampler/retimer."""

from typing import TYPE_CHECKING, Dict, Any, Set

from bag.layout.template import TemplateBase

from abs_templates_ec.analog_core.base import AnalogBase, AnalogBaseEnd
from abs_templates_ec.digital.core import DigitalBase

from digital_ec.layout.stdcells.latch import DFlipFlopCK2, LatchCK2

from ..laygo.misc import LaygoDummy
from ..laygo.strongarm import SenseAmpStrongArm
from ..laygo.divider import SinClkDivider

if TYPE_CHECKING:
    from bag.layout.template import TemplateDB


class SenseAmpColumn(TemplateBase):
    """A column of StrongArm sense amplifiers.

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

    # input index list
    in_idx_list = [1, 0, 1, 2, 0, 3, 2, 3]
    # input type list
    in_type_list = ['dlev', 'data', 'data', 'dlev'] * 2

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
            row_heights='row heights for one summer.',
            sup_tids='supply tracks information.',
            data_tids='data input tracks information.',
            dlev_tids='dlev input tracks information.',
            options='other AnalogBase options',
            show_pins='True to draw pin geometries.',
        )

    @classmethod
    def get_default_param_values(cls):
        # type: () -> Dict[str, Any]
        return dict(
            options=None,
            show_pins=True,
        )

    def draw_layout(self):
        config = self.params['config']
        w_dict = self.params['w_dict']
        th_dict = self.params['th_dict']
        seg_dict = self.params['seg_dict']
        tr_widths = self.params['tr_widths']
        tr_spaces = self.params['tr_spaces']
        row_heights = self.params['row_heights']
        sup_tids = self.params['sup_tids']
        data_tids = self.params['data_tids']
        dlev_tids = self.params['dlev_tids']
        options = self.params['options']
        show_pins = self.params['show_pins']

        # handle row_heights/substrate tracks
        top_layer = AnalogBase.get_mos_conn_layer(self.grid.tech_info) + 2
        bot_params = dict(config=config, w_dict=w_dict, th_dict=th_dict, seg_dict=seg_dict,
                          tr_widths=tr_widths, tr_spaces=tr_spaces, top_layer=top_layer,
                          draw_boundaries=True, end_mode=12, show_pins=False, export_probe=False,
                          sup_tids=sup_tids[0], min_height=row_heights[0], in_tids=dlev_tids)

        # create masters
        bot_master = self.new_template(params=bot_params, temp_cls=SenseAmpStrongArm)
        top_master = bot_master.new_template_with(min_height=row_heights[1], sup_tids=sup_tids[1],
                                                  in_tids=data_tids)

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

        # reexport pins
        vss_list, vdd_list = [], []
        for inst, in_idx, in_type in zip(inst_list, self.in_idx_list, self.in_type_list):
            self.reexport(inst.get_port('inp'), net_name='inp_%s<%d>' % (in_type, in_idx),
                          show=show_pins)
            self.reexport(inst.get_port('inn'), net_name='inn_%s<%d>' % (in_type, in_idx),
                          show=show_pins)
            vss_list.append(inst.get_pin('VSS'))
            vdd_list.append(inst.get_pin('VDD'))
            out_idx = (in_idx - 2) % 4
            self.reexport(inst.get_port('out'), net_name='sa_%s<%d>' % (in_type, out_idx),
                          show=show_pins)
            self.reexport(inst.get_port('clk'), net_name='en<%d>' % out_idx, show=show_pins)

        self.add_pin('VSS', vss_list, label='VSS:', show=show_pins)
        self.add_pin('VDD', vdd_list, label='VDD:', show=show_pins)


class DividerColumn(TemplateBase):
    """A column of clock dividers.

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
            sum_row_info='Summer row AnalogBase layout information dictionary.',
            lat_row_info='Latch row AnalogBase layout information dictionary.',
            seg_dict='Number of segments dictionary.',
            tr_widths='Track width dictionary.',
            tr_spaces='Track spacing dictionary.',
            div_tr_info='divider track information dictionary.',
            sup_tids='supply tracks information.',
            options='other AnalogBase options',
            show_pins='True to draw pin geometries.',
        )

    @classmethod
    def get_default_param_values(cls):
        # type: () -> Dict[str, Any]
        return dict(
            options=None,
            show_pins=True,
        )

    def draw_layout(self):
        config = self.params['config']
        sum_row_info = self.params['sum_row_info']
        lat_row_info = self.params['lat_row_info']
        seg_dict = self.params['seg_dict']
        tr_widths = self.params['tr_widths']
        tr_spaces = self.params['tr_spaces']
        div_tr_info = self.params['div_tr_info']
        sup_tids = self.params['sup_tids']
        options = self.params['options']
        show_pins = self.params['show_pins']

        # create masters
        div_params = dict(config=config, row_layout_info=lat_row_info, seg_dict=seg_dict,
                          tr_widths=tr_widths, tr_spaces=tr_spaces, tr_info=div_tr_info, fg_min=0,
                          end_mode=12, abut_mode=0, show_pins=False)

        div_master = self.new_template(params=div_params, temp_cls=SinClkDivider)
        fg_tot = div_master.fg_tot

        dums_params = dict(config=config, row_layout_info=sum_row_info, num_col=fg_tot,
                           tr_widths=tr_widths, tr_spaces=tr_spaces, sup_tids=sup_tids[0],
                           end_mode=12, abut_mode=0, show_pins=False)
        dums_master = self.new_template(params=dums_params, temp_cls=LaygoDummy)
        duml_master = dums_master.new_template_with(row_layout_info=lat_row_info,
                                                    sup_tids=sup_tids[1])

        top_layer = sum_row_info['top_layer']
        end_row_params = dict(
            lch=config['lch'],
            fg=fg_tot,
            sub_type='ptap',
            threshold=sum_row_info['row_prop_list'][0]['threshold'],
            top_layer=sum_row_info['top_layer'],
            end_mode=0b11,
            guard_ring_nf=0,
            options=options,
        )
        end_row_master = self.new_template(params=end_row_params, temp_cls=AnalogBaseEnd)
        eayt = end_row_master.array_box.top_unit

        # place instances
        vdd_list, vss_list = [], []
        bot_div, top_div = None, None
        bayt, tayt = dums_master.array_box.top_unit, duml_master.array_box.top_unit
        bot_row = self.add_instance(end_row_master, 'XROWB', loc=(0, 0), unit_mode=True)
        ycur = eayt
        for idx in range(4):
            is_even = idx % 2 == 0
            if is_even:
                m0, m1 = dums_master, duml_master
                if idx == 2:
                    m1 = div_master
            else:
                m0, m1 = duml_master, dums_master
                if idx == 1:
                    m0 = div_master
            binst = self.add_instance(m0, 'X%d' % (idx * 2), loc=(0, ycur),
                                      orient='R0', unit_mode=True)
            ycur += bayt + tayt
            tinst = self.add_instance(m1, 'X%d' % (idx * 2 + 1), loc=(0, ycur),
                                      orient='MX', unit_mode=True)

            for inst in (binst, tinst):
                vdd_list.append(inst.get_pin('VDD'))
                vss_list.append(inst.get_pin('VSS'))
            if m0 is div_master:
                bot_div = binst
            if m1 is div_master:
                top_div = tinst
        ycur += eayt
        top_row = self.add_instance(end_row_master, 'XROWT', loc=(0, ycur), orient='MX',
                                    unit_mode=True)

        # set size
        self.set_size_from_bound_box(top_layer, bot_row.bound_box.merge(top_row.bound_box))
        self.array_box = self.bound_box


class Retimer(DigitalBase):
    """A class that wraps a given standard cell with proper boundaries.

    This class is usually used just for layout debugging (i.e. DRC checking).

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
        # type: (TemplateDB, str, Dict[str, Any], Set[str], **Any) -> None
        DigitalBase.__init__(self, temp_db, lib_name, params, used_names, **kwargs)
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
            wp='pmos widths.',
            wn='nmos widths.',
            seg_dict='number of segments dictionary.',
            tr_widths='Track width dictionary.',
            tr_spaces='Track spacing dictionary.',
            show_pins='True to draw pin geometries.',
        )

    @classmethod
    def get_default_param_values(cls):
        # type: () -> Dict[str, Any]
        return dict(
            show_pins=True,
        )

    def draw_layout(self):
        seg_dict = self.params['seg_dict']
        show_pins = self.params['show_pins']

        base_params = dict(
            config=self.params['config'],
            wp=self.params['wp'],
            wn=self.params['wn'],
            tr_widths=self.params['tr_widths'],
            tr_spaces=self.params['tr_spaces'],
            show_pins=False,
        )

        base_params['seg'] = seg_dict['dff']
        ff_master = self.new_template(params=base_params, temp_cls=DFlipFlopCK2)
        base_params['seg'] = seg_dict['latch']
        lat_master = self.new_template(params=base_params, temp_cls=LatchCK2)

        ncol = max(ff_master.num_cols, lat_master.num_cols)
        self.initialize(ff_master.row_layout_info, 3, ncol)

        self.add_digital_block(ff_master, (0, 0))
        self.add_digital_block(ff_master, (0, 1))
        self.add_digital_block(lat_master, (0, 2))

        self.fill_space()
