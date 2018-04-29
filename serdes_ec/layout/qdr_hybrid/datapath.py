# -*- coding: utf-8 -*-

"""This module defines classes needed to build the Hybrid-QDR FFE/DFE summer."""

from typing import TYPE_CHECKING, Dict, Any, Set

from bag.layout.template import TemplateBase

from .tapx import TapXColumn
from .offset import HighPassColumn
from .tap1 import Tap1Column
from .sampler import SamplerColumn

if TYPE_CHECKING:
    from bag.layout.template import TemplateDB


class RXDatapath(TemplateBase):
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
        show_pins = self.params['show_pins']
        tapx_master, tap1_master, offset_master, loff_master, samp_master = self._create_masters()

        xcur = 0
        tapx = self.add_instance(tapx_master, 'XTAPX', loc=(xcur, 0), unit_mode=True)
        xcur += tapx_master.bound_box.width_unit
        offset = self.add_instance(offset_master, 'XOFF', loc=(xcur, 0), unit_mode=True)
        xcur += offset_master.bound_box.width_unit
        tap1 = self.add_instance(tap1_master, 'XTAP1', loc=(xcur, 0), unit_mode=True)
        xcur += tap1_master.bound_box.width_unit
        offlev = self.add_instance(loff_master, 'XOFFL', loc=(xcur, 0), unit_mode=True)
        xcur += loff_master.bound_box.width_unit
        samp = self.add_instance(samp_master, 'XSAMP', loc=(xcur, 0), unit_mode=True)

        bnd_box = tapx.bound_box.merge(samp.bound_box)
        self.set_size_from_bound_box(tapx_master.top_layer, bnd_box)
        self.array_box = bnd_box

        for name in samp.port_names_iter():
            self.reexport(samp.get_port(name), show=show_pins)

    def _create_masters(self):
        show_pins_debug = True

        config = self.params['config']
        ptap_w = self.params['ptap_w']
        ntap_w = self.params['ntap_w']
        sum_params = self.params['sum_params']
        hp_params = self.params['hp_params']
        samp_params = self.params['samp_params']
        fg_dum = self.params['fg_dum']
        tr_widths = self.params['tr_widths']
        tr_spaces = self.params['tr_spaces']
        ana_options = self.params['ana_options']

        lch = config['lch']
        w_lat = sum_params['w_lat']
        th_lat = sum_params['th_lat']
        seg_sum_list = sum_params['seg_sum_list']
        seg_dfe_list = sum_params['seg_dfe_list']

        # create masters
        tapx_params = sum_params.copy()
        tapx_params['config'] = config
        tapx_params['lch'] = lch
        tapx_params['ptap_w'] = ptap_w
        tapx_params['ntap_w'] = ntap_w
        tapx_params['seg_sum_list'] = seg_sum_list[2:]
        tapx_params['seg_dfe_list'] = seg_dfe_list[1:]
        tapx_params['fg_dum'] = fg_dum
        tapx_params['tr_widths'] = tr_widths
        tapx_params['tr_spaces'] = tr_spaces
        tapx_params['options'] = ana_options
        tapx_params['show_pins'] = show_pins_debug
        tapx_master = self.new_template(params=tapx_params, temp_cls=TapXColumn)
        row_heights = tapx_master.row_heights
        sup_tids = tapx_master.sup_tids
        vss_tids = tapx_master.vss_tids
        vdd_tids = tapx_master.vdd_tids
        tapx_out_tr_info = tapx_master.out_tr_info

        tap1_params = sum_params.copy()
        tap1_params['config'] = config
        tap1_params['lch'] = lch
        tap1_params['ptap_w'] = ptap_w
        tap1_params['ntap_w'] = ntap_w
        tap1_params['w_dict'] = w_lat
        tap1_params['th_dict'] = th_lat
        tap1_params['seg_main'] = seg_sum_list[0]
        tap1_params['seg_fb'] = seg_sum_list[1]
        tap1_params['seg_lat'] = seg_dfe_list[0]
        tap1_params['fg_dum'] = fg_dum
        tap1_params['tr_widths'] = tr_widths
        tap1_params['tr_spaces'] = tr_spaces
        tap1_params['options'] = ana_options
        tap1_params['row_heights'] = row_heights
        tap1_params['sup_tids'] = sup_tids
        tap1_params['show_pins'] = show_pins_debug
        tap1_master = self.new_template(params=tap1_params, temp_cls=Tap1Column)
        tap1_in_tr_info = tap1_master.in_tr_info
        tap1_out_tr_info = tap1_master.out_tr_info
        tap1_data_tr_info = tap1_master.data_tr_info

        h_tot = row_heights[0] + row_heights[1]
        offset_params = hp_params.copy()
        offset_params['h_unit'] = h_tot
        offset_params['lch'] = lch
        offset_params['ptap_w'] = ptap_w
        offset_params['threshold'] = th_lat['tail']
        offset_params['top_layer'] = tapx_master.top_layer
        offset_params['in_tr_info'] = tapx_out_tr_info
        offset_params['out_tr_info'] = tap1_in_tr_info
        offset_params['vdd_tr_info'] = vdd_tids
        offset_params['tr_widths'] = tr_widths
        offset_params['tr_spaces'] = tr_spaces
        offset_params['ana_options'] = ana_options
        offset_params['sub_tids'] = vss_tids
        offset_params['show_pins'] = show_pins_debug
        offset_master = self.new_template(params=offset_params, temp_cls=HighPassColumn)

        loff_params = hp_params.copy()
        loff_params['h_unit'] = h_tot
        loff_params['lch'] = lch
        loff_params['ptap_w'] = ptap_w
        loff_params['threshold'] = th_lat['tail']
        loff_params['top_layer'] = tapx_master.top_layer
        loff_params['in_tr_info'] = tap1_out_tr_info
        loff_params['out_tr_info'] = tap1_in_tr_info
        loff_params['vdd_tr_info'] = vdd_tids
        loff_params['tr_widths'] = tr_widths
        loff_params['tr_spaces'] = tr_spaces
        loff_params['ana_options'] = ana_options
        loff_params['sub_tids'] = vss_tids
        loff_params['show_pins'] = show_pins_debug
        loff_master = self.new_template(params=loff_params, temp_cls=HighPassColumn)

        samp_params = samp_params.copy()
        samp_params['config'] = config
        samp_params['tr_widths'] = tr_widths
        samp_params['tr_spaces'] = tr_spaces
        samp_params['row_heights'] = row_heights
        samp_params['sup_tids'] = sup_tids
        samp_params['data_tids'] = tap1_data_tr_info
        samp_params['dlev_tids'] = tap1_out_tr_info
        samp_params['sum_row_info'] = tap1_master.sum_row_info
        samp_params['lat_row_info'] = tap1_master.lat_row_info
        samp_params['div_tr_info'] = tap1_master.div_tr_info
        samp_params['options'] = ana_options
        samp_params['show_pins'] = show_pins_debug
        samp_master = self.new_template(params=samp_params, temp_cls=SamplerColumn)

        return tapx_master, tap1_master, offset_master, loff_master, samp_master
