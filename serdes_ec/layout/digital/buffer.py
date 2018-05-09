# -*- coding: utf-8 -*-

"""This module defines digital buffer templates."""

from typing import TYPE_CHECKING, Dict, Any, Set, List

from bag.layout.template import TemplateBase


from digital_ec.layout.stdcells.core import StdDigitalTemplate
from digital_ec.layout.stdcells.inv import InvChain

if TYPE_CHECKING:
    from bag.layout.template import TemplateDB


class BufferRow(StdDigitalTemplate):
    """A row of buffers.

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
        StdDigitalTemplate.__init__(self, temp_db, lib_name, params, used_names, **kwargs)
        self._sch_params = None

    @property
    def sch_params(self):
        # type: () -> Dict[str, Any]
        return self._sch_params

    @classmethod
    def get_cache_properties(cls):
        # type: () -> List[str]
        """Returns a list of properties to cache."""
        return ['sch_params']

    @classmethod
    def get_params_info(cls):
        # type: () -> Dict[str, str]
        return dict(
            config='laygo configuration dictionary.',
            nbuf='number of buffers per row.',
            seg_list='number of segments for each inverter in the buffer.',
            tr_widths='Track width dictionary.',
            tr_spaces='Track spacing dictionary.',
            ncol_min='Minimum number of columns.',
            wp_list='list of PMOS widths.',
            wn_list='list of NMOS widths.',
            row_layout_info='Row layout information dictionary.',
            show_pins='True to draw pin geometries.',
        )

    @classmethod
    def get_default_param_values(cls):
        # type: () -> Dict[str, Any]
        return dict(
            wp_list=None,
            wn_list=None,
            row_layout_info=None,
            show_pins=True,
        )

    def draw_layout(self):
        blk_sp = 2

        nbuf = self.params['nbuf']
        tr_widths = self.params['tr_widths']
        tr_spaces = self.params['tr_spaces']
        ncol_min = self.params['ncol_min']
        show_pins = self.params['show_pins']

        base_params = self.params.copy()
        base_params['show_pins'] = False
        master = self.new_template(params=base_params, temp_cls=InvChain)

        tap_ncol = self.sub_columns
        buf_ncol = master.num_cols
        ncol = max(ncol_min, 2 * tap_ncol + nbuf * buf_ncol + 2 * blk_sp)

        # setup floorplan
        row_layout_info = master.row_layout_info
        self.initialize(row_layout_info, 1, ncol)

        # draw taps and get supplies
        vdd_list, vss_list = [], []
        for cidx in (0, ncol - tap_ncol):
            tap = self.add_substrate_tap((cidx, 0))
            vdd_list.extend(tap.port_pins_iter('VDD'))
            vss_list.extend(tap.port_pins_iter('VSS'))
        vdd = self.connect_wires(vdd_list)
        vss = self.connect_wires(vss_list)

        # draw instances
        inst_list = []
        for idx in range(nbuf):
            cidx = tap_ncol + blk_sp + idx * buf_ncol
            inst_list.append(self.add_digital_block(master, (cidx, 0)))
        self.fill_space()

        self._sch_params = dict()
