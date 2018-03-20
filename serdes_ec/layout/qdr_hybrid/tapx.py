# -*- coding: utf-8 -*-

from typing import TYPE_CHECKING, Dict, Any, Set

"""This module defines classes needed to build the Hybrid-QDR FFE/DFE summer."""


from bag.layout.template import TemplateBase

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

    @property
    def sch_params(self):
        # type: () -> Dict[str, Any]
        return self._sch_params

    @classmethod
    def get_default_param_values(cls):
        # type: () -> Dict[str, Any]
        return dict(
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
            end_mode='The AnalogBase end_mode flag.',
            show_pins='True to create pin labels.',
            options='other AnalogBase options',
        )

    def draw_layout(self):
        # get parameters
        end_mode = self.params['end_mode']
        show_pins = self.params['show_pins']

        # get layout parameters
        top_layer = IntegAmp.get_mos_conn_layer(self.grid.tech_info) + 2
        sum_params = dict(
            w_dict=self.params['w_sum'],
            th_dict=self.params['th_sum'],
            seg_dict=self.params['seg_sum'],
            top_layer=top_layer,
            show_pins=False,
            end_mode=end_mode,
        )
        lat_params = dict(
            w_dict=self.params['w_lat'],
            th_dict=self.params['th_lat'],
            seg_dict=self.params['seg_lat'],
            top_layer=top_layer,
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
        l_inst = self.add_instance(l_master, 'XLAT', loc=(0, y0), orient='MX', unit_mode=True)

        # set size
        self.array_box = s_inst.array_box.merge(l_inst.array_box)
        self.set_size_from_bound_box(top_layer, s_inst.bound_box.merge(l_inst.bound_box))

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
                    (l_inst, 'clkp', 'clkp', True), (l_inst, 'clkn', 'clkn', True),
                    (l_inst, 'inp', 'inp', False), (l_inst, 'inn', 'inn', False),
                    (l_inst, 'biasp', 'biasp_l', False),
                    (l_inst, 'en<0>', 'en<0>', False), (l_inst, 'en<1>', 'en<1>', True),
                    (l_inst, 'setp', 'setp', False), (l_inst, 'setn', 'setn', False),
                    (l_inst, 'pulse', 'pulse', False),
                    (l_inst, 'outp', 'outp_l', True), (l_inst, 'outn', 'outn_l', True),
                    (l_inst, 'VDD', 'VDD', True), (l_inst, 'VSS', 'VSS', True),
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
