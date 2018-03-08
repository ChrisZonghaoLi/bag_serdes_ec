# -*- coding: utf-8 -*-

"""This module contains LaygoBase templates used in QDR receiver."""

from typing import TYPE_CHECKING, Dict, Any, Set

from abs_templates_ec.laygo.core import LaygoBase

from bag.layout.routing import TrackManager

if TYPE_CHECKING:
    from bag.layout.template import TemplateDB


class SinClkDivider(LaygoBase):
    """A Sinusoidal clock divider using LaygoBase.

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
    **kwargs :
        dictionary of optional parameters.  See documentation of
        :class:`bag.layout.template.TemplateBase` for details.
    """

    def __init__(self, temp_db, lib_name, params, used_names, **kwargs):
        # type: (TemplateDB, str, Dict[str, Any], Set[str], **kwargs) -> None
        LaygoBase.__init__(self, temp_db, lib_name, params, used_names, **kwargs)
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
            row_layout_info='The AnalogBase layout information dictionary.',
            seg_dict='Number of segments dictionary.',
            tr_widths='Track width dictionary.',
            tr_spaces='Track spacing dictionary.',
        )

    def draw_layout(self):
        row_layout_info = self.params['row_layout_info']
        seg_dict = self.params['seg_dict'].copy()
        tr_widths = self.params['tr_widths']
        tr_spaces = self.params['tr_spaces']

        tr_manager = TrackManager(self.grid, tr_widths, tr_spaces, half_space=True)

        seg_sr = self._get_sr_latch_info(seg_dict)
        num_col = seg_sr

        self.set_rows_direct(row_layout_info, num_col=num_col)

        vss_ports, vdd_ports = self._draw_substrate(num_col)
        self._draw_sr_latch(num_col - seg_sr, num_col, seg_dict, tr_manager)

        self.fill_space()

    def _draw_substrate(self, num_col):
        nsub = self.add_laygo_mos(0, 0, num_col)
        psub = self.add_laygo_mos(self.num_rows - 1, 0, num_col)
        return nsub, psub

    @classmethod
    def _get_sr_latch_info(cls, seg_dict):

        seg_inv = seg_dict['sr_inv']
        seg_drv = seg_dict['sr_drv']
        seg_set = seg_dict['sr_set']
        seg_sp = seg_dict['sr_sp']
        seg_nand = seg_dict['sr_nand']

        if seg_inv % 2 != 0 or seg_drv % 2 != 0 or seg_sp % 2 != 0:
            raise ValueError('This generator only works for even sr_inv/sr_drv/sr_sp.')
        if seg_sp < 2:
            raise ValueError('sr_sp must be >= 2.')

        seg_nand_set = max(seg_nand * 2, seg_set)
        return (seg_inv + seg_drv + seg_sp + seg_nand_set) * 2

    def _draw_sr_latch(self, start, seg_tot, seg_dict, tr_manager):
        seg_nand = seg_dict['sr_nand']
        seg_set = seg_dict['sr_set']
        seg_sp = seg_dict['sr_sp']
        seg_inv = seg_dict['sr_inv']
        seg_drv = seg_dict['sr_drv']
        seg_nand_set = max(seg_nand * 2, seg_set)

        # place instances
        stop = start + seg_tot
        ridx = 2
        setl = self.add_laygo_mos(ridx, start + seg_nand_set - seg_set, seg_set)
        setr = self.add_laygo_mos(ridx, stop - seg_nand_set, seg_set)
        ridx += 1
        cidx = start + seg_nand_set - seg_nand * 2
        nnandl = self.add_laygo_mos(ridx, cidx, seg_nand, gate_loc='s', stack=True)
        pnandl = self.add_laygo_mos(ridx + 1, cidx, seg_nand, gate_loc='s', stack=True)
        cidx = stop - seg_nand_set
        nnandr = self.add_laygo_mos(ridx, cidx, seg_nand, gate_loc='s', stack=True, flip=True)
        pnandr = self.add_laygo_mos(ridx + 1, cidx, seg_nand, gate_loc='s', stack=True, flip=True)
        start += seg_nand_set + seg_sp
        stop -= seg_nand_set + seg_sp

        ndrvl = self.add_laygo_mos(ridx, start, seg_drv)
        pdrvl = self.add_laygo_mos(ridx + 1, start, seg_drv)
        cidx = stop - seg_drv
        ndrvr = self.add_laygo_mos(ridx, cidx, seg_drv)
        pdrvr = self.add_laygo_mos(ridx + 1, cidx, seg_drv)
        start += seg_drv
        stop -= seg_drv

        ninvl = self.add_laygo_mos(ridx, start, seg_inv)
        pinvl = self.add_laygo_mos(ridx + 1, start, seg_inv)
        cidx = stop - seg_inv
        ninvr = self.add_laygo_mos(ridx, cidx, seg_inv)
        pinvr = self.add_laygo_mos(ridx + 1, cidx, seg_inv)

        # compute track locations

        # gather wires
        vss_list = [inst['s'] for inst in (setl, setr, ndrvl, ndrvr, ninvl, ninvr)]
        vdd_list = [inst['s'] for inst in (pdrvl, pdrvr, pinvl, pinvr)]
        q_list = self.connect_wires([inst['d'] for inst in (nnandl, pnandl, ndrvl, pdrvl)])
        qb_list = self.connect_wires([inst['d'] for inst in (nnandr, pnandr, ndrvr, pdrvr)])
        s_list = self.connect_wires([ninvl['d'], pinvl['d']])
        r_list = self.connect_wires([ninvr['d'], pinvr['d']])
        nand_vss_list = [nnandl['s'], nnandr['s']]
        nand_vdd_list = [pnandl['s'], pnandr['s']]
