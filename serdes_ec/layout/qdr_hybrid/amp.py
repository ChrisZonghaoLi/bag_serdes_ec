# -*- coding: utf-8 -*-

"""This module defines amplifier generators based on HybridQDRBase."""

from typing import TYPE_CHECKING, Dict, Any, Set, Tuple, Union

from bag.layout.routing import TrackManager

from .base import HybridQDRBaseInfo, HybridQDRBase

if TYPE_CHECKING:
    from bag.layout.template import TemplateDB


class IntegAmp(HybridQDRBase):
    """A single integrating amplifier.

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
        HybridQDRBase.__init__(self, temp_db, lib_name, params, used_names, **kwargs)
        self._sch_params = None
        self._fg_tot = None
        self._track_info = None
        self._hm_intvs = None
        self._hm_widths = None

    @property
    def sch_params(self):
        # type: () -> Dict[str, Any]
        return self._sch_params

    @property
    def fg_tot(self):
        # type: () -> int
        return self._fg_tot

    @property
    def track_info(self):
        # type: () -> Dict[str, Tuple[Union[float, int], int]]
        return self._track_info

    def get_vm_coord(self, vm_width, is_left, mode):
        # type: (int, bool, int) -> int
        if is_left:
            idx, sgn = 0, -1
        else:
            idx, sgn = 1, 1
        idx = 0 if is_left else 1
        other_coord = self._hm_intvs[0][idx]
        hm_layer = self.mos_conn_layer + 1
        if mode & 1 == 1:
            in_coord = self._vm_coord_helper(self._hm_intvs[1][idx], hm_layer, self._hm_widths[0],
                                             vm_width, sgn)
        else:
            in_coord = other_coord

        if mode & 2 == 2:
            out_coord = self._vm_coord_helper(self._hm_intvs[2][idx], hm_layer, self._hm_widths[1],
                                              vm_width, sgn)
        else:
            out_coord = other_coord

        if is_left:
            return min(other_coord, in_coord, out_coord)
        else:
            return max(other_coord, in_coord, out_coord)

    def _vm_coord_helper(self, coord, hm_layer, hm_w, vm_w, sgn):
        sple = self.grid.get_line_end_space(hm_layer, hm_w, unit_mode=True)
        extx = self.grid.get_via_extensions(hm_layer, hm_w, vm_w, unit_mode=True)[0]
        return coord + sgn * (sple + extx)

    @classmethod
    def get_amp_fg_info(cls, grid, lch, seg_dict):
        qdr_info = HybridQDRBaseInfo(grid, lch, 0, do_correct_v_pitch=True)
        fg_sep_hm = qdr_info.get_fg_sep_from_hm_space(1, round_even=True)
        fg_sep_hm = max(0, fg_sep_hm)

        amp_info = qdr_info.get_integ_amp_info(seg_dict, fg_dum=0, fg_sep_hm=fg_sep_hm)

        return amp_info['fg_tot'], fg_sep_hm

    @classmethod
    def get_params_info(cls):
        # type: () -> Dict[str, str]
        return dict(
            lch='channel length, in meters.',
            ptap_w='NMOS substrate width, in meters/number of fins.',
            ntap_w='PMOS substrate width, in meters/number of fins.',
            w_dict='NMOS/PMOS width dictionary.',
            th_dict='NMOS/PMOS threshold flavor dictionary.',
            seg_dict='number of segments dictionary.',
            fg_duml='Number of left edge dummy fingers.',
            fg_dumr='Number of right edge dummy fingers.',
            tr_widths='Track width dictionary.',
            tr_spaces='Track spacing dictionary.',
            flip_sign='True to flip summer output sign.',
            but_sw='True to reserve space for butterfly switch.',
            top_layer='Top layer ID',
            end_mode='The AnalogBase end_mode flag.',
            options='other AnalogBase options',
            min_height='Minimum height.',
            vss_tid='VSS track information.',
            vdd_tid='VDD track information.',
            sch_hp_params='Schematic high-pass filter parameters.',
            show_pins='True to create pin labels.',
            export_probe='True to export probe ports.',
        )

    @classmethod
    def get_default_param_values(cls):
        # type: () -> Dict[str, Any]
        return dict(
            flip_sign=False,
            but_sw=False,
            top_layer=None,
            end_mode=15,
            options=None,
            min_height=0,
            vss_tid=None,
            vdd_tid=None,
            sch_hp_params=None,
            show_pins=True,
            export_probe=False,
        )

    def draw_layout(self):
        lch = self.params['lch']
        ptap_w = self.params['ptap_w']
        ntap_w = self.params['ntap_w']
        w_dict = self.params['w_dict']
        th_dict = self.params['th_dict']
        seg_dict = self.params['seg_dict']
        fg_duml = self.params['fg_duml']
        fg_dumr = self.params['fg_dumr']
        tr_widths = self.params['tr_widths']
        tr_spaces = self.params['tr_spaces']
        flip_sign = self.params['flip_sign']
        but_sw = self.params['but_sw']
        top_layer = self.params['top_layer']
        end_mode = self.params['end_mode']
        options = self.params['options']
        min_height = self.params['min_height']
        vss_tid = self.params['vss_tid']
        vdd_tid = self.params['vdd_tid']
        sch_hp_params = self.params['sch_hp_params']
        show_pins = self.params['show_pins']
        export_probe = self.params['export_probe']

        if options is None:
            options = {}

        if but_sw:
            casc_g = [1, 1]
        else:
            casc_g = [1]

        # get track manager and wire names
        tr_manager = TrackManager(self.grid, tr_widths, tr_spaces, half_space=True)
        wire_names = {
            'tail': dict(g=['clk'], ds=[1]),
            'nen': dict(g=['clk', 'en'], ds=['ntail']),
            # add a track in input row drain/source for VDD of tail switch
            'in': dict(g2=['in', 'in']),
            'casc': dict(g=casc_g, ds=['ptail']),
            'pen': dict(ds2=['out', 'out'], g=['en', 'en']),
            'load': dict(ds=['ptail'], g=['clk', 'clk']),
        }

        # get total number of fingers
        hm_layer = self.mos_conn_layer + 1
        if top_layer is None:
            top_layer = hm_layer

        fg_amp, fg_sep_hm = self.get_amp_fg_info(self.grid, lch, seg_dict)
        fg_tot = fg_amp + fg_duml + fg_dumr
        self.draw_rows(lch, fg_tot, ptap_w, ntap_w, w_dict, th_dict, tr_manager, wire_names,
                       top_layer=top_layer, end_mode=end_mode, min_height=min_height, **options)

        # draw amplifier
        ports, _ = self.draw_integ_amp(fg_duml, seg_dict, invert=flip_sign,
                                       fg_dum=0, fg_sep_hm=fg_sep_hm)

        if seg_dict.get('tsw', 0) > 0:
            clkn_label = 'clkn:'
            self.add_pin('nclkn', ports['nclkn'], label=clkn_label, show=show_pins)
        else:
            clkn_label = 'clkn'

        w_sup = tr_manager.get_width(hm_layer, 'sup')
        sup_tids = [None, None]
        if vss_tid is None:
            vss_width = w_sup
        else:
            sup_tids[0] = vss_tid[0]
            vss_width = vss_tid[1]
        if vdd_tid is None:
            vdd_width = w_sup
        else:
            sup_tids[1] = vdd_tid[0]
            vdd_width = vdd_tid[1]
        vss_warrs, vdd_warrs = self.fill_dummy(vdd_width=vdd_width, vss_width=vss_width,
                                               sup_tids=sup_tids)
        vss_warr = vss_warrs[0]
        vdd_warr = vdd_warrs[0]
        self.add_pin('VSS', vss_warr, show=show_pins)
        self.add_pin('VDD', vdd_warr, show=show_pins)
        self._track_info = dict(
            VSS=(vss_warr.track_id.base_index, vss_warr.track_id.width),
            VDD=(vdd_warr.track_id.base_index, vdd_warr.track_id.width),
        )

        for name in ('inp', 'inn', 'outp', 'outn', 'biasp'):
            warr = ports[name]
            self.add_pin(name, warr, show=show_pins)
            self._track_info[name] = (warr.track_id.base_index, warr.track_id.width)

        for name in ('foot', 'tail'):
            warr = ports[name]
            self._track_info[name] = (warr.track_id.base_index, warr.track_id.width)
            if export_probe:
                self.add_pin(name, warr, show=True)

        nen3 = ports['nen3']
        self.add_pin('nen3', nen3, show=False)
        self._track_info['nen3'] = (nen3.track_id.base_index, nen3.track_id.width)
        if 'pen3' in ports:
            self.add_pin('pen3', ports['pen3'], show=False)
            self.add_pin('en<3>', nen3, label='en<3>:', show=show_pins)
            self.add_pin('en<3>', ports['pen3'], label='en<3>:', show=show_pins)
        else:
            self.add_pin('en<3>', nen3, show=show_pins)

        for value in (('pen2', 'en<2>'), ('clkp', 'clkp'), ('clkn', 'clkn', clkn_label),
                      ('casc', 'casc'), ('casc<0>', 'casc<0>'), ('casc<1>', 'casc<1>')):
            name, port_name = value[:2]
            if len(value) > 2:
                label = value[2]
            else:
                label = port_name
            if name in ports:
                warr = ports[name]
                self.add_pin(port_name, warr, label=label, show=show_pins)
                if port_name == 'clkp' or port_name == 'clkn':
                    self._track_info[port_name] = (warr.track_id.base_index, warr.track_id.width)

        # get intermediate wire intervals
        lower, upper = None, None
        for name in ('foot', 'tail', 'pm0p', 'pm0n', 'pm1p', 'pm1n', 'nmp', 'nmn'):
            if name in ports:
                warr = ports[name]
                if lower is None:
                    lower = warr.lower_unit
                    upper = warr.upper_unit
                else:
                    lower = min(lower, warr.lower_unit)
                    upper = max(upper, warr.upper_unit)

        self.fill_box = self.bound_box

        # set schematic parameters and other properties
        self._sch_params = self._get_sch_params(lch, w_dict, th_dict, seg_dict, sch_hp_params,
                                                flip_sign, export_probe)
        self._fg_tot = fg_tot
        self._hm_widths = (tr_manager.get_width(hm_layer, 'in'),
                           tr_manager.get_width(hm_layer, 'out'))
        self._hm_intvs = ((lower, upper),
                          (ports['inp'].lower_unit, ports['inp'].upper_unit),
                          (ports['outp'].lower_unit, ports['outp'].upper_unit))

    def _get_sch_params(self, lch, w_dict, th_dict, seg_dict, sch_hp_params,
                        flip_sign, export_probe):
        ndum_info = []
        pdum_info = []
        for info in self.get_sch_dummy_info():
            if info[0][0] == 'pch':
                pdum_info.append(info)
            else:
                ndum_info.append(info)

        nw_dict = {k: v for k, v in w_dict.items() if k != 'load' and k != 'pen'}
        nth_dict = {k: v for k, v in th_dict.items() if k != 'load' and k != 'pen'}
        nseg_dict = {k: v for k, v in seg_dict.items()
                     if k != 'load' and k != 'pen' and k != 'en_only' and k != 'en_swap'}
        pw_dict = {'load': w_dict.get('load', 0), 'pen': w_dict.get('pen', 0)}
        pth_dict = {'load': th_dict.get('load', 'standard'), 'pen': th_dict.get('pen', 'standard')}
        pseg_dict = {'load': seg_dict.get('load', 0), 'pen': seg_dict.get('pen', 0),
                     'en_only': seg_dict.get('en_only', False),
                     'en_swap': seg_dict.get('en_swap', False)}

        return dict(
            load_params=dict(
                lch=lch,
                w_dict=pw_dict,
                th_dict=pth_dict,
                seg_dict=pseg_dict,
                dum_info=pdum_info,
            ),
            gm_params=dict(
                lch=lch,
                w_dict=nw_dict,
                th_dict=nth_dict,
                seg_dict=nseg_dict,
                dum_info=ndum_info,
                hp_params=sch_hp_params,
                export_probe=export_probe,
            ),
            flip_sign=flip_sign,
        )
