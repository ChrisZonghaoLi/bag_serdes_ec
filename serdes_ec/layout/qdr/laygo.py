# -*- coding: utf-8 -*-

"""This module contains LaygoBase templates used in QDR receiver."""

from typing import TYPE_CHECKING, Dict, Any, Set

from abs_templates_ec.laygo.core import LaygoBase

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
            seg_dict='Number of segments dictionary.'
        )

    def draw_layout(self):
        row_layout_info = self.params['row_layout_info']
        seg_dict = self.params['seg_dict'].copy()

        seg_sr = self._get_sr_latch_info(seg_dict)

        self.set_rows_direct(row_layout_info, num_col=seg_sr)

        self._draw_sr_latch(0, seg_sr, seg_dict)

        self.fill_space()

    @classmethod
    def _get_sr_latch_info(cls, seg_dict):

        seg_inv = seg_dict['sr_inv']
        seg_drv = seg_dict['sr_drv']
        seg_set = seg_dict['sr_set']
        seg_sp = seg_dict['sr_sp']
        seg_nand = seg_dict['sr_nand']

        if seg_inv % 2 != 0 or seg_drv % 2 != 0 or seg_sp % 2 != 0:
            raise ValueError('This generator only works for even sr_inv/sr_drv/sr_sp.')
        if seg_set < seg_nand * 2:
            raise ValueError('This generator only works if seg_set >= seg_nand * 2')

        return (seg_inv + seg_drv + seg_sp + seg_set) * 2

    def _draw_sr_latch(self, start, seg_tot, seg_dict):
        seg_nand = seg_dict['sr_nand']
        seg_set = seg_dict['sr_set']
        seg_sp = seg_dict['sr_sp']
        seg_inv = seg_dict['sr_inv']
        seg_drv = seg_dict['sr_drv']

        stop = start + seg_tot
        ridx = 2
        nx = seg_set // 2
        setl = self.add_laygo_primitive('fg2d', loc=(start, ridx), nx=nx, spx=2)
        setr = self.add_laygo_primitive('fg2d', loc=(stop - seg_set, ridx), nx=nx, spx=2)
        delta = seg_set - seg_nand * 2
        start += delta
        stop += delta

        ridx += 1
        nx = seg_nand
        nnandl = self.add_laygo_primitive('stack2s', loc=(start, ridx), nx=nx, spx=2)
        nnandr = self.add_laygo_primitive('stack2s', loc=(stop - seg_nand * 2, ridx),
                                          nx=nx, spx=2)
        pnandl = self.add_laygo_primitive('stack2s', loc=(start, ridx + 1), nx=nx, spx=2)
        pnandr = self.add_laygo_primitive('stack2s', loc=(stop - seg_nand * 2, ridx + 1),
                                          nx=nx, spx=2)
        delta = seg_nand * 2 + seg_sp
        start += delta
        stop -= delta
        nx = seg_drv // 2
        ndrvl = self.add_laygo_primitive('fg2d', loc=(start, ridx), nx=nx, spx=2)
        ndrvr = self.add_laygo_primitive('fg2d', loc=(stop - seg_drv, ridx), nx=nx, spx=2)
        pdrvl = self.add_laygo_primitive('fg2d', loc=(start, ridx + 1), nx=nx, spx=2)
        pdrvr = self.add_laygo_primitive('fg2d', loc=(stop - seg_drv, ridx + 1), nx=nx, spx=2)
        start += seg_drv
        stop -= seg_drv
        nx = seg_inv // 2
        ninvl = self.add_laygo_primitive('fg2d', loc=(start, ridx), nx=nx, spx=2)
        ninvr = self.add_laygo_primitive('fg2d', loc=(stop - seg_inv, ridx), nx=nx, spx=2)
        pinvl = self.add_laygo_primitive('fg2d', loc=(start, ridx + 1), nx=nx, spx=2)
        pinvr = self.add_laygo_primitive('fg2d', loc=(stop - seg_inv, ridx + 1), nx=nx, spx=2)
