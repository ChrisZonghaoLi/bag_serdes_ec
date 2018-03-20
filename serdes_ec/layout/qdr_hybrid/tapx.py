# -*- coding: utf-8 -*-

from typing import TYPE_CHECKING, Dict, Any, Set

"""This module defines classes needed to build the Hybrid-QDR FFE/DFE summer."""


from bag.layout.template import TemplateBase

from ..laygo.misc import LaygoDummy
from ..laygo.divider import SinClkDivider
from .amp import IntegAmp

if TYPE_CHECKING:
    from bag.layout.template import TemplateDB


class TapXSummerCell(TemplateBase):
    """A summer cell containing a single DFE/FFE tap with the corresponding latch.

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
        self._lat_row_layout_info = None

    @property
    def sch_params(self):
        # type: () -> Dict[str, Any]
        return self._sch_params

    @property
    def lat_row_layout_info(self):
        return self._lat_row_layout_info

    @classmethod
    def get_default_param_values(cls):
        # type: () -> Dict[str, Any]
        return dict(
            flip_sign=False,
            end_mode=12,
            show_pins=True,
            options=None,
        )

    @classmethod
    def get_params_info(cls):
        # type: () -> Dict[str, str]
        return dict(
            lch='channel length, in meters.',
            ptap_w='NMOS substrate width, in meters/number of fins.',
            ntap_w='PMOS substrate width, in meters/number of fins.',
            w_sum='NMOS/PMOS width dictionary for summer.',
            w_lat='NMOS/PMOS width dictionary for latch.',
            th_sum='NMOS/PMOS threshold flavor dictionary.',
            th_lat='NMOS/PMOS threshold dictoary for latch.',
            seg_sum='number of segments dictionary for summer tap.',
            seg_lat='number of segments dictionary for latch.',
            fg_dum='Number of single-sided edge dummy fingers.',
            tr_widths='Track width dictionary.',
            tr_spaces='Track spacing dictionary.',
            flip_sign='True to flip summer output sign.',
            end_mode='The AnalogBase end_mode flag.',
            show_pins='True to create pin labels.',
            options='other AnalogBase options',
        )

    def draw_layout(self):
        # get parameters
        flip_sign = self.params['flip_sign']
        end_mode = self.params['end_mode']
        show_pins = self.params['show_pins']

        # get layout parameters
        top_layer = IntegAmp.get_mos_conn_layer(self.grid.tech_info) + 2
        sum_params = dict(
            w_dict=self.params['w_sum'],
            th_dict=self.params['th_sum'],
            seg_dict=self.params['seg_sum'],
            top_layer=top_layer,
            flip_sign=flip_sign,
            show_pins=False,
            end_mode=end_mode,
        )
        lat_params = dict(
            w_dict=self.params['w_lat'],
            th_dict=self.params['th_lat'],
            seg_dict=self.params['seg_lat'],
            top_layer=top_layer,
            flip_sign=False,
            show_pins=False,
            end_mode=end_mode & 0b1100,
        )
        for key in ('lch', 'ptap_w', 'ntap_w', 'fg_dum', 'tr_widths', 'tr_spaces', 'options'):
            sum_params[key] = lat_params[key] = self.params[key]

        # get masters
        l_master = self.new_template(params=lat_params, temp_cls=IntegAmp)
        sum_params['fg_min'] = l_master.fg_tot
        s_master = self.new_template(params=sum_params, temp_cls=IntegAmp)
        if l_master.fg_tot < s_master.fg_tot:
            # update latch master
            l_master = l_master.new_template_with(fg_min=s_master.fg_tot)

        # place instances
        s_inst = self.add_instance(s_master, 'XSUM', loc=(0, 0), unit_mode=True)
        y0 = s_inst.array_box.top_unit + l_master.array_box.top_unit
        d_inst = self.add_instance(l_master, 'XLAT', loc=(0, y0), orient='MX', unit_mode=True)

        # set size
        self.array_box = s_inst.array_box.merge(d_inst.array_box)
        self.set_size_from_bound_box(top_layer, s_inst.bound_box.merge(d_inst.bound_box))

        # export pins in-place
        exp_list = [(s_inst, 'clkp', 'clkn', True), (s_inst, 'clkn', 'clkp', True),
                    (s_inst, 'casc', 'casc', False),
                    (s_inst, 'inp', 'outp_l', True), (s_inst, 'inn', 'outn_l', True),
                    (s_inst, 'biasp', 'biasn_s', False),
                    (s_inst, 'en<0>', 'en<1>', True), (s_inst, 'en<1>', 'en<2>', False),
                    (s_inst, 'setp', 'setp', False), (s_inst, 'setn', 'setn', False),
                    (s_inst, 'pulse', 'pulse', False),
                    (s_inst, 'outp', 'outp_s', False), (s_inst, 'outn', 'outn_s', False),
                    (s_inst, 'VDD', 'VDD', True), (s_inst, 'VSS', 'VSS', True),
                    (d_inst, 'clkp', 'clkp', True), (d_inst, 'clkn', 'clkn', True),
                    (d_inst, 'inp', 'inp', False), (d_inst, 'inn', 'inn', False),
                    (d_inst, 'biasp', 'biasp_l', False),
                    (d_inst, 'en<0>', 'en<0>', True), (d_inst, 'en<1>', 'en<1>', True),
                    (d_inst, 'setp', 'setp', False), (d_inst, 'setn', 'setn', False),
                    (d_inst, 'pulse', 'pulse', False),
                    (d_inst, 'outp', 'outp_l', True), (d_inst, 'outn', 'outn_l', True),
                    (d_inst, 'VDD', 'VDD', True), (d_inst, 'VSS', 'VSS', True),
                    ]

        for inst, port_name, name, vconn in exp_list:
            if inst.has_port(port_name):
                port = inst.get_port(port_name)
                label = name + ':' if vconn else name
                self.reexport(port, net_name=name, label=label, show=show_pins)

        # set schematic parameters
        self._sch_params = dict(
            sum_params=s_master.sch_params,
            lat_params=l_master.sch_params,
        )
        self._lat_row_layout_info = l_master.row_layout_info


class TapXSummerLast(TemplateBase):
    """A summer cell containing DFE tap2 gm cell with divider/pulse gen/dummies.

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
        self._fg_core = None

    @property
    def sch_params(self):
        # type: () -> Dict[str, Any]
        return self._sch_params

    @property
    def fg_core(self):
        # type: () -> int
        return self._fg_core

    @classmethod
    def get_default_param_values(cls):
        # type: () -> Dict[str, Any]
        return dict(
            div_pos_edge=True,
            flip_sign=False,
            fg_min=0,
            end_mode=12,
            show_pins=True,
            options=None,
        )

    @classmethod
    def get_params_info(cls):
        # type: () -> Dict[str, str]
        return dict(
            config='Laygo configuration dictionary for the divider.',
            row_layout_info='The AnalogBase layout information dictionary for divider.',
            lch='channel length, in meters.',
            ptap_w='NMOS substrate width, in meters/number of fins.',
            ntap_w='PMOS substrate width, in meters/number of fins.',
            w_sum='NMOS/PMOS width dictionary for summer.',
            th_sum='NMOS/PMOS threshold flavor dictionary.',
            seg_sum='number of segments dictionary for summer tap.',
            seg_div='number of segments dictionary for clock divider.',
            seg_pul='number of segments dictionary for pulse generation.',
            fg_dum='Number of single-sided edge dummy fingers.',
            tr_widths='Track width dictionary.',
            tr_spaces='Track spacing dictionary.',
            tr_info='output track information dictionary.',
            div_pos_edge='True if the divider triggers off positive edge of the clock.',
            flip_sign='True to flip summer output sign.',
            fg_min='Minimum number of core fingers.',
            end_mode='The AnalogBase end_mode flag.',
            show_pins='True to create pin labels.',
            options='other AnalogBase options',
        )

    def draw_layout(self):
        # get parameters
        row_layout_info = self.params['row_layout_info']
        seg_div = self.params['seg_div']
        seg_pul = self.params['seg_pul']
        tr_info = self.params['tr_info']
        div_pos_edge = self.params['div_pos_edge']
        flip_sign = self.params['flip_sign']
        fg_min = self.params['fg_min']
        end_mode = self.params['end_mode']
        show_pins = self.params['show_pins']

        no_dig = (seg_div is None and seg_pul is None)

        # get layout parameters
        top_layer = IntegAmp.get_mos_conn_layer(self.grid.tech_info) + 2
        sum_params = dict(
            w_dict=self.params['w_sum'],
            th_dict=self.params['th_sum'],
            seg_dict=self.params['seg_sum'],
            top_layer=top_layer,
            flip_sign=flip_sign,
            show_pins=False,
            end_mode=end_mode,
        )
        for key in ('lch', 'ptap_w', 'ntap_w', 'fg_dum', 'tr_widths', 'tr_spaces', 'options'):
            sum_params[key] = self.params[key]

        s_master = self.new_template(params=sum_params, temp_cls=IntegAmp)
        fg_core = s_master.layout_info.fg_core
        fg_min = max(fg_min, fg_core)

        dig_params = dict(
            config=self.params['config'],
            row_layout_info=row_layout_info,
            tr_widths=self.params['tr_widths'],
            tr_spaces=self.params['tr_spaces'],
            end_mode=end_mode & 0b1100,
            show_pins=False,
        )
        if no_dig:
            # no digital block, draw LaygoDummy
            if fg_core < fg_min:
                new_fg_min = s_master.fg_tot + (fg_min - fg_core)
                s_master = s_master.new_template_with(fg_min=new_fg_min)

            dig_params['num_col'] = s_master.fg_tot
            d_master = self.new_template(params=dig_params, temp_cls=LaygoDummy)
            div_sch_params = pul_sch_params = None
        else:
            # draw divider
            dig_params['seg_dict'] = seg_div
            dig_params['tr_info'] = tr_info
            dig_params['fg_min'] = fg_min
            d_master = self.new_template(params=dig_params, temp_cls=SinClkDivider)
            div_sch_params = d_master.sch_params
            pul_sch_params = None
            fg_min = max(fg_min, d_master.laygo_info.core_col)

            if fg_core < fg_min:
                new_fg_min = s_master.fg_tot + (fg_min - fg_core)
                s_master = s_master.new_template_with(fg_min=new_fg_min)

        # TODO: add pulse generator logic here

        # place instances
        s_inst = self.add_instance(s_master, 'XSUM', loc=(0, 0), unit_mode=True)
        y0 = s_inst.array_box.top_unit + d_master.array_box.top_unit
        d_inst = self.add_instance(d_master, 'XDIG', loc=(0, y0), orient='MX', unit_mode=True)

        # set size
        self.array_box = s_inst.array_box.merge(d_inst.array_box)
        self.set_size_from_bound_box(top_layer, s_inst.bound_box.merge(d_inst.bound_box))

        # get pins
        vconn_clkp = vconn_clkn = False
        # export digital pins
        if seg_div is not None:
            # perform connections for divider
            if div_pos_edge:
                clk_name = 'clkp'
                vconn_clkp = True
            else:
                clk_name = 'clkn'
                vconn_clkn = True

            # re-export divider pins
            self.reexport(d_inst.get_port('VDD'), label='VDD:', show=show_pins)
            self.reexport(d_inst.get_port('VSS'), label='VSS:', show=show_pins)
            self.reexport(d_inst.get_port('clk'), net_name=clk_name, label=clk_name + ':',
                          show=show_pins)
            self.reexport(d_inst.get_port('q'), net_name='div', show=show_pins)
            self.reexport(d_inst.get_port('qb'), net_name='divb', show=show_pins)
            self.reexport(d_inst.get_port('en'), net_name='en_div', show=show_pins)
            self.reexport(d_inst.get_port('scan_s'), net_name='scan_div', show=show_pins)
        if seg_pul is not None:
            # TODO: perform connections for pulse generation
            pass

        # export pins in-place
        exp_list = [(s_inst, 'clkp', 'clkn', vconn_clkn), (s_inst, 'clkn', 'clkp', vconn_clkp),
                    (s_inst, 'inp', 'inp', False), (s_inst, 'inn', 'inn', False),
                    (s_inst, 'biasp', 'biasn', False),
                    (s_inst, 'en<0>', 'en<1>', True), (s_inst, 'en<1>', 'en<2>', False),
                    (s_inst, 'setp', 'setp', False), (s_inst, 'setn', 'setn', False),
                    (s_inst, 'pulse', 'pulse_in', False),
                    (s_inst, 'outp', 'outp', False), (s_inst, 'outn', 'outn', False),
                    (s_inst, 'VDD', 'VDD', True), (s_inst, 'VSS', 'VSS', True),
                    ]

        for inst, port_name, name, vconn in exp_list:
            if inst.has_port(port_name):
                port = inst.get_port(port_name)
                label = name + ':' if vconn else name
                self.reexport(port, net_name=name, label=label, show=show_pins)

        # set schematic parameters
        self._sch_params = dict(
            div_pos_edge=div_pos_edge,
            sum_params=s_master.sch_params,
            div_params=div_sch_params,
            pul_params=pul_sch_params,
        )
