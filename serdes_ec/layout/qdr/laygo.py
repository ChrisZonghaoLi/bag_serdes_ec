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
        seg_dict = self.params['seg_dict']

        num_col = self._get_sr_latch_seg(seg_dict)

        self.set_rows_direct(row_layout_info, num_col=num_col)

        self.fill_space()

    def _get_sr_latch_seg(self, seg_dict):
        seg_nand = 1
        seg_set = 2
        seg_sp = 2

        seg_inv = seg_dict['sr_inv']
        seg_drv = seg_dict['sr_drv']

        if seg_inv % 2 == 0 or seg_drv % 2 == 0:
            raise ValueError('This generator only works for even sr_inv or sr_drv.')

        return (seg_inv + seg_drv + seg_sp + seg_set) * 2

    def _draw_sr_latch(self, seg_dict):
        seg_nand = 1
        seg_set = 2

        seg_inv = seg_dict['sr_inv']
        seg_drv = seg_dict['sr_drv']

        if seg_inv % 2 == 0 or seg_drv % 2 == 0:
            raise ValueError('This generator only works for even sr_inv or sr_drv.')



