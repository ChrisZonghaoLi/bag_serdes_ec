# -*- coding: utf-8 -*-

"""This module defines classes needed to build the Hybrid-QDR FFE/DFE summer."""

from typing import TYPE_CHECKING, Dict, Any, Set, Tuple, List, Union

from bag.layout.util import BBox
from bag.layout.template import TemplateBase

from abs_templates_ec.analog_mos.mos import DummyFillActive

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
        self._x_tapx = None
        self._x_tap1 = None
        self._num_dfe = None
        self._num_ffe = None
        self._blockage_intvs = None
        self._sup_y_list = None
        self._buf_locs = None
        self._retime_ncol = None
        self._en_div_tidx = None

    @property
    def sch_params(self):
        # type: () -> Dict[str, Any]
        return self._sch_params

    @property
    def x_tapx(self):
        # type: () -> Tuple[int, int]
        return self._x_tapx

    @property
    def x_tap1(self):
        # type: () -> Tuple[int, int]
        return self._x_tap1

    @property
    def num_dfe(self):
        # type: () -> int
        return self._num_dfe

    @property
    def num_ffe(self):
        # type: () -> int
        return self._num_ffe

    @property
    def num_hp_tapx(self):
        # type: () -> int
        return self._num_dfe * 2 + 4

    @property
    def num_hp_tap1(self):
        # type: () -> int
        return 6

    @property
    def blockage_intvs(self):
        # type: () -> List[Tuple[int, int]]
        return self._blockage_intvs

    @property
    def sup_y_list(self):
        # type: () -> List[int]
        return self._sup_y_list

    @property
    def buf_locs(self):
        # type: () -> Tuple[Tuple[int, int], Tuple[int, int]]
        return self._buf_locs

    @property
    def retime_ncol(self):
        # type: () -> int
        return self._retime_ncol

    @property
    def en_div_tidx(self):
        # type: () -> Union[float, int]
        return self._en_div_tidx

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
            scan_buf_params='scan buffer parameters.',
            fg_dum='Number of single-sided edge dummy fingers.',
            tr_widths='Track width dictionary.',
            tr_spaces='Track spacing dictionary.',
            tr_widths_dig='Track width dictionary for digital.',
            tr_spaces_dig='Track spacing dictionary for digital.',
            fill_w='supply fill wire width.',
            fill_sp='supply fill spacing.',
            fill_margin='space between supply fill and others.',
            x_margin='space between fill wires and left/right edge.',
            ana_options='other AnalogBase options',
            show_pins='True to create pin labels.',
            export_probe='True to export probe ports.',
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
            export_probe=False,
        )

    def draw_layout(self):
        show_pins = self.params['show_pins']
        export_probe = self.params['export_probe']

        tmp = self._create_masters(export_probe)
        master_tapx, master_tap1, master_offset, master_loff, master_samp = tmp

        # place instances
        xcur = 0
        self._blockage_intvs = []
        tapx_box = master_tapx.bound_box
        top_layer = master_tapx.top_layer
        tapx = self.add_instance(master_tapx, 'XTAPX', loc=(xcur, 0), unit_mode=True)
        xr = xcur + tapx_box.width_unit
        self._x_tapx = (xcur, xr)
        for xl, xu in master_tapx.blockage_intvs:
            self._blockage_intvs.append((xl + xcur, xu + xcur))
        xcur = xr
        offset = self.add_instance(master_offset, 'XOFF', loc=(xcur, 0), unit_mode=True)
        xcur += master_offset.bound_box.width_unit
        tap1 = self.add_instance(master_tap1, 'XTAP1', loc=(xcur, 0), unit_mode=True)
        xr = xcur + master_tap1.bound_box.width_unit
        self._x_tap1 = (xcur, xr)
        for xl, xu in master_tap1.blockage_intvs:
            self._blockage_intvs.append((xl + xcur, xu + xcur))

        xcur = xr
        offlev = self.add_instance(master_loff, 'XOFFL', loc=(xcur, 0), unit_mode=True)
        xcur += master_loff.bound_box.width_unit
        samp = self.add_instance(master_samp, 'XSAMP', loc=(xcur, 0), unit_mode=True)
        sbuf_locs = master_samp.buf_locs
        xbuf = sbuf_locs[0][0] + xcur
        self._buf_locs = ((xbuf, sbuf_locs[0][1]), (xbuf, sbuf_locs[1][1]))

        self.array_box = bnd_box = samp.bound_box.extend(x=0, unit_mode=True)
        self.set_size_from_bound_box(top_layer, bnd_box)
        self.add_cell_boundary(bnd_box)

        # reverse vertical track for en_div in the future
        ym_tidx = self.grid.find_next_track(top_layer, xbuf, half_track=True, mode=1,
                                            unit_mode=True)
        self._en_div_tidx = ym_tidx
        self.reserve_tracks(top_layer, ym_tidx)

        self._connect_signals(tapx, tap1, offset, offlev, samp, show_pins, export_probe)

        self._export_pins(tapx, tap1, offset, offlev, samp, show_pins)

        self._connect_supplies(tapx, tap1, offset, offlev, samp, show_pins)

        self._do_dummy_fill(top_layer, tapx, tap1, offset, offlev, samp)

        self._sch_params = dict(
            tapx_params=master_tapx.sch_params,
            off_params=master_offset.sch_params,
            tap1_params=master_tap1.sch_params,
            loff_params=master_loff.sch_params,
            samp_params=master_samp.sch_params,
            export_probe=export_probe,
        )
        self._num_ffe = master_tapx.num_ffe
        self._num_dfe = master_tapx.num_dfe
        self._sup_y_list = master_tapx.sup_y_list

    def _do_dummy_fill(self, top_layer, tapx, tap1, offset, offlev, samp):
        res = self.grid.resolution

        tapx_box = tapx.fill_box
        off_box = offset.fill_box
        tap1_box = tap1.fill_box
        lev_box = offlev.fill_box
        samp_box = samp.fill_box
        yb = tapx_box.bottom_unit
        yt = tapx_box.top_unit
        box1 = BBox(tapx_box.right_unit, yb, off_box.left_unit, yt, res, unit_mode=True)
        box2 = BBox(tap1_box.right_unit, yb, lev_box.left_unit, yt, res, unit_mode=True)

        params = dict(
            mos_type='nch',
            threshold='standard',
            width=box1.width_unit,
            height=box1.height_unit,
        )
        dum1 = self.new_template(params=params, temp_cls=DummyFillActive)
        params['width'] = box2.width_unit
        params['height'] = box2.height_unit
        dum2 = self.new_template(params=params, temp_cls=DummyFillActive)
        self.add_instance(dum1, 'XDUM1', loc=(box1.left_unit, box1.bottom_unit), unit_mode=True)
        self.add_instance(dum2, 'XDUM2', loc=(box2.left_unit, box2.bottom_unit), unit_mode=True)

        hm_layer = top_layer - 1
        for layer in range(1, hm_layer):
            self.do_max_space_fill(layer, bound_box=box1)
            self.do_max_space_fill(layer, bound_box=box2)

        self.fill_box = tapx_box.merge(samp_box)
        self.do_max_space_fill(hm_layer, self.fill_box, fill_pitch=2)

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
        xl = tapx.location_unit[0] + x_margin
        vdd_hm = self.connect_wires(vdd_hm_list, lower=xl, unit_mode=True)
        vss_hm = self.connect_wires(vss_hm_list, lower=xl, unit_mode=True)
        sp_le = bnd_box.height_unit
        vdd, vss = self.do_power_fill(vm_layer, fill_margin, sp_le, vdd_warrs=vdd_hm,
                                      vss_warrs=vss_hm, bound_box=bnd_box, fill_width=fill_w,
                                      fill_space=fill_sp, x_margin=x_margin, unit_mode=True)
        self.connect_to_track_wires(samp.get_all_port_pins('VDD_o'), vdd)
        self.connect_to_track_wires(samp.get_all_port_pins('VSS_o'), vss)
        vdd_vm_list.extend(vdd)
        vss_vm_list.extend(vss)
        self.add_pin('VDD', vdd_hm, show=show_pins)
        self.add_pin('VSS', vss_hm, show=show_pins)
        self.add_pin('VDD', vdd_vm_list, show=show_pins)
        self.add_pin('VSS', vss_vm_list, show=show_pins)
        self.add_pin('VDD_re', samp.get_all_port_pins('VDD_re'), label='VDD', show=False)
        self.add_pin('VSS_re', samp.get_all_port_pins('VSS_re'), label='VSS', show=False)

    def _export_pins(self, tapx, tap1, offset, offlev, samp, show_pins):

        # reexport common ports
        reexport_set = {'clkp', 'clkn', 'en_div', 'scan_div<3>', 'scan_div<2>'}
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
                self.reexport(tapx.get_port(name), net_name='clk_digital_tapx' + suf,
                              show=show_pins)
            elif name.startswith('sgnp') or name.startswith('sgnn'):
                suf = name[4:]
                self.reexport(tapx.get_port(name), net_name=name[:4] + '_dfe' + suf, show=show_pins)

        # rexport tap1 ports
        self.reexport(tap1.get_port('VDD_ext'), show=False)
        # reexport sampler ports
        self.reexport(samp.get_port('des_clk'), show=show_pins)
        self.reexport(samp.get_port('des_clkb'), show=show_pins)

        # reexport highpass column ports, and ports with index of 4
        way_order = [3, 0, 2, 1]
        self.reexport(offset.get_port('VDD_vm'), net_name='VDD', label='VDD', show=show_pins)
        self.reexport(offlev.get_port('VDD_vm'), net_name='VDD', label='VDD', show=show_pins)
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
            self.reexport(tap1.get_port('bias_d' + off_suf), net_name='clk_digital_tap1' + off_suf,
                          show=show_pins)
            # sampler
            self.reexport(samp.get_port('data' + off_suf), show=show_pins)
            self.reexport(samp.get_port('dlev' + off_suf), show=show_pins)

    def _connect_signals(self, tapx, tap1, offset, offlev, samp, show_pins, export_probe):
        # connect input/outputs that are track-aligned by construction
        io_list2 = [[], [], []]
        out_names = ['outp', 'outn']
        in_names = ['inp', 'inn']
        out_insts = [tapx, offset, tap1]
        out_pnames = ['_tapx', None, '_tap1']
        in_insts = [offset, tap1, offlev]
        in_pnames = [None, '_tap1', None]
        for idx in range(4):
            suf = '<%d>' % idx
            for name in out_names:
                cur_name = name + suf
                for io_list, inst, pname in zip(io_list2, out_insts, out_pnames):
                    pin = inst.get_pin(cur_name)
                    io_list.append(pin)
                    if pname is not None and export_probe:
                        self.add_pin(name + pname + suf, pin, show=show_pins)
            for name in in_names:
                cur_name = name + suf
                for io_list, inst, pname in zip(io_list2, in_insts, in_pnames):
                    pin = inst.get_pin(cur_name)
                    io_list.append(pin)
                    if pname is not None and export_probe:
                        self.add_pin(name + pname + suf, pin, show=show_pins)
            if export_probe:
                # export enable signal probes
                en_name = 'en' + suf
                self.add_pin('en_tapx' + suf, tapx.get_pin(en_name), show=show_pins)
                self.add_pin('en_tap1' + suf, tap1.get_pin(en_name), show=show_pins)
                self.add_pin('en_samp' + suf, samp.get_pin(en_name), show=show_pins)
                sa_l = 'sa_dlev' + suf
                self.add_pin(sa_l, samp.get_pin(sa_l), show=show_pins)
                sa_d = 'sa_data' + suf
                self.add_pin(sa_d, samp.get_pin(sa_d), show=show_pins)

        # add signal chain probes
        if export_probe:
            for idx in tapx.master.probe_range_iter(analog=True):
                suf = '<%d>' % idx
                self.reexport(tapx.get_port('outp_a' + suf), show=show_pins)
                self.reexport(tapx.get_port('outn_a' + suf), show=show_pins)
            for idx in tapx.master.probe_range_iter(analog=False):
                suf = '<%d>' % idx
                suf2 = '<%d>' % (idx - 8)
                self.add_pin('outp_data' + suf2, tapx.get_pin('outp_d' + suf), show=show_pins)
                self.add_pin('outn_data' + suf2, tapx.get_pin('outn_d' + suf), show=show_pins)

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
            outp_data = samp.get_pin('inp_data' + out_suf)
            outn_data = samp.get_pin('inn_data' + out_suf)
            self.connect_differential_wires(inp, inn, outp_data, outn_data, unit_mode=True)
            outp_d = tapx.get_pin('inp_d' + out_suf)
            outn_d = tapx.get_pin('inn_d' + out_suf)
            self.connect_differential_wires(inp, inn, outp_d, outn_d, unit_mode=True)
            if export_probe:
                self.add_pin('outp_data' + out_suf, outp_data, show=show_pins)
                self.add_pin('outn_data' + out_suf, outn_data, show=show_pins)
                self.add_pin('outp_dlev' + out_suf, outp_lev, show=show_pins)
                self.add_pin('outn_dlev' + out_suf, outn_lev, show=show_pins)

    def _create_masters(self, export_probe):
        config = self.params['config']
        ptap_w = self.params['ptap_w']
        ntap_w = self.params['ntap_w']
        sum_params = self.params['sum_params']
        hp_params = self.params['hp_params']
        samp_params = self.params['samp_params']
        scan_buf_params = self.params['scan_buf_params']
        fg_dum = self.params['fg_dum']
        tr_widths = self.params['tr_widths']
        tr_spaces = self.params['tr_spaces']
        tr_widths_dig = self.params['tr_widths_dig']
        tr_spaces_dig = self.params['tr_spaces_dig']
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
        tapx_params['export_probe'] = export_probe
        master_tapx = self.new_template(params=tapx_params, temp_cls=TapXColumn)
        row_heights = master_tapx.row_heights
        sup_tids = master_tapx.sup_tids
        vss_tids = master_tapx.vss_tids
        vdd_tids = master_tapx.vdd_tids
        tapx_out_tr_info = master_tapx.out_tr_info

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
        tap1_params['export_probe'] = export_probe
        master_tap1 = self.new_template(params=tap1_params, temp_cls=Tap1Column)
        tap1_in_tr_info = master_tap1.in_tr_info
        tap1_out_tr_info = master_tap1.out_tr_info

        h_tot = row_heights[0] + row_heights[1]
        offset_params = hp_params.copy()
        offset_params['h_unit'] = h_tot
        offset_params['lch'] = lch
        offset_params['ptap_w'] = ptap_w
        offset_params['threshold'] = th_lat['tail']
        offset_params['top_layer'] = master_tapx.top_layer
        offset_params['in_tr_info'] = tapx_out_tr_info
        offset_params['out_tr_info'] = tap1_in_tr_info
        offset_params['vdd_tr_info'] = vdd_tids
        offset_params['tr_widths'] = tr_widths
        offset_params['tr_spaces'] = tr_spaces
        offset_params['ana_options'] = ana_options
        offset_params['sub_tids'] = vss_tids
        offset_params['show_pins'] = False
        master_offset = self.new_template(params=offset_params, temp_cls=HighPassColumn)

        loff_params = hp_params.copy()
        loff_params['h_unit'] = h_tot
        loff_params['lch'] = lch
        loff_params['ptap_w'] = ptap_w
        loff_params['threshold'] = th_lat['tail']
        loff_params['top_layer'] = master_tapx.top_layer
        loff_params['in_tr_info'] = tap1_out_tr_info
        loff_params['out_tr_info'] = tap1_in_tr_info
        loff_params['vdd_tr_info'] = vdd_tids
        loff_params['tr_widths'] = tr_widths
        loff_params['tr_spaces'] = tr_spaces
        loff_params['ana_options'] = ana_options
        loff_params['sub_tids'] = vss_tids
        loff_params['show_pins'] = False
        master_loff = self.new_template(params=loff_params, temp_cls=HighPassColumn)

        samp_params = samp_params.copy()
        samp_params['config'] = config
        samp_params['buf_params'] = scan_buf_params
        samp_params['tr_widths'] = tr_widths
        samp_params['tr_spaces'] = tr_spaces
        samp_params['tr_widths_dig'] = tr_widths_dig
        samp_params['tr_spaces_dig'] = tr_spaces_dig
        samp_params['row_heights'] = row_heights
        samp_params['sup_tids'] = sup_tids
        samp_params['sum_row_info'] = master_tap1.sum_row_info
        samp_params['lat_row_info'] = master_tap1.lat_row_info
        samp_params['div_tr_info'] = master_tap1.div_tr_info
        samp_params['options'] = ana_options
        samp_params['show_pins'] = False
        samp_params['export_probe'] = export_probe
        master_samp = self.new_template(params=samp_params, temp_cls=SamplerColumn)
        self._retime_ncol = master_samp.retime_ncol

        return master_tapx, master_tap1, master_offset, master_loff, master_samp
