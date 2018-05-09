# -*- coding: utf-8 -*-

"""This module defines digital buffer templates."""

from typing import TYPE_CHECKING, Dict, Any, Set, List

from bag.layout.routing.base import TrackID, WireArray

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

    _blk_sp = 2

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
            out_delta='output track spacing from middle wire.',
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
            out_delta=1,
            ncol_min=0,
            wp_list=None,
            wn_list=None,
            row_layout_info=None,
            show_pins=True,
        )

    def draw_layout(self):
        nbuf = self.params['nbuf']
        seg_list = self.params['seg_list']
        out_delta = self.params['out_delta']
        ncol_min = self.params['ncol_min']
        show_pins = self.params['show_pins']

        base_params = self.params.copy()
        base_params['show_pins'] = False
        master = self.new_template(params=base_params, temp_cls=InvChain)
        mid_tidx = master.mid_tidx
        base_params['sig_locs'] = dict(out=mid_tidx + out_delta)
        master = self.new_template(params=base_params, temp_cls=InvChain)
        vm_layer = master.get_port('out').get_pins()[0].layer_id

        tap_ncol = self.sub_columns
        buf_ncol = master.num_cols
        ncol = max(ncol_min, self.compute_num_cols(self.grid.tech_info, self.lch_unit,
                                                   nbuf, seg_list))

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

        # draw instances, and export ports
        hm_layer = vm_layer + 1
        num_h_tr2 = self.get_num_x_tracks(hm_layer, half_int=True)
        in_idx0 = ((num_h_tr2 - 2 * nbuf) // 2) / 2
        for idx in range(nbuf):
            cidx = tap_ncol + self._blk_sp + idx * buf_ncol
            cur_inst = self.add_digital_block(master, (cidx, 0))
            cur_mid = cur_inst.translate_master_track(vm_layer, mid_tidx)
            cur_in = self.connect_to_tracks(cur_inst.get_pin('in'), TrackID(vm_layer, cur_mid - 1),
                                            min_len_mode=0)
            cur_in = self.connect_to_tracks(cur_in, TrackID(hm_layer, in_idx0 + idx),
                                            min_len_mode=0)
            self.add_pin('in<%d>' % idx, cur_in, show=show_pins)
            self.add_pin('out<%d>' % idx, cur_inst.get_pin('out'), show=show_pins)
        self.fill_space()

        self.add_pin('VDD', vdd, show=show_pins)
        self.add_pin('VSS', vss, show=show_pins)

        self._sch_params = dict(
            nbuf=nbuf,
            buf_params=master.sch_params
        )

    @classmethod
    def compute_num_cols(cls, tech_info, lch_unit, nbuf, seg_list):
        tap_ncol = cls.get_sub_columns(tech_info, lch_unit)
        buf_ncol = InvChain.compute_num_cols(seg_list)
        return 2 * tap_ncol + nbuf * buf_ncol + 2 * cls._blk_sp


class BufferArray(StdDigitalTemplate):
    """An array of buffers

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

    _blk_sp = 2

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
            nbuf_list='list of number of buffers per row.',
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
            ncol_min=0,
            wp_list=None,
            wn_list=None,
            row_layout_info=None,
            show_pins=True,
        )

    def draw_layout(self):
        nbuf_list = self.params['nbuf_list']
        seg_list = self.params['seg_list']
        ncol_min = self.params['ncol_min']
        row_layout_info = self.params['row_layout_info']
        show_pins = self.params['show_pins']

        # compute number of rows and columns
        nrow = len(nbuf_list)
        tech_info = self.grid.tech_info
        lch_unit = self.lch_unit
        ncol = 0
        for nbuf in nbuf_list:
            ncol = max(ncol, BufferRow.compute_num_cols(tech_info, lch_unit, nbuf, seg_list))
        ncol = max(ncol, ncol_min)

        # setup floorplan and add instances
        params = self.params.copy()
        params['ncol_min'] = ncol
        params['show_pins'] = False
        inst_list = []
        vdd_list = []
        vss_list = []
        buf_params = None
        idx0 = 0
        for ridx, nbuf in enumerate(nbuf_list):
            params['nbuf'] = nbuf
            params['out_delta'] = ridx + 1
            master = self.new_template(params=params, temp_cls=BufferRow)
            if row_layout_info is None:
                buf_params = master.sch_params['buf_params']
                params['row_layout_info'] = row_layout_info = master.row_layout_info
                self.initialize(row_layout_info, nrow, ncol, draw_boundaries=True, end_mode=15)
            inst = self.add_digital_block(master, (0, ridx))
            for idx in range(nbuf):
                self.reexport(inst.get_port('in<%d>' % idx), net_name='in<%d>' % (idx + idx0),
                              show=show_pins)
                self.reexport(inst.get_port('out<%d>' % idx), net_name='out<%d>' % (idx + idx0),
                              show=show_pins)
            idx0 += nbuf
            vdd_list.append(inst.get_pin('VDD'))
            vss_list.append(inst.get_pin('VSS'))
            inst_list.append(inst)

        # fill remaining space
        self.fill_space()

        self.add_pin('VDD', WireArray.list_to_warr(vdd_list), show=show_pins)
        self.add_pin('VSS', WireArray.list_to_warr(vss_list), show=show_pins)

        self._sch_params = dict(
            nbuf_list=nbuf_list,
            buf_params=buf_params,
        )
