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
            fill_w='supply fill wire width.',
            fill_sp='supply fill spacing.',
            fill_margin='space between supply fill and others.',
            x_margin='space between fill wires and left/right edge.',
            ana_options='other AnalogBase options',
            show_pins='True to create pin labels.',
        )

    @classmethod
    def get_default_param_values(cls):
        # type: () -> Dict[str, Any]
        return dict(
            fill_w=2,
            fill_sp=1,
            fill_margin=0,
            x_margin=100,
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

        self.array_box = bnd_box = tapx.bound_box.merge(samp.bound_box)
        self.set_size_from_bound_box(tapx_master.top_layer, bnd_box)

        self._connect_signals(tapx, tap1, offset, offlev, samp)

        self._export_pins(tapx, tap1, offset, offlev, samp, show_pins)

        self._connect_supplies(tapx, tap1, offset, offlev, samp, show_pins)

        self._sch_params = dict(
            tapx_params=tapx_master.sch_params,
            off_params=offset_master.sch_params,
            tap1_params=tap1_master.sch_params,
            loff_params=loff_master.sch_params,
            samp_params=samp_master.sch_params,
        )

    def _connect_supplies(self, tapx, tap1, offset, offlev, samp, show_pins):
        fill_w = self.params['fill_w']
        fill_sp = self.params['fill_sp']
        fill_margin = self.params['fill_margin']
        x_margin = self.params['x_margin']

        vdd_hm_list = []
        vss_hm_list = []
        vdd_vm_list = []
        vss_vm_list = []
        vm_layer = self.top_layer
        hm_layer = vm_layer - 1
        for inst in (tapx, tap1, offset, offlev, samp):
            vdd_hm_list.extend(inst.port_pins_iter('VDD', layer=hm_layer))
            vss_hm_list.extend(inst.port_pins_iter('VSS', layer=hm_layer))
            vdd_vm_list.extend(inst.port_pins_iter('VDD', layer=vm_layer))
            vss_vm_list.extend(inst.port_pins_iter('VSS', layer=vm_layer))

        bnd_box = self.bound_box
        xr = bnd_box.right_unit - x_margin
        xl = x_margin
        vdd_hm = self.connect_wires(vdd_hm_list, lower=xl, upper=xr, unit_mode=True)
        vss_hm = self.connect_wires(vss_hm_list, lower=xl, upper=xr, unit_mode=True)
        sp_le = bnd_box.height_unit
        vdd, vss = self.do_power_fill(vm_layer, fill_margin, sp_le, vdd_warrs=vdd_hm,
                                      vss_warrs=vss_hm, bound_box=bnd_box, fill_width=fill_w,
                                      fill_space=fill_sp, x_margin=x_margin, unit_mode=True)
        vdd_vm_list.extend(vdd)
        vss_vm_list.extend(vss)
        self.add_pin('VDD', vdd_vm_list, show=show_pins)
        self.add_pin('VSS', vss_vm_list, show=show_pins)

    def _export_pins(self, tapx, tap1, offset, offlev, samp, show_pins):

        # reexport common ports
        reexport_set = {'clkp', 'clkn', 'en_div<3>', 'en_div<2>', 'scan_div<3>', 'scan_div<2>'}
        for name in reexport_set:
            self.reexport(tap1.get_port(name), label=name + ':', show=show_pins)
            self.reexport(tapx.get_port(name), label=name + ':', show=show_pins)
            self.reexport(samp.get_port(name), label=name + ':', show=show_pins)

        # reexport TapX ports.
        self.reexport(tapx.get_port('inp_a'), net_name='inp', show=show_pins)
        self.reexport(tapx.get_port('inn_a'), net_name='inn', show=show_pins)
        for name in tapx.port_names_iter():
            if name.startswith('casc'):
                suf = name[4:]
                self.reexport(tapx.get_port(name), net_name='bias_ffe' + suf, show=show_pins)
            elif name.startswith('bias_m'):
                suf = name[6:]
                self.reexport(tapx.get_port(name), net_name='clk_main' + suf, show=show_pins)
            elif name.startswith('bias_s'):
                suf = name[6:]
                self.reexport(tapx.get_port(name), net_name='clk_dfe' + suf, show=show_pins)
            elif name.startswith('bias_a'):
                suf = name[6:]
                self.reexport(tapx.get_port(name), net_name='clk_analog' + suf, show=show_pins)
            elif name.startswith('bias_d'):
                suf = name[6:]
                net_name = 'clk_digital' + suf
                self.reexport(tapx.get_port(name), net_name=net_name, label=net_name + ':',
                              show=show_pins)
            elif name.startswith('sgnp') or name.startswith('sgnn'):
                suf = name[4:]
                self.reexport(tapx.get_port(name), net_name=name[:4] + '_dfe' + suf, show=show_pins)

        # reexport sampler ports
        self.reexport(samp.get_port('des_clk'), show=show_pins)
        self.reexport(samp.get_port('des_clkb'), show=show_pins)

        # reexport highpass column ports, and ports with index of 4
        way_order = [3, 0, 2, 1]
        for idx, way_idx in enumerate(way_order):
            off_suf = '<%d>' % idx
            way_suf = '<%d>' % way_idx
            self.reexport(offset.get_port('biasp' + off_suf), net_name='bias_offp' + way_suf,
                          show=show_pins)
            self.reexport(offset.get_port('biasn' + off_suf), net_name='bias_offn' + way_suf,
                          show=show_pins)
            self.reexport(offlev.get_port('biasp' + off_suf), net_name='bias_dlevp' + way_suf,
                          show=show_pins)
            self.reexport(offlev.get_port('biasn' + off_suf), net_name='bias_dlevn' + way_suf,
                          show=show_pins)

            # tap1
            self.reexport(tap1.get_port('bias_f' + off_suf), net_name='clk_dfe<%d>' % (idx + 4),
                          show=show_pins)
            self.reexport(tap1.get_port('bias_m' + off_suf), net_name='clk_tap1' + off_suf,
                          show=show_pins)
            net_name = 'clk_digital' + off_suf
            self.reexport(tap1.get_port('bias_d' + off_suf), net_name=net_name,
                          label=net_name + ':', show=show_pins)
            # sampler
            self.reexport(samp.get_port('data' + off_suf), show=show_pins)
            self.reexport(samp.get_port('dlev' + off_suf), show=show_pins)

    def _connect_signals(self, tapx, tap1, offset, offlev, samp):
        # connect input/outputs that are track-aligned by construction
        io_list2 = [[], [], []]
        out_names = ['outp', 'outn']
        in_names = ['inp', 'inn']
        out_insts = [tapx, offset, tap1]
        in_insts = [offset, tap1, offlev]
        for idx in range(4):
            suf = '<%d>' % idx
            for name in out_names:
                cur_name = name + suf
                for io_list, inst in zip(io_list2, out_insts):
                    io_list.extend(inst.port_pins_iter(cur_name))
            for name in in_names:
                cur_name = name + suf
                for io_list, inst in zip(io_list2, in_insts):
                    io_list.extend(inst.port_pins_iter(cur_name))

        for io_list in io_list2:
            self.connect_wires(io_list)

        # connect data/dlev to sampler, also tap2 feedback
        dlev_order = [1, 2, 0, 3]
        for in_idx, out_idx in enumerate(dlev_order):
            in_suf = '<%d>' % in_idx
            out_suf = '<%d>' % out_idx
            inp = offlev.get_pin('outp' + in_suf)
            inn = offlev.get_pin('outn' + in_suf)
            outp_lev = samp.get_pin('inp_dlev' + out_suf)
            outn_lev = samp.get_pin('inn_dlev' + out_suf)
            self.connect_differential_wires(inp, inn, outp_lev, outn_lev, unit_mode=True)
            inp = tap1.get_pin('outp_d' + out_suf)
            inn = tap1.get_pin('outn_d' + out_suf)
            outp_lev = samp.get_pin('inp_data' + out_suf)
            outn_lev = samp.get_pin('inn_data' + out_suf)
            self.connect_differential_wires(inp, inn, outp_lev, outn_lev, unit_mode=True)
            outp_d = tapx.get_pin('inp_d' + out_suf)
            outn_d = tapx.get_pin('inn_d' + out_suf)
            self.connect_differential_wires(inp, inn, outp_d, outn_d, unit_mode=True)

    def _create_masters(self):
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
        tapx_params['show_pins'] = False
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
        tap1_params['show_pins'] = False
        tap1_master = self.new_template(params=tap1_params, temp_cls=Tap1Column)
        tap1_in_tr_info = tap1_master.in_tr_info
        tap1_out_tr_info = tap1_master.out_tr_info

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
        offset_params['show_pins'] = False
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
        loff_params['show_pins'] = False
        loff_master = self.new_template(params=loff_params, temp_cls=HighPassColumn)

        samp_params = samp_params.copy()
        samp_params['config'] = config
        samp_params['tr_widths'] = tr_widths
        samp_params['tr_spaces'] = tr_spaces
        samp_params['row_heights'] = row_heights
        samp_params['sup_tids'] = sup_tids
        samp_params['sum_row_info'] = tap1_master.sum_row_info
        samp_params['lat_row_info'] = tap1_master.lat_row_info
        samp_params['div_tr_info'] = tap1_master.div_tr_info
        samp_params['options'] = ana_options
        samp_params['show_pins'] = False
        samp_master = self.new_template(params=samp_params, temp_cls=SamplerColumn)

        return tapx_master, tap1_master, offset_master, loff_master, samp_master
