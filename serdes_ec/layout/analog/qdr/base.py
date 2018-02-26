# -*- coding: utf-8 -*-

"""This module defines HybridQDRBaseInfo and HybridQDRBase, which draws hybrid QDR serdes blocks."""

from typing import TYPE_CHECKING, Optional, Dict, Any, Set, Tuple, List, Union

import abc

from abs_templates_ec.analog_core.base import AnalogBase, AnalogBaseInfo

if TYPE_CHECKING:
    from bag.layout.routing import TrackManager, RoutingGrid
    from bag.layout.template import TemplateDB


class HybridQDRBaseInfo(AnalogBaseInfo):
    """A class that calculates information to assist in HybridQDRBase layout.

    Parameters
    ----------
    grid : RoutingGrid
        the RoutingGrid object.
    lch : float
        the channel length of AnalogBase, in meters.
    guard_ring_nf : int
        guard ring width in number of fingers.  0 to disable.
    top_layer : Optional[int]
        the AnalogBase top layer ID.
    end_mode : int
        right/left/top/bottom end mode flag.  This is a 4-bit integer.  If bit 0 (LSB) is 1, then
        we assume there are no blocks abutting the bottom.  If bit 1 is 1, we assume there are no
        blocks abutting the top.  bit 2 and bit 3 (MSB) corresponds to left and right, respectively.
        The default value is 15, which means we assume this AnalogBase is surrounded by empty
        spaces.
    min_fg_sep : int
        minimum number of separation fingers.
    fg_tot : Optional[int]
        number of fingers in a row.
    """

    def __init__(self, grid, lch, guard_ring_nf, top_layer=None, end_mode=15, min_fg_sep=0,
                 fg_tot=None, **kwargs):
        # type: (RoutingGrid, float, int, Optional[int], int, int, Optional[int], **kwargs) -> None
        AnalogBaseInfo.__init__(self, grid, lch, guard_ring_nf, top_layer=top_layer,
                                end_mode=end_mode, min_fg_sep=min_fg_sep, fg_tot=fg_tot, **kwargs)

    def get_integ_amp_info(self, seg_dict):
        # type: (Dict[str, int]) -> Dict[str, Any]
        """Compute placement of transistors in the given integrating amplifier.

        Parameters
        ----------
        seg_dict : Dict[str, int]
            a dictionary containing number of segments per transistor type.

        Returns
        -------
        info_dict : Dict[str, Any]
            the amplifier information dictionary.  Has the following entries:

            seg_tot : int
                total number of segments needed to draw the integrating amplifier.
            col_dict : Dict[str, int]
                a dictionary of left side column indices of each transistor.
            sd_dict : Dict[Tuple[str, str], str]
                a dictionary from net name/transistor tuple to source-drain junction type.
        """
        need_sep = not self.abut_analog_mos
        fg_sep = self.min_fg_sep

        seg_load = seg_dict.get('load', 0)
        seg_enp = seg_dict.get('enp', 0)
        seg_casc = seg_dict.get('casc', 0)
        seg_in = seg_dict['in']
        seg_enn = seg_dict['enn']
        seg_tail = seg_dict['tail']

        # calculate PMOS center transistor number of fingers
        seg_ps = max(seg_enp, seg_load)
        if seg_load == 0:
            seg_pc = 0
        else:
            if need_sep or seg_load > seg_enp:
                seg_pc = seg_ps * 2 + fg_sep
            else:
                seg_pc = seg_ps * 2

        # calculate NMOS center transistor number of fingers
        seg_nc = max(seg_casc, seg_in)
        # calculate number of center fingers and total size
        seg_center = max(seg_nc, seg_pc)
        seg_single = max(seg_center, seg_enn, seg_tail)
        seg_tot = 2 * seg_single + fg_sep

        # compute column index of each transistor
        col_dict = {}
        center_off = (seg_single - seg_center) // 2
        if seg_load > 0:
            pc_off = center_off + (seg_center - seg_pc) // 2
            load_off = (seg_ps - seg_load) // 2
            enp_off = (seg_ps - seg_enp) // 2
            col_dict['load0'] = pc_off + load_off
            col_dict['load1'] = pc_off + seg_pc - load_off - seg_load
            col_dict['enp0'] = pc_off + enp_off
            col_dict['enp1'] = pc_off + seg_pc - enp_off - seg_enp

        nc_off = center_off + (seg_center - seg_nc) // 2
        if seg_casc > 0:
            col_dict['casc'] = nc_off + (seg_nc - seg_casc) // 2
        col_dict['in'] = nc_off + (seg_nc - seg_in) // 2
        col_dict['enn'] = min(seg_single - seg_enn, col_dict['in'])
        col_dict['tail'] = min(seg_single - seg_tail, col_dict['enn'])

        # compute source-drain junction type for each net
        sd_dict = {('VDD', 'load0'): 's', ('VDD', 'load1'): 's',
                   ('mp0', 'load0'): 'd', ('mp1', 'load1'): 'd'}
        sd_name = 'd' if (col_dict['enp0'] - col_dict['load0']) % 2 == 0 else 's'
        sd_dict[('mp0', 'enp0')] = sd_dict[('mp1', 'enp1')] = sd_name
        sd_name = 'd' if sd_name == 's' else 's'
        sd_dict[('out', 'enp0')] = sd_dict[('out', 'enp1')] = sd_name
        if seg_casc > 0:
            if (col_dict['casc'] - col_dict['enp0']) % 2 == 1:
                sd_name = 'd' if sd_name == 's' else 's'
            sd_dict[('out', 'casc')] = sd_name
            sd_name = 'd' if sd_name == 's' else 's'
            sd_dict[('cn', 'casc')] = sd_name
            if (col_dict['in'] - col_dict['casc']) % 2 == 1:
                sd_name = 'd' if sd_name == 's' else 's'
            sd_dict[('cn', 'in')] = sd_name
            sd_name = 'd' if sd_name == 's' else 's'
            sd_dict[('tail', 'in')] = sd_name
        else:
            if (col_dict['in'] - col_dict['enp0']) % 2 == 1:
                sd_name = 'd' if sd_name == 's' else 's'
            sd_dict[('out', 'in')] = sd_name
            sd_name = 'd' if sd_name == 's' else 's'
            sd_dict[('tail', 'in')] = sd_name
        if (col_dict['enn'] - col_dict['in']) % 2 == 1:
            sd_name = 'd' if sd_name == 's' else 's'
        sd_dict[('tail', 'enn')] = sd_name
        sd_name = 'd' if sd_name == 's' else 's'
        sd_dict[('foot', 'enn')] = sd_name
        if (col_dict['tail'] - col_dict['enn']) % 2 == 1:
            sd_name = 'd' if sd_name == 's' else 's'
        sd_dict[('foot', 'tail')] = sd_name
        sd_name = 'd' if sd_name == 's' else 's'
        sd_dict[('VSS', 'tail')] = sd_name

        return dict(
            seg_tot=seg_tot,
            col_dict=col_dict,
            sd_dict=sd_dict,
        )


class HybridQDRBase(AnalogBase, metaclass=abc.ABCMeta):
    """Subclass of AnalogBase that draws QDR serdes blocks.

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
        optional parameters.
    """

    n_name_list = ['tail', 'enn', 'in', 'casc']
    p_name_list = ['enp', 'load']

    def __init__(self, temp_db, lib_name, params, used_names, **kwargs):
        # type: (TemplateDB, str, Dict[str, Any], Set[str], **kwargs) -> None
        AnalogBase.__init__(self, temp_db, lib_name, params, used_names, **kwargs)
        self._row_lookup = {key: ('nch', idx) for idx, key in enumerate(self.n_name_list)}
        for idx, key in enumerate(self.p_name_list):
            self._row_lookup[key] = ('pch', idx)

    def get_row_index(self, name):
        # type: (str) -> Tuple[str, int]
        """Returns the row index of the given transistor name.

        Parameters
        ----------
        name : str
            the transistor name.

        Returns
        -------
        mos_type : str
            the transistor type.
        row_idx : int
            the row index.
        """
        if name not in self._row_lookup:
            raise ValueError('row %s not found.' % name)
        return self._row_lookup[name]

    def draw_rows(self,
                  lch,  # type: float
                  fg_tot,  # type: int
                  ptap_w,  # type: Union[float, int]
                  ntap_w,  # type: Union[float, int]
                  w_dict,  # type: Dict[str, Union[float, int]]
                  th_dict,  # type: Dict[str, str]
                  tr_manager,  # type: TrackManager
                  wire_names,  # type: Dict[str, Dict[str, List[str]]]
                  **kwargs  # type: **kwargs
                  ):
        # type: (...) -> None
        """Draw the transistors and substrate rows.

        Parameters
        ----------
        lch : float
            the transistor channel length, in meters
        fg_tot : int
            total number of fingers for each row.
        ptap_w : Union[float, int]
            pwell substrate contact width.
        ntap_w : Union[float, int]
            nwell substrate contact width.
        w_dict : Dict[str, Union[float, int]]
            dictionary from transistor type to row width.
        th_dict : Dict[str, str]
            dictionary from transistor type to threshold flavor.
        tr_manager : TrackManager
            the TrackManager object.
        wire_names : Dict[str, Dict[str, List[str]]]
            dictionary from transistor type to wires in that row.

        **kwargs
            addtional parameters for AnalogBase's draw_base() method.
        """
        guard_ring_nf = kwargs.pop('guard_ring_nf', 0)

        # pop unsupported arguments
        for name in ['ng_tracks', 'nds_tracks', 'pg_tracks', 'pds_tracks',
                     'n_orientations', 'p_orientations']:
            kwargs.pop(name)

        # make layout information object
        self.set_layout_info(HybridQDRBaseInfo(self.grid, lch, guard_ring_nf, fg_tot=fg_tot,
                                               **kwargs))

        nw_list, nth_list, n_wires = [], [], []
        for name in self.n_name_list:
            nw_list.append(w_dict[name])
            nth_list.append(th_dict[name])
            n_wires.append(wire_names[name])
        pw_list, pth_list, p_wires = [], [], []
        for name in self.p_name_list:
            pw_list.append(w_dict[name])
            pth_list.append(th_dict[name])
            p_wires.append(wire_names[name])

        n_orient = ['R0'] * len(nw_list)
        p_orient = ['MX'] * len(pw_list)

        # draw base
        self.draw_base(lch, fg_tot, ptap_w, ntap_w, nw_list, nth_list, pw_list, pth_list,
                       n_orientations=n_orient, p_orientations=p_orient,
                       guard_ring_nf=guard_ring_nf, tr_manager=tr_manager,
                       wire_names=dict(nch=n_wires, pch=p_wires), **kwargs)
