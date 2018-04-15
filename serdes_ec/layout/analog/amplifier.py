# -*- coding: utf-8 -*-

"""This module defines amplifier templates used in high speed links.
"""

from typing import Dict, Any, Set

from bag.layout.routing import TrackManager
from bag.layout.template import TemplateDB

from serdes_ec.layout.analog.base import SerdesRXBase, SerdesRXBaseInfo


class DiffAmp(SerdesRXBase):
    """A single diff amp.

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
        super(DiffAmp, self).__init__(temp_db, lib_name, params, used_names, **kwargs)
        self._sch_params = None

    @property
    def sch_params(self):
        # type: () -> Dict[str, Any]
        return self._sch_params

    @classmethod
    def get_default_param_values(cls):
        # type: () -> Dict[str, Any]
        """Returns a dictionary containing default parameter values.

        Override this method to define default parameter values.  As good practice,
        you should avoid defining default values for technology-dependent parameters
        (such as channel length, transistor width, etc.), but only define default
        values for technology-independent parameters (such as number of tracks).

        Returns
        -------
        default_params : dict[str, any]
            dictionary of default parameter values.
        """
        return dict(
            flip_out_sd=False,
            guard_ring_nf=0,
            top_layer=None,
            show_pins=True,
            options=None,
        )

    @classmethod
    def get_params_info(cls):
        """Returns a dictionary containing parameter descriptions.

        Override this method to return a dictionary from parameter names to descriptions.

        Returns
        -------
        param_info : dict[str, str]
            dictionary from parameter name to description.
        """
        return dict(
            lch='channel length, in meters.',
            ptap_w='NMOS substrate width, in meters/number of fins.',
            ntap_w='PMOS substrate width, in meters/number of fins.',
            w_dict='NMOS/PMOS width dictionary.',
            th_dict='NMOS/PMOS threshold flavor dictionary.',
            seg_dict='NMOS/PMOS number of segments dictionary.',
            fg_dum='Number of single-sided edge dummy fingers.',
            flip_out_sd='True to flip output source/drain.',
            guard_ring_nf='Width of the guard ring in number of fingers.  0 to disable.',
            top_layer='the top routing layer.',
            tr_widths='Track width dictionary.',
            tr_spaces='Track spacing dictionary.',
            show_pins='True to create pin labels.',
            options='AnalogBase options',
        )

    def draw_layout(self):
        """Draw the layout of a dynamic latch chain.
        """
        lch = self.params['lch']
        ptap_w = self.params['ptap_w']
        ntap_w = self.params['ntap_w']
        w_dict = self.params['w_dict']
        th_dict = self.params['th_dict']
        seg_dict = self.params['seg_dict']
        fg_dum = self.params['fg_dum']
        flip_out_sd = self.params['flip_out_sd']
        guard_ring_nf = self.params['guard_ring_nf']
        top_layer = self.params['top_layer']
        tr_widths = self.params['tr_widths']
        tr_spaces = self.params['tr_spaces']
        show_pins = self.params['show_pins']
        options = self.params['options']

        if options is None:
            options = {}

        # make SerdesRXBaseInfo and compute total number of fingers.
        serdes_info = SerdesRXBaseInfo(self.grid, lch, guard_ring_nf, top_layer=top_layer)
        diffamp_info = serdes_info.get_diffamp_info(seg_dict, fg_dum=fg_dum,
                                                    flip_out_sd=flip_out_sd)
        fg_tot = diffamp_info['fg_tot']

        # construct number of tracks dictionary
        row_names = ['load', 'casc', 'in', 'sw', 'en', 'tail']
        gtr_lists = [['bias'], ['bias'], ['in', 'in'], ['bias'], ['bias'], ['bias']]
        dtr_lists = [['out', 'out'], ['mid'], [], ['vdd'], ['tail'], ['tail']]
        dtr_names = [['outp', 'outn'], [('midp', 'midn')], [], ['vddn'], ['tail'], ['tail']]

        # rename tail row drain net name if enable row exists
        if w_dict.get('en', 0) > 0:
            dtr_lists[-1][0] = 'foot'

        hm_layer = self.mos_conn_layer + 1
        tr_manager = TrackManager(self.grid, tr_widths, tr_spaces)
        g_ntr_dict, ds_ntr_dict, tr_indices = {}, {}, {}
        for row_name, gtr_list, dtr_list, dtr_name_list in \
                zip(row_names, gtr_lists, dtr_lists, dtr_names):
            w_row = w_dict.get(row_name, 0)
            if w_row > 0:
                num_gtr, _ = tr_manager.place_wires(hm_layer, gtr_list)
                if dtr_list:
                    dtr_sp = tr_manager.get_space(hm_layer, dtr_list[0])
                    num_dtr, didx_list = tr_manager.place_wires(hm_layer, dtr_list,
                                                                start_idx=dtr_sp)
                    for dtr_name, dtr_idx in zip(dtr_name_list, didx_list):
                        if isinstance(dtr_name, tuple):
                            for dtr_n in dtr_name:
                                tr_indices[dtr_n] = dtr_idx
                        else:
                            tr_indices[dtr_name] = dtr_idx
                    num_dtr += 2 * dtr_sp
                else:
                    num_dtr = 1

                g_ntr_dict[row_name] = num_gtr
                ds_ntr_dict[row_name] = num_dtr

        # draw transistor rows
        self.draw_rows(lch, fg_tot, ptap_w, ntap_w, w_dict, th_dict, g_ntr_dict, ds_ntr_dict,
                       guard_ring_nf=guard_ring_nf, **options)

        # draw diffamp
        amp_ports, _ = self.draw_diffamp(0, seg_dict, tr_widths=tr_widths, tr_spaces=tr_spaces,
                                         tr_indices=tr_indices, fg_dum=fg_dum,
                                         flip_out_sd=flip_out_sd)

        # add dummies and pins
        vss_warrs, vdd_warrs = self.fill_dummy()
        self.add_pin('VSS', vss_warrs)
        self.add_pin('VDD', vdd_warrs)
        hide_pins = {'midp', 'midn', 'tail', 'foot'}
        for pname, warrs in amp_ports.items():
            self.add_pin(pname, warrs, show=show_pins and pname not in hide_pins)

        # compute schematic parameters
        self._sch_params = dict(
            lch=lch,
            w_dict=w_dict.copy(),
            th_dict=th_dict.copy(),
            seg_dict=seg_dict.copy(),
            dum_info=self.get_sch_dummy_info(),
        )
