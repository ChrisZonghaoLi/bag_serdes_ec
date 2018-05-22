# -*- coding: utf-8 -*-


from typing import TYPE_CHECKING, Dict, Set, Any, List, Union

from itertools import chain, repeat

from bag.layout.routing.base import TrackID, TrackManager
from bag.layout.util import BBox
from bag.layout.template import TemplateBase, BlackBoxTemplate

from abs_templates_ec.resistor.core import ResArrayBase
from abs_templates_ec.analog_mos.mos import DummyFillActive

from analog_ec.layout.passives.capacitor.momcap import MOMCapCore
from analog_ec.layout.passives.substrate import SubstrateWrapper

if TYPE_CHECKING:
    from bag.layout.template import TemplateDB


class PassiveCTLECore(ResArrayBase):
    """Passive CTLE Core.

    Parameters
    ----------
    temp_db : :class:`bag.layout.template.TemplateDB`
        the template database.
    lib_name : str
        the layout library name.
    params : Dict[str, Any]
        the parameter values.
    used_names : Set[str]
        a set of already used cell names.
    **kwargs :
        dictionary of optional parameters.  See documentation of
        :class:`bag.layout.template.TemplateBase` for details.
    """

    def __init__(self, temp_db, lib_name, params, used_names, **kwargs):
        # type: (TemplateDB, str, Dict[str, Any], Set[str], **kwargs) -> None
        ResArrayBase.__init__(self, temp_db, lib_name, params, used_names, **kwargs)
        self._sch_params = None

    @property
    def sch_params(self):
        # type: () -> Dict[str, Any]
        return self._sch_params

    @classmethod
    def get_params_info(cls):
        # type: () -> Dict[str, str]
        return dict(
            l='unit resistor length, in meters.',
            w='unit resistor width, in meters.',
            cap_height='capacitor height, in resolution units.',
            num_r1='number of r1 segments per column.',
            num_r2='number of r2 segments per column.',
            num_col='number of resistor columns.',
            num_dumc='number of dummy columns.',
            num_dumr='number of dummy rows.',
            sub_type='the substrate type.',
            threshold='the substrate threshold flavor.',
            tr_widths='Track width dictionary.',
            tr_spaces='Track spacing dictionary.',
            port_tr_w='MOM cap port track width, in number of tracks.',
            res_type='the resistor type.',
            res_options='Configuration dictionary for ResArrayBase.',
            cap_spx='Space between capacitor and left/right edge, in resolution units.',
            cap_spy='Space between capacitor and cm-port/top/bottom edge, in resolution units.',
            half_blk_x='True to allow for half horizontal blocks.',
            show_pins='True to draw pin layous.',
        )

    @classmethod
    def get_default_param_values(cls):
        # type: () -> Dict[str, Any]
        return dict(
            port_tr_w=1,
            res_type='standard',
            res_options=None,
            cap_spx=0,
            cap_spy=0,
            half_blk_x=True,
            show_pins=True,
        )

    def draw_layout(self):
        # type: () -> None

        l = self.params['l']
        w = self.params['w']
        cap_height = self.params['cap_height']
        num_r1 = self.params['num_r1']
        num_r2 = self.params['num_r2']
        num_col = self.params['num_col']
        num_dumc = self.params['num_dumc']
        num_dumr = self.params['num_dumr']
        sub_type = self.params['sub_type']
        threshold = self.params['threshold']
        tr_widths = self.params['tr_widths']
        tr_spaces = self.params['tr_spaces']
        port_tr_w = self.params['port_tr_w']
        res_type = self.params['res_type']
        res_options = self.params['res_options']
        cap_spx = self.params['cap_spx']
        cap_spy = self.params['cap_spy']
        half_blk_x = self.params['half_blk_x']
        show_pins = self.params['show_pins']

        res = self.grid.resolution
        lay_unit = self.grid.layout_unit

        if num_col % 2 != 0:
            raise ValueError('num_col must be even.')
        if num_dumc <= 0 or num_dumr <= 0:
            raise ValueError('num_dumr and num_dumc must be > 0.')
        if res_options is None:
            my_options = dict(well_end_mode=2)
        else:
            my_options = res_options.copy()
            my_options['well_end_mode'] = 2

        # draw array
        vm_layer = self.bot_layer_id + 1
        hm_layer = vm_layer + 1
        top_layer = hm_layer + 1
        nx = 2 * num_col + 2 * num_dumc
        ny = 2 * (max(num_r1, num_r2) + num_dumr)
        ndum_tot = nx * ny - 2 * num_col * (num_r1 + num_r2)
        self.draw_array(l, w, sub_type, threshold, nx=nx, ny=ny, top_layer=top_layer,
                        res_type=res_type, grid_type=None, options=my_options,
                        connect_up=True, half_blk_x=half_blk_x, half_blk_y=False)

        # connect wires
        tr_manager = TrackManager(self.grid, tr_widths, tr_spaces, half_space=True)

        vm_w_io = tr_manager.get_width(vm_layer, 'ctle')
        sup_name = 'VDD' if sub_type == 'ntap' else 'VSS'
        supt, supb = self._connect_dummies(num_col, num_r1, num_r2, num_dumr, num_dumc)
        tmp = self._connect_snake(num_col, num_r1, num_r2, num_dumr, num_dumc, vm_w_io, show_pins)
        inp, inn, outp, outn, outcm, outp_yt, outn_yb = tmp

        # calculate capacitor bounding box
        bnd_box = self.bound_box
        yc = bnd_box.yc_unit
        hm_w_io = tr_manager.get_width(hm_layer, 'ctle')
        cm_tr = self.grid.coord_to_track(hm_layer, yc, unit_mode=True)
        cm_yb, cm_yt = self.grid.get_wire_bounds(hm_layer, cm_tr, width=hm_w_io, unit_mode=True)
        # make sure metal resistor has non-zero length
        cap_yb = max(outp_yt + 2, cm_yt + cap_spy)
        cap_yt = min(cap_yb + cap_height, bnd_box.top_unit - cap_spy)
        cap_xl = cap_spx
        cap_xr = bnd_box.right_unit - cap_spx

        # construct port parity
        top_parity = {hm_layer: (0, 1), top_layer: (1, 0)}
        bot_parity = {hm_layer: (1, 0), top_layer: (1, 0)}
        cap_top = self.add_mom_cap(BBox(cap_xl, cap_yb, cap_xr, cap_yt, res, unit_mode=True),
                                   hm_layer, 2, port_parity=top_parity, port_widths=port_tr_w)
        # make sure metal resistor has non-zero length
        cap_yt = min(outn_yb - 2, cm_yb - cap_spy)
        cap_yb = max(cap_yt - cap_height, cap_spy)
        cap_bot = self.add_mom_cap(BBox(cap_xl, cap_yb, cap_xr, cap_yt, res, unit_mode=True),
                                   hm_layer, 2, port_parity=bot_parity, port_widths=port_tr_w)

        outp_hm_tid = cap_top[hm_layer][1][0].track_id
        outn_hm_tid = cap_bot[hm_layer][1][0].track_id
        self.connect_to_tracks(inp, cap_top[hm_layer][0][0].track_id)
        self.connect_to_tracks(outp, outp_hm_tid)
        self.connect_to_tracks(inn, cap_bot[hm_layer][0][0].track_id)
        self.connect_to_tracks(outn, outn_hm_tid)

        # add metal resistors
        inp_vm_tid = inp.track_id
        outp_vm_tid = outp.track_id
        res_w = self.grid.get_track_width(vm_layer, outp_vm_tid.width, unit_mode=True)
        rmp_yt = min(outp_yt + res_w, outp_hm_tid.get_bounds(self.grid, unit_mode=True)[0])
        rmn_yb = max(outn_yb - res_w, outn_hm_tid.get_bounds(self.grid, unit_mode=True)[1])
        res_info = (vm_layer, res_w * res * lay_unit, (rmp_yt - outp_yt) * res * lay_unit)
        self.add_res_metal_warr(vm_layer, outp_vm_tid.base_index, outp_yt, rmp_yt,
                                width=outp_vm_tid.width, unit_mode=True)
        self.add_res_metal_warr(vm_layer, inp_vm_tid.base_index, outp_yt, rmp_yt,
                                width=inp_vm_tid.width, unit_mode=True)
        self.add_res_metal_warr(vm_layer, outp_vm_tid.base_index, rmn_yb, outn_yb,
                                width=outp_vm_tid.width, unit_mode=True)
        self.add_res_metal_warr(vm_layer, inp_vm_tid.base_index, rmn_yb, outn_yb,
                                width=inp_vm_tid.width, unit_mode=True)

        self.add_pin('inp', cap_top[top_layer][0], show=show_pins)
        self.add_pin('outp', cap_top[top_layer][1], show=show_pins)
        self.add_pin('inn', cap_bot[top_layer][0], show=show_pins)
        self.add_pin('outn', cap_bot[top_layer][1], show=show_pins)
        self.add_pin(sup_name, supb, label=sup_name, show=show_pins)
        self.add_pin(sup_name, supt, label=sup_name, show=show_pins)

        self._sch_params = dict(
            l=l,
            w=w,
            intent=res_type,
            nr1=num_r1 * num_col,
            nr2=num_r2 * num_col,
            ndum=ndum_tot,
            res_in_info=res_info,
            res_out_info=res_info,
            sub_name='VSS',
        )

    def _connect_snake(self, ncol, nr1, nr2, ndumr, ndumc, io_width, show_pins):
        nrow_half = max(nr1, nr2) + ndumr
        for cidx in range(ncol):
            c1 = ndumc + cidx
            c2 = c1 + ncol
            # connect in same column
            for idx in range(1, nr1):
                self._connect_mirror(nrow_half, (idx - 1, c1), (idx, c1), 1, 0)
            for idx in range(1, nr2):
                self._connect_mirror(nrow_half, (idx - 1, c2), (idx, c2), 1, 0)
            # connect adjacent columns
            if cidx != ncol - 1:
                if cidx % 2 == 0:
                    self._connect_mirror(nrow_half, (nr1 - 1, c1), (nr1 - 1, c1 + 1), 1, 1)
                    self._connect_mirror(nrow_half, (nr2 - 1, c2), (nr2 - 1, c2 + 1), 1, 1)
                else:
                    self._connect_mirror(nrow_half, (0, c1), (0, c1 + 1), 0, 0)
                    self._connect_mirror(nrow_half, (0, c2), (0, c2 + 1), 0, 0)

        # connect outp/outn
        outpl = self.get_res_ports(nrow_half, ndumc + ncol - 1)[0]
        outpr = self.get_res_ports(nrow_half, ndumc + ncol)[0]
        outp = self.connect_wires([outpl, outpr])[0]
        outnl = self.get_res_ports(nrow_half - 1, ndumc + ncol - 1)[1]
        outnr = self.get_res_ports(nrow_half - 1, ndumc + ncol)[1]
        outn = self.connect_wires([outnl, outnr])[0]
        outp_yt = outp.track_id.get_bounds(self.grid, unit_mode=True)[1]
        outn_yb = outn.track_id.get_bounds(self.grid, unit_mode=True)[0]

        vm_layer = outp.layer_id + 1
        vm_tr = self.grid.coord_to_nearest_track(vm_layer, outp.middle, half_track=True)
        vm_tid = TrackID(vm_layer, vm_tr, width=io_width)
        outp = self.connect_to_tracks(outp, vm_tid, min_len_mode=1)
        outn = self.connect_to_tracks(outn, vm_tid, min_len_mode=-1)

        # connect inp/inn
        inp = self.get_res_ports(nrow_half, ndumc)[0]
        inn = self.get_res_ports(nrow_half - 1, ndumc)[1]
        mid = (self.get_res_ports(nrow_half, ndumc - 1)[0].middle + inp.middle) / 2
        vm_tr = self.grid.coord_to_nearest_track(vm_layer, mid, half_track=True)
        vm_tid = TrackID(vm_layer, vm_tr, width=io_width)
        inp = self.connect_to_tracks(inp, vm_tid, min_len_mode=1)
        inn = self.connect_to_tracks(inn, vm_tid, min_len_mode=-1)

        # connect outcm
        cmp = self.get_res_ports(nrow_half, ndumc + 2 * ncol - 1)[0]
        cmn = self.get_res_ports(nrow_half - 1, ndumc + 2 * ncol - 1)[1]
        vm_tr = self.grid.coord_to_nearest_track(vm_layer, cmp.middle, half_track=True)
        vm_tid = TrackID(vm_layer, vm_tr, width=io_width)
        outcm_v = self.connect_to_tracks([cmp, cmn], vm_tid)
        hm_layer = vm_layer + 1
        hm_tr = self.grid.coord_to_nearest_track(hm_layer, outcm_v.middle, half_track=True)
        outcm = self.connect_to_tracks(outcm_v, TrackID(hm_layer, hm_tr, width=io_width),
                                       track_lower=0)
        self.add_pin('outcm', outcm, show=show_pins)

        return inp, inn, outp, outn, outcm_v, outp_yt, outn_yb

    def _connect_mirror(self, offset, loc1, loc2, port1, port2):
        r1, c1 = loc1
        r2, c2 = loc2
        for sgn in (-1, 1):
            cur_r1 = offset + sgn * r1
            cur_r2 = offset + sgn * r2
            if sgn < 0:
                cur_r1 -= 1
                cur_r2 -= 1
            if sgn < 0:
                cur_port1 = 1 - port1
                cur_port2 = 1 - port2
            else:
                cur_port1 = port1
                cur_port2 = port2
            wa1 = self.get_res_ports(cur_r1, c1)[cur_port1]
            wa2 = self.get_res_ports(cur_r2, c2)[cur_port2]
            if wa1.track_id.base_index == wa2.track_id.base_index:
                self.connect_wires([wa1, wa2])
            else:
                mode = -1 if c1 % 2 == 0 else 1
                vm_layer = wa1.layer_id + 1
                vm = self.grid.coord_to_nearest_track(vm_layer, wa1.middle_unit, mode=mode,
                                                      half_track=True, unit_mode=True)
                self.connect_to_tracks([wa1, wa2], TrackID(vm_layer, vm))

    def _connect_dummies(self, ncol, nr1, nr2, ndumr, ndumc):
        res_num_iter = chain(repeat(0, ndumc), repeat(nr1, ncol), repeat(nr2, ncol),
                             repeat(0, ndumc))
        nrow_half = max(nr1, nr2) + ndumr
        bot_warrs, top_warrs = [], []
        for col_idx, res_num in enumerate(res_num_iter):
            mode = -1 if col_idx % 2 == 0 else 1
            if res_num == 0:
                cur_ndum = nrow_half * 2
                bot_idx_list = [0]
            else:
                cur_ndum = nrow_half - res_num
                bot_idx_list = [0, nrow_half + res_num]

            for bot_idx in bot_idx_list:
                top_idx = bot_idx + cur_ndum
                warr_list = []
                for ridx in range(bot_idx, top_idx):
                    bp, tp = self.get_res_ports(ridx, col_idx)
                    warr_list.append(bp)
                    warr_list.append(tp)
                vm_layer = warr_list[0].layer_id + 1
                vm = self.grid.coord_to_nearest_track(vm_layer, warr_list[0].middle_unit, mode=mode,
                                                      half_track=True, unit_mode=True)
                sup_warr = self.connect_to_tracks(warr_list, TrackID(vm_layer, vm))
                if bot_idx == 0:
                    bot_warrs.append(sup_warr)
                if bot_idx != 0 or res_num == 0:
                    top_warrs.append(sup_warr)

        hm_layer = bot_warrs[0].layer_id + 1
        hm_pitch = self.grid.get_track_pitch(hm_layer, unit_mode=True)
        num_hm_tracks = self.array_box.height_unit // hm_pitch
        btr = self.connect_to_tracks(bot_warrs, TrackID(hm_layer, 0), track_lower=0)
        ttr = self.connect_to_tracks(top_warrs, TrackID(hm_layer, num_hm_tracks - 1),
                                     track_lower=0)

        return ttr, btr


class PassiveCTLE(SubstrateWrapper):
    """A wrapper with substrate contact around HighPassArrayClkCore

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
        SubstrateWrapper.__init__(self, temp_db, lib_name, params, used_names, **kwargs)

    @classmethod
    def get_params_info(cls):
        # type: () -> Dict[str, str]
        return dict(
            l='unit resistor length, in meters.',
            w='unit resistor width, in meters.',
            cap_height='capacitor height, in resolution units.',
            num_r1='number of r1 segments per column.',
            num_r2='number of r2 segments per column.',
            num_col='number of resistor columns.',
            num_dumc='number of dummy columns.',
            num_dumr='number of dummy rows.',
            sub_w='Substrate width.',
            sub_lch='Substrate channel length.',
            sub_type='the substrate type.',
            threshold='the substrate threshold flavor.',
            tr_widths='Track width dictionary.',
            tr_spaces='Track spacing dictionary.',
            port_tr_w='MOM cap port track width, in number of tracks.',
            res_type='the resistor type.',
            res_options='Configuration dictionary for ResArrayBase.',
            cap_spx='Space between capacitor and left/right edge, in resolution units.',
            cap_spy='Space between capacitor and cm-port/top/bottom edge, in resolution units.',
            sub_tr_w='substrate track width in number of tracks.  None for default.',
            show_pins='True to draw pin layous.',
        )

    @classmethod
    def get_default_param_values(cls):
        # type: () -> Dict[str, Any]
        return dict(
            port_tr_w=1,
            res_type='standard',
            res_options=None,
            cap_spx=0,
            cap_spy=0,
            sub_tr_w=None,
            show_pins=True,
        )

    def draw_layout(self):
        sub_w = self.params['sub_w']
        sub_lch = self.params['sub_lch']
        sub_type = self.params['sub_type']
        threshold = self.params['threshold']
        res_type = self.params['res_type']
        sub_tr_w = self.params['sub_tr_w']
        show_pins = self.params['show_pins']

        params = self.params.copy()
        _, sub_list = self.draw_layout_helper(PassiveCTLECore, params, sub_lch, sub_w, sub_tr_w,
                                              sub_type, threshold, show_pins, is_passive=True,
                                              res_type=res_type)
        self.extend_wires(sub_list, lower=0, unit_mode=True)

        self.fill_box = bnd_box = self.bound_box
        for lay in range(1, self.top_layer):
            self.do_max_space_fill(lay, bnd_box, fill_pitch=1.5)


class CMLResLoadCore(ResArrayBase):
    """load resistor for CML driver.

    Parameters
    ----------
    temp_db : :class:`bag.layout.template.TemplateDB`
        the template database.
    lib_name : str
        the layout library name.
    params : Dict[str, Any]
        the parameter values.
    used_names : Set[str]
        a set of already used cell names.
    **kwargs :
        dictionary of optional parameters.  See documentation of
        :class:`bag.layout.template.TemplateBase` for details.
    """

    def __init__(self, temp_db, lib_name, params, used_names, **kwargs):
        # type: (TemplateDB, str, Dict[str, Any], Set[str], **kwargs) -> None
        ResArrayBase.__init__(self, temp_db, lib_name, params, used_names, **kwargs)
        self._sch_params = None

    @property
    def sch_params(self):
        return self._sch_params

    @classmethod
    def get_params_info(cls):
        # type: () -> Dict[str, str]
        return dict(
            l='unit resistor length, in meters.',
            w='unit resistor width, in meters.',
            nx='number of columns.',
            ndum='number of dummies.',
            sub_type='the substrate type.',
            threshold='the substrate threshold flavor.',
            res_type='the resistor type.',
            res_options='Configuration dictionary for ResArrayBase.',
            em_specs='EM specifications for the termination network.',
            half_blk_x='True to allow for half horizontal blocks.',
            show_pins='True to show pins.',
        )

    @classmethod
    def get_default_param_values(cls):
        # type: () -> Dict[str, Any]
        return dict(
            res_type='standard',
            res_options=None,
            em_specs=None,
            half_blk_x=True,
            show_pins=True,
        )

    def draw_layout(self):
        # type: () -> None
        l = self.params['l']
        w = self.params['w']
        nx = self.params['nx']
        ndum = self.params['ndum']
        sub_type = self.params['sub_type']
        threshold = self.params['threshold']
        res_type = self.params['res_type']
        res_options = self.params['res_options']
        em_specs = self.params['em_specs']
        half_blk_x = self.params['half_blk_x']
        show_pins = self.params['show_pins']

        if res_options is None:
            my_options = dict(well_end_mode=2)
        else:
            my_options = res_options.copy()
            my_options['well_end_mode'] = 2
        if em_specs is None:
            em_specs = {}

        bot_layer = self.bot_layer_id
        top_layer = bot_layer + 3
        # draw array
        nx_tot = nx + 2 * ndum
        min_tracks = [2, 1, 1, 1]
        self.draw_array(l, w, sub_type, threshold, nx=nx_tot, ny=1, min_tracks=min_tracks,
                        em_specs=em_specs, top_layer=top_layer, res_type=res_type,
                        options=my_options, connect_up=True, half_blk_x=half_blk_x)

        # for each resistor, bring it to ym_layer
        for idx in range(nx_tot):
            bot, top = self.get_res_ports(0, idx)
            bot = self._export_to_ym(bot, bot_layer)
            top = self._export_to_ym(top, bot_layer)
            if ndum <= idx < nx_tot - ndum:
                self.add_pin('bot<%d>' % (idx - ndum), bot, show=show_pins)
                self.add_pin('top<%d>' % (idx - ndum), top, show=show_pins)
            else:
                self.add_pin('dummy', self.connect_wires([bot, top]), show=show_pins)

        self._sch_params = dict(
            l=l,
            w=w,
            intent=res_type,
            npar=nx,
            ndum=2 * ndum,
            sub_name='VSS',
        )

    def _export_to_ym(self, port, bot_layer):
        warr = port
        for off in range(1, 4):
            next_layer = bot_layer + off
            next_width = self.w_tracks[off]
            next_tr = self.grid.coord_to_nearest_track(next_layer, warr.middle_unit,
                                                       half_track=True, mode=0, unit_mode=True)
            tid = TrackID(next_layer, next_tr, width=next_width)
            warr = self.connect_to_tracks(warr, tid, min_len_mode=0)

        return warr


class CMLResLoad(SubstrateWrapper):
    """A wrapper with substrate contact around CMLResLoadCore

    Parameters
    ----------
    temp_db : :class:`bag.layout.template.TemplateDB`
            the template database.
    lib_name : str
        the layout library name.
    params : dict[str, any]
        the parameter values.
    used_names : set[str]
        a set of already used cell names.
    **kwargs :
        dictionary of optional parameters.  See documentation of
        :class:`bag.layout.template.TemplateBase` for details.
    """

    def __init__(self, temp_db, lib_name, params, used_names, **kwargs):
        # type: (TemplateDB, str, Dict[str, Any], Set[str], **Any) -> None
        SubstrateWrapper.__init__(self, temp_db, lib_name, params, used_names, **kwargs)
        self._out_xc_list = None
        self._sup_tracks = None

    @property
    def out_xc_list(self):
        # type: () -> List[int]
        return self._out_xc_list

    @property
    def sup_tracks(self):
        # type: () -> List[Union[float, int]]
        return self._sup_tracks

    @classmethod
    def get_params_info(cls):
        # type: () -> Dict[str, str]
        return dict(
            l='unit resistor length, in meters.',
            w='unit resistor width, in meters.',
            nx='number of columns.',
            ndum='number of dummies.',
            sub_w='Substrate width.',
            sub_lch='Substrate channel length.',
            sub_type='the substrate type.',
            threshold='the substrate threshold flavor.',
            res_type='the resistor type.',
            res_options='Configuration dictionary for ResArrayBase.',
            em_specs='EM specifications for the termination network.',
            sub_tr_w='substrate track width in number of tracks.  None for default.',
            show_pins='True to show pins.',
        )

    @classmethod
    def get_default_param_values(cls):
        # type: () -> Dict[str, Any]
        return dict(
            res_type='standard',
            res_options=None,
            em_specs=None,
            sub_tr_w=None,
            show_pins=True,
        )

    def draw_layout(self):
        # type: () -> None
        nx = self.params['nx']
        sub_w = self.params['sub_w']
        sub_lch = self.params['sub_lch']
        sub_type = self.params['sub_type']
        threshold = self.params['threshold']
        res_type = self.params['res_type']
        sub_tr_w = self.params['sub_tr_w']
        show_pins = self.params['show_pins']

        params = self.params.copy()
        tmp = self.place_instances(CMLResLoadCore, params, sub_lch, sub_w, sub_tr_w,
                                   sub_type, threshold, res_type=res_type, is_passive=True)
        inst, sub_insts, sub_port_name = tmp
        top_sub_warrs = sub_insts[1].get_all_port_pins(sub_port_name)

        self.fill_box = bnd_box = self.bound_box
        for lay in range(1, self.top_layer):
            self.do_max_space_fill(lay, bnd_box, fill_pitch=3)

        self._sup_tracks = []
        sub_list = [pin for inst in sub_insts for pin in inst.port_pins_iter(sub_port_name)]
        warrs = self.connect_to_track_wires(sub_list, inst.get_all_port_pins('dummy'))
        for warr in warrs:
            for tidx in warr.track_id:
                self._sup_tracks.append(tidx)
        self._sup_tracks.sort()

        self._out_xc_list = []
        for idx in range(nx):
            top = inst.get_pin('top<%d>' % idx)
            xc = self.grid.track_to_coord(top.layer_id, top.track_id.base_index, unit_mode=True)
            self._out_xc_list.append(xc)
            warrs = self.connect_to_track_wires(top_sub_warrs, top)
            self.add_pin(sub_port_name, warrs, show=show_pins)
            self.reexport(inst.get_port('bot<%d>' % idx), net_name='out', show=show_pins)

    @classmethod
    def connect_up_layers(cls, template, cur_layer, cur_warrs, xc_list, top_layer, em_specs,
                          v_mode=1):
        """Connect up layers while satisfying EM specs"""
        grid = template.grid

        cur_tr_w = cur_warrs[0].width
        cur_w = grid.get_track_width(cur_layer, cur_tr_w, unit_mode=True)
        nout = len(xc_list)
        mid_idx = nout // 2
        for next_layer in range(cur_layer + 1, top_layer + 1):
            if next_layer == top_layer:
                next_em_specs = em_specs.copy()
                for key in ['idc', 'iac_rms', 'iac_peak']:
                    if key in next_em_specs:
                        next_em_specs[key] *= nout
                bot_w = top_w = -1
            else:
                next_em_specs = em_specs
                top_tr_w = grid.get_min_track_width(next_layer + 1, **next_em_specs)
                top_w = grid.get_track_width(next_layer + 1, top_tr_w, unit_mode=True)
                bot_w = cur_w

            next_tr_w = grid.get_min_track_width(next_layer, bot_w=bot_w, top_w=top_w,
                                                 unit_mode=True, **next_em_specs)
            next_warrs = []
            if len(cur_warrs) == 1:
                for idx, xc in enumerate(xc_list):
                    mode = -1 if idx < mid_idx else 1
                    tr = grid.coord_to_nearest_track(next_layer, xc, half_track=True,
                                                     mode=mode, unit_mode=True)
                    tid = TrackID(next_layer, tr, width=next_tr_w)
                    next_warrs.append(template.connect_to_tracks(cur_warrs[0], tid, min_len_mode=0))
            else:
                yc = cur_warrs[0].middle_unit
                tr = grid.coord_to_nearest_track(next_layer, yc, half_track=True,
                                                 mode=v_mode, unit_mode=True)
                tid = TrackID(next_layer, tr, width=next_tr_w)
                next_warrs.append(template.connect_to_tracks(cur_warrs, tid, min_len_mode=0))

            cur_warrs = next_warrs
            cur_w = grid.get_track_width(next_layer, next_tr_w, unit_mode=True)

        return cur_warrs


class TermRXSingle(TemplateBase):
    """A single-ended termination block for RX.

    Parameters
    ----------
    temp_db : :class:`bag.layout.template.TemplateDB`
        the template database.
    lib_name : str
        the layout library name.
    params : Dict[str, Any]
        the parameter values.
    used_names : Set[str]
        a set of already used cell names.
    **kwargs :
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
            res_params='load resistor parameters.',
            esd_params='ESD black-box parameters.',
            cap_params='MOM cap parameters.',
            cap_out_tid='Capacitor output track ID.',
            em_specs='electro-migration specs.',
            top_layer='top level layer',
            fill_config='fill configuration dictionary.',
            show_pins='True to draw pins.',
        )

    @classmethod
    def get_default_param_values(cls):
        # type: () -> Dict[str, Any]
        return dict(
            cap_out_tid=None,
            em_specs=None,
            show_pins=True,
        )

    def draw_layout(self):
        # type: () -> None
        em_specs = self.params['em_specs']
        top_layer = self.params['top_layer']
        fill_config = self.params['fill_config']
        show_pins = self.params['show_pins']

        res = self.grid.resolution

        master_res, master_esd, master_cap, dum_params = self._make_masters()

        # compute placement
        box_res = master_res.bound_box
        box_esd = master_esd.bound_box
        box_cap = master_cap.bound_box
        w_res = box_res.width_unit
        w_esd = box_esd.width_unit
        w_cap = box_cap.width_unit
        h_res = box_res.height_unit

        w_tot = w_res + w_esd + w_cap
        h_tot = max(box_esd.height_unit, h_res, box_cap.height_unit)
        w_blk, h_blk = self.grid.get_fill_size(top_layer, fill_config, unit_mode=True)
        w_tot = -(-w_tot // w_blk) * w_blk
        h_tot = -(-h_tot // h_blk) * h_blk

        x_cap = w_tot - w_cap
        x_res = x_cap - w_res
        y_res = h_res

        # add instances
        inst_esd = self.add_instance(master_esd, 'XESD', (0, 0), unit_mode=True)
        inst_res = self.add_instance(master_res, 'XRES', (x_res, y_res),
                                     orient='MX', unit_mode=True)
        inst_cap = self.add_instance(master_cap, 'XCAP', (x_cap, 0), unit_mode=True)

        # set size
        self.array_box = tot_box = BBox(0, 0, w_tot, h_tot, res, unit_mode=True)
        self.set_size_from_bound_box(top_layer, tot_box, round_up=True)
        self.add_cell_boundary(tot_box)

        # connect input
        xc_list = [xc + x_res for xc in master_res.out_xc_list]
        self._connect_input(top_layer, xc_list, inst_esd, inst_res, inst_cap, em_specs, show_pins)

        # get supplies
        vss_res = inst_res.get_all_port_pins('VSS')
        self.extend_wires(vss_res, lower=0, unit_mode=True)
        vss = inst_esd.get_all_port_pins('VSS')
        vss.append(self.connect_to_track_wires(vss_res, inst_esd.get_pin('VSS_out')))
        vdd = inst_esd.get_all_port_pins('VDD')

        self.add_pin('VSS', vss, show=show_pins)
        self.add_pin('VDD', vdd, show=show_pins)

        # draw dummy fill
        fill_top_layer = vdd[0].layer_id
        self._fill_dummy(top_layer, fill_top_layer, tot_box, inst_res, inst_cap, dum_params)

        self._sch_params = dict(
            esd_params=master_esd.sch_params,
            res_params=master_res.sch_params,
            cap_params=master_cap.sch_params,
        )

    def _fill_dummy(self, top_layer, fill_top_layer, tot_box, inst_res, inst_cap, dum_params):
        res = self.grid.resolution

        box_res = inst_res.bound_box
        box_cap = inst_cap.bound_box

        # fill empty space
        yt = tot_box.top_unit
        for box in (box_res, box_cap):
            if box.top_unit < yt:
                cur_box = BBox(box.left_unit, box.top_unit, box.right_unit, yt, res, unit_mode=True)
                self._fill_space(cur_box, dum_params, fill_top_layer)

        # fill resistor
        for lay in range(inst_res.master.top_layer, fill_top_layer + 1):
            self.do_max_space_fill(lay, box_res, fill_pitch=2)

        # fill capacitor
        for lay in range(inst_cap.master.top_layer, top_layer):
            self.do_max_space_fill(lay, box_cap, fill_pitch=2)

    def _fill_space(self, fill_box, dum_params, fill_top_layer):
        dum_params['width'] = fill_box.width_unit
        dum_params['height'] = fill_box.height_unit

        master_dum = self.new_template(params=dum_params, temp_cls=DummyFillActive)
        self.add_instance(master_dum, loc=(fill_box.left_unit, fill_box.bottom_unit),
                          unit_mode=True)
        for lay_id in range(1, fill_top_layer + 1):
            self.do_max_space_fill(lay_id, fill_box, fill_pitch=2)

    def _connect_input(self, top_layer, xc_list, inst_esd, inst_res, inst_cap, em_specs, show_pins):
        cur_warrs = self.connect_wires([inst_esd.get_pin('in'), inst_cap.get_pin('plus')])
        in_warr = cur_warrs[0]
        res_pins = inst_res.get_all_port_pins('out')
        self.connect_to_track_wires(res_pins, in_warr)

        cur_layer = in_warr.layer_id
        if in_warr.layer_id < top_layer:
            # connect up layers.
            cur_warrs = CMLResLoad.connect_up_layers(self, cur_layer, cur_warrs, xc_list,
                                                     top_layer, em_specs)

        self.add_pin('in', cur_warrs[0], show=show_pins)
        self.add_pin('out', inst_cap.get_pin('minus'), show=show_pins)

    def _make_masters(self):
        res_params = self.params['res_params']
        esd_params = self.params['esd_params']
        cap_params = self.params['cap_params']
        cap_out_tid = self.params['cap_out_tid']
        em_specs = self.params['em_specs']
        fill_config = self.params['fill_config']

        res_params = res_params.copy()
        esd_params = esd_params.copy()
        cap_params = cap_params.copy()

        res_params['sub_type'] = 'ptap'
        res_params['em_specs'] = em_specs
        res_params['show_pins'] = False
        master_res = self.new_template(params=res_params, temp_cls=CMLResLoad)

        esd_params['show_pins'] = False
        master_esd = self.new_template(params=esd_params, temp_cls=BlackBoxTemplate)
        in_tid = master_esd.get_port('in').get_pins()[0].track_id

        cap_params['in_tid'] = (in_tid.base_index, in_tid.width)
        cap_params['out_tid'] = cap_out_tid
        cap_params['top_layer'] = master_res.top_layer
        cap_params['fill_config'] = fill_config
        cap_params['show_pins'] = False
        master_cap = self.new_template(params=cap_params, temp_cls=MOMCapCore)

        dum_params = dict(
            mos_type=cap_params['mos_type'],
            threshold=cap_params['threshold'],
        )

        return master_res, master_esd, master_cap, dum_params


class TermRX(TemplateBase):
    """A termination block for RX.

    Parameters
    ----------
    temp_db : :class:`bag.layout.template.TemplateDB`
        the template database.
    lib_name : str
        the layout library name.
    params : Dict[str, Any]
        the parameter values.
    used_names : Set[str]
        a set of already used cell names.
    **kwargs :
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
            res_params='load resistor parameters.',
            esd_params='ESD black-box parameters.',
            cap_params='MOM cap parameters.',
            cap_out_tid='Capacitor output track ID.',
            em_specs='electro-migration specs.',
            top_layer='top level layer',
            fill_config='fill configuration dictionary.',
            show_pins='True to draw pins.',
        )

    @classmethod
    def get_default_param_values(cls):
        # type: () -> Dict[str, Any]
        return dict(
            cap_out_tid=None,
            em_specs=None,
            show_pins=True,
        )

    def draw_layout(self):
        # type: () -> None
        show_pins = self.params['show_pins']

        params = self.params.copy()
        params['show_pins'] = False
        master = self.new_template(params=params, temp_cls=TermRXSingle)

        bnd_box = master.bound_box
        y0 = bnd_box.height_unit
        instn = self.add_instance(master, 'XN', loc=(0, y0), orient='MX', unit_mode=True)
        instp = self.add_instance(master, 'XP', loc=(0, y0), unit_mode=True)

        self.array_box = tot_box = bnd_box.merge(instp.bound_box)
        self.set_size_from_bound_box(master.top_layer, tot_box)

        self.reexport(instp.get_port('in'), net_name='inp', show=show_pins)
        self.reexport(instn.get_port('in'), net_name='inn', show=show_pins)
        self.reexport(instp.get_port('out'), net_name='outp', show=show_pins)
        self.reexport(instn.get_port('out'), net_name='outn', show=show_pins)
        for name in ('VDD', 'VSS'):
            label = name + ':'
            self.reexport(instp.get_port(name), label=label, show=show_pins)
            self.reexport(instn.get_port(name), label=label, show=show_pins)

        self._sch_params = master.sch_params
