# -*- coding: utf-8 -*-

"""This module defines HybridQDRBaseInfo and HybridQDRBase, which draws hybrid QDR serdes blocks."""

from typing import TYPE_CHECKING, Optional, Dict, Any, Set, Tuple, List, Union

import abc

from abs_templates_ec.analog_core.base import AnalogBase, AnalogBaseInfo

if TYPE_CHECKING:
    from bag.layout.routing import WireArray, TrackManager, RoutingGrid
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

    def get_integ_amp_info(self, seg_dict, fg_min=0, fg_dum=0):
        # type: (Dict[str, int], int, int) -> Dict[str, Any]
        """Compute placement of transistors in the given integrating amplifier.

        Parameters
        ----------
        seg_dict : Dict[str, int]
            a dictionary containing number of segments per transistor type.
        fg_min : int
            minimum number of fingers.
        fg_dum : int
            number of dummy fingers on each side.

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
        fg_dum = max(fg_dum, -(-(fg_min - seg_tot) // 2))
        fg_tot = seg_tot + 2 * fg_dum

        # compute column index of each transistor
        col_dict = {}
        center_off = (seg_single - seg_center) // 2
        if seg_load > 0:
            pc_off = fg_dum + center_off + (seg_center - seg_pc) // 2
            load_off = (seg_ps - seg_load) // 2
            enp_off = (seg_ps - seg_enp) // 2
            col_dict['load0'] = pc_off + load_off
            col_dict['load1'] = pc_off + seg_pc - load_off - seg_load
            col_dict['enp0'] = pc_off + enp_off
            col_dict['enp1'] = pc_off + seg_pc - enp_off - seg_enp

        nc_off = fg_dum + center_off + (seg_center - seg_nc) // 2
        if seg_casc > 0:
            col_dict['casc'] = nc_off + (seg_nc - seg_casc) // 2
        col_dict['in'] = nc_off + (seg_nc - seg_in) // 2
        col_dict['enn'] = fg_dum + min(seg_single - seg_enn, col_dict['in'])
        col_dict['tail'] = fg_dum + min(seg_single - seg_tail, col_dict['enn'])

        # compute source-drain junction type for each net
        sd_dict = {('load0', 's'): 'VDD', ('load1', 's'): 'VDD',
                   ('load0', 'd'): 'mp0', ('load1', 'd'): 'mp1', }
        sd_dir_dict = {'load0': (2, 0), 'load1': (2, 0), }
        if (col_dict['enp0'] - col_dict['load0']) % 2 == 0:
            sd_dict[('enp0', 'd')] = 'mp0'
            sd_dict[('enp1', 'd')] = 'mp1'
            sd_dict[('enp0', 's')] = sd_dict[('enp1', 's')] = 'out'
            sd_name = 's'
            sd_dir_dict['enp0'] = sd_dir_dict['enp1'] = (0, 2)
        else:
            sd_dict[('enp0', 's')] = 'mp0'
            sd_dict[('enp1', 's')] = 'mp1'
            sd_dict[('enp0', 'd')] = sd_dict[('enp1', 'd')] = 'out'
            sd_name = 'd'
            sd_dir_dict['enp0'] = sd_dir_dict['enp1'] = (2, 0)
        if seg_casc > 0:
            if (col_dict['casc'] - col_dict['enp0']) % 2 == 1:
                sd_name = 'd' if sd_name == 's' else 's'
            sd_dict[('casc', sd_name)] = 'out'
            if sd_name == 'd':
                sd_dir = (0, 2)
                sd_name = 's'
            else:
                sd_dir = (2, 0)
                sd_name = 'd'
            sd_dict[('casc', sd_name)] = 'cn'
            sd_dir_dict['casc'] = sd_dir

            if (col_dict['in'] - col_dict['casc']) % 2 == 1:
                sd_name = 'd' if sd_name == 's' else 's'
            sd_dict[('in', sd_name)] = 'cn'
            if sd_name == 'd':
                sd_dir = (0, 2)
                sd_name = 's'
            else:
                sd_dir = (2, 0)
                sd_name = 'd'
            sd_dict[('in', sd_name)] = 'tail'
            sd_dir_dict['in'] = sd_dir
        else:
            if (col_dict['in'] - col_dict['enp0']) % 2 == 1:
                sd_name = 'd' if sd_name == 's' else 's'
            sd_dict[('in', sd_name)] = 'out'
            if sd_name == 'd':
                sd_dir = (0, 2)
                sd_name = 's'
            else:
                sd_dir = (2, 0)
                sd_name = 'd'
            sd_dict[('in', sd_name)] = 'tail'
            sd_dir_dict['in'] = sd_dir

        if (col_dict['enn'] - col_dict['in']) % 2 == 1:
            sd_name = 'd' if sd_name == 's' else 's'
        sd_dict[('enn', sd_name)] = 'tail'
        if sd_name == 'd':
            sd_dir = (0, 2)
            sd_name = 's'
        else:
            sd_dir = (2, 0)
            sd_name = 'd'
        sd_dict[('enn', sd_name)] = 'foot'
        sd_dir_dict['enn'] = sd_dir

        if (col_dict['tail'] - col_dict['enn']) % 2 == 1:
            sd_name = 'd' if sd_name == 's' else 's'
        sd_dict[('tail', sd_name)] = 'foot'
        if sd_name == 'd':
            sd_dir = (0, 2)
            sd_name = 's'
        else:
            sd_dir = (2, 0)
            sd_name = 'd'
        sd_dict[('tail', sd_name)] = 'VSS'
        sd_dir_dict['tail'] = sd_dir

        return dict(
            fg_tot=fg_tot,
            fg_dum=fg_dum,
            fg_sep=fg_sep,
            col_dict=col_dict,
            sd_dict=sd_dict,
            sd_dir_dict=sd_dir_dict,
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
    tran_list = [('load0', 'load'), ('load1', 'load'), ('enp0', 'enp'), ('enp1', 'enp'),
                 ('casc', 'casc'), ('in', 'in'), ('enn', 'enn'), ('tail', 'tail')]
    diff_nets = {'mp0', 'mp1', 'out', 'cn'}
    gate_dict = {'load0': 'pclk0', 'load1': 'pclk1', 'enp0': 'enp0', 'enp1': 'enp1',
                 'casc': 'casc', 'in': 'in', 'enn': 'enn', 'tail': 'nclk'}

    def __init__(self, temp_db, lib_name, params, used_names, **kwargs):
        # type: (TemplateDB, str, Dict[str, Any], Set[str], **kwargs) -> None
        AnalogBase.__init__(self, temp_db, lib_name, params, used_names, **kwargs)
        self._row_lookup = {key: ('nch', idx) for idx, key in enumerate(self.n_name_list)}
        for idx, key in enumerate(self.p_name_list):
            self._row_lookup[key] = ('pch', idx)

    @property
    def qdr_info(self):
        # type: () -> HybridQDRBaseInfo
        # noinspection PyTypeChecker
        return self.layout_info

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
            kwargs.pop(name, None)

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

    def _draw_integ_amp_mos(self,  # type: HybridQDRBase
                            col_idx,  # type: int
                            fg_tot,  # type: int
                            seg_dict,  # type: Dict[str, int]
                            col_dict,  # type: Dict[str, int]
                            sd_dict,  # type: Dict[Tuple[str, str], str]
                            sd_dir_dict,  # type: Dict[str, Tuple[int, int]]
                            net_prefix='',  # type: str
                            ):
        # type: (...) -> Dict[str, List[WireArray]]
        ports = {}
        for tran_name, tran_row in self.tran_list:
            seg = seg_dict.get(tran_row, 0)
            if seg > 0:
                # get transistor info
                mos_type, row_idx = self.get_row_index(tran_row)
                col = col_dict[tran_name]
                sdir, ddir = sd_dir_dict[tran_name]
                colp = col_idx + col
                coln = col_idx + (fg_tot - col - seg)
                snet = sd_dict[(tran_name, 's')]
                dnet = sd_dict[(tran_name, 'd')]
                # determine net names
                if snet in self.diff_nets:
                    snetp = snet + 'p'
                    snetn = snet + 'n'
                else:
                    snetp = snetn = snet
                if dnet in self.diff_nets:
                    dnetp = dnet + 'p'
                    dnetn = dnet + 'n'
                else:
                    dnetp = dnetn = dnet
                # draw transistors
                mp = self.draw_mos_conn(mos_type, row_idx, colp, seg, sdir, ddir,
                                        snet=net_prefix + snetp, dnet=net_prefix + dnetp)
                mn = self.draw_mos_conn(mos_type, row_idx, coln, seg, sdir, ddir,
                                        snet=net_prefix + snetn, dnet=net_prefix + dnetn)
                gnet = self.gate_dict[tran_name]
                # save gate port
                if tran_name == 'in':
                    ports[gnet + 'p'] = [mn['g']]
                    ports[gnet + 'n'] = [mp['g']]
                else:
                    ports[gnet] = [mp['g'], mn['g']]
                # save drain/source ports
                for name, warr in [(snetp, mp['s']), (snetn, mn['s']),
                                   (dnetp, mp['d']), (dnetn, mn['d'])]:
                    if name in ports:
                        cur_list = ports[name]
                    else:
                        cur_list = []
                        ports[name] = cur_list
                    cur_list.append(warr)

        return ports

    def draw_integ_amp(self,  # type: HybridQDRBase
                       col_idx,  # type: int
                       seg_dict,  # type: Dict[str, int]
                       fg_min=0,  # type: int
                       fg_dum=0,  # type: int
                       idx_dict=None,  # type: Optional[Dict[str, int]]]
                       ):
        # type: (...) -> Tuple[Dict[str, WireArray], Dict[str, Any]]
        """Draw a differential amplifier.

        Parameters
        ----------
        col_idx : int
            the left-most transistor index.  0 is the left-most transistor.
        seg_dict : Dict[str, int]
            a dictionary containing number of segments per transistor type.
        fg_min : int
            minimum number of total fingers.
        fg_dum : int
            minimum single-sided number of dummy fingers.
        idx_dict : Optional[Dict[str, int]]
            track index dictionary.

        Returns
        -------
        port_dict : Dict[str, WireArray]
            a dictionary from connection name to WireArray on horizontal routing layer.
        amp_info : Dict[str, Any]
            the amplifier layout information dictionary
        """
        if idx_dict is None:
            idx_dict = {}

        # get layout information
        amp_info = self.qdr_info.get_integ_amp_info(seg_dict, fg_min=fg_min, fg_dum=fg_dum)
        seg_casc = seg_dict.get('casc', 0)
        fg_tot = amp_info['fg_tot']
        col_dict = amp_info['col_dict']
        sd_dict = amp_info['sd_dict']
        sd_dir_dict = amp_info['sd_dir_dict']

        ports = self._draw_integ_amp_mos(col_idx, fg_tot, seg_dict, col_dict, sd_dict, sd_dir_dict)

        # connect wires
        self.connect_to_substrate('ntap', ports['VDD'])
        self.connect_to_substrate('ptap', ports['VSS'])
        # get TrackIDs
        foot_tid = self.get_wire_id('nch', 0, 'ds', wire_name='tail')
        tail_tid = self.get_wire_id('nch', 1, 'ds', wire_name='tail')
        outn_tid = self.get_wire_id('pch', 0, 'ds', wire_idx=0, wire_name='out')
        outp_tid = self.get_wire_id('pch', 0, 'ds', wire_idx=1, wire_name='out')
        inn_tid = self.get_wire_id('nch', 2, 'g', wire_idx=0, wire_name='in')
        inp_tid = self.get_wire_id('nch', 2, 'g', wire_idx=1, wire_name='in')
        mp_tid = self.get_wire_id('pch', 1, 'ds', wire_name='tail')
        nclk_tid = self.get_wire_id('nch', 0, 'g', wire_idx=idx_dict.get('nclk', -1))
        enn_tid = self.get_wire_id('nch', 1, 'g', wire_idx=idx_dict.get('enn', -1))
        enp0_tid = self.get_wire_id('pch', 0, 'g', wire_idx=idx_dict.get('enp0', 0))
        enp1_tid = self.get_wire_id('pch', 0, 'g', wire_idx=idx_dict.get('enp1', 1))
        pclk0_tid = self.get_wire_id('pch', 1, 'g', wire_idx=idx_dict.get('pclk0', 0))
        pclk1_tid = self.get_wire_id('pch', 1, 'g', wire_idx=idx_dict.get('pclk1', 1))

        # connect intermediate nodes
        self.connect_to_tracks(ports['foot'], foot_tid)
        self.connect_to_tracks(ports['tail'], tail_tid)
        for name in ('mp0p', 'mp0n', 'mp1p', 'mp1n'):
            self.connect_to_tracks(ports[name], mp_tid)

        # connect gates
        nclk = self.connect_to_tracks(ports['nclk'], nclk_tid)
        enn = self.connect_to_tracks(ports['enn'], enn_tid)
        enp0 = self.connect_to_tracks(ports['enp0'], enp0_tid)
        enp1 = self.connect_to_tracks(ports['enp1'], enp1_tid)
        pclk0 = self.connect_to_tracks(ports['pclk0'], pclk0_tid)
        pclk1 = self.connect_to_tracks(ports['pclk1'], pclk1_tid)

        hm_layer = outp_tid.layer_id
        out_w = outp_tid.width
        outp_idx = outp_tid.base_index
        outn_idx = outn_tid.base_index
        outp, outn = self.connect_differential_tracks(ports['outp'], ports['outn'], hm_layer,
                                                      outp_idx, outn_idx, width=out_w)
        in_w = inp_tid.width
        inp_idx = inp_tid.base_index
        inn_idx = inn_tid.base_index
        inp, inn = self.connect_differential_tracks(ports['inp'], ports['inn'], hm_layer,
                                                    inp_idx, inn_idx, width=in_w)

        ports = dict(inp=inp, inn=inn, outp=outp, outn=outn,
                     enp0=enp0, enp1=enp1, pclk0=pclk0, pclk1=pclk1,
                     enn=enn, nclk=nclk,
                     )

        # connect cascode if necessary
        if seg_casc > 0:
            cn_tid = self.get_wire_id('nch', 2, 'ds', wire_name='tail')
            casc_tid = self.get_wire_id('nch', 3, 'g', wire_idx=idx_dict.get('casc', -1))
            self.connect_to_tracks(ports['cn'], cn_tid)
            casc = self.connect_to_tracks(ports['casc'], casc_tid)
            ports['casc'] = casc

        return ports, amp_info
