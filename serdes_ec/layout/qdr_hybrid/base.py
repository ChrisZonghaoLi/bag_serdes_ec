# -*- coding: utf-8 -*-

"""This module defines HybridQDRBaseInfo and HybridQDRBase, which draws Hybrid-QDR serdes blocks."""

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

    def get_integ_amp_info(self, seg_dict, fg_min=0, fg_dum=0, fg_sep_hm=0):
        # type: (Dict[str, int], int, int, int) -> Dict[str, Any]
        """Compute placement of transistors in the given integrating amplifier.

        Parameters
        ----------
        seg_dict : Dict[str, int]
            a dictionary containing number of segments per transistor type.
        fg_min : int
            minimum number of fingers.
        fg_dum : int
            number of dummy fingers on each side.
        fg_sep_hm : int
            number of fingers separating the load reset switches.

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
        fg_sep = self.min_fg_sep
        fg_sep_load = max(0, fg_sep_hm - 2)

        seg_load = seg_dict.get('load', 0)
        seg_pen = seg_dict.get('pen', 0)
        seg_casc = seg_dict.get('casc', 0)
        seg_but = seg_dict.get('but', 0)
        seg_in = seg_dict['in']
        seg_nen = seg_dict['nen']
        seg_tail = seg_dict['tail']

        if seg_casc > 0 < seg_but:
            raise ValueError('Cannot have both cascode transistor and butterfly switch.')
        if seg_load > 0 and seg_but > 0:
            raise ValueError('Cannot have both butterfly switch and load.')

        # calculate PMOS center transistor number of fingers
        seg_ps = max(seg_pen, seg_load)
        if seg_load == 0:
            seg_pc = 0
        else:
            if not self.abut_analog_mos or fg_sep_load > 0 or seg_load > seg_pen:
                fg_sep_load = max(fg_sep_load, fg_sep)
            else:
                fg_sep_load = 0
            seg_pc = seg_ps * 2 + fg_sep_load

        if seg_casc > 0 or seg_but > 0:
            fg_sep = max(fg_sep, fg_sep_hm)

        # calculate NMOS center transistor number of fingers
        if seg_but > 0:
            if self.abut_analog_mos:
                seg_but_tot = 2 * seg_but
            else:
                seg_but_tot = 2 * seg_but + fg_sep
        else:
            seg_but_tot = 0
        seg_nc = max(seg_casc, seg_in, seg_but_tot)

        # calculate number of center fingers and total size
        seg_center = max(seg_nc, seg_pc)
        seg_single = max(seg_center, seg_nen, seg_tail)
        seg_tot = 2 * seg_single + fg_sep
        fg_dum = max(fg_dum, -(-(fg_min - seg_tot) // 2))
        fg_tot = seg_tot + 2 * fg_dum

        if abs(seg_pc - seg_nc) % 4 == 2:
            if seg_pc < seg_nc:
                pcol_delta = 1
                ncol_delta = 0
            else:
                pcol_delta = 0
                ncol_delta = 1
        else:
            pcol_delta = ncol_delta = 0

        # compute column index of each transistor
        col_dict = {}
        center_off = (seg_single - seg_center) // 2
        if seg_load > 0:
            pc_off = fg_dum + center_off + (seg_center - seg_pc) // 2
            load_off = (seg_ps - seg_load) // 2
            pen_off = (seg_ps - seg_pen) // 2
            col_dict['load0'] = pc_off + load_off + pcol_delta
            col_dict['load1'] = pc_off + seg_pc - load_off - seg_load + pcol_delta
            col_dict['pen0'] = pc_off + pen_off + pcol_delta
            col_dict['pen1'] = pc_off + seg_pc - pen_off - seg_pen + pcol_delta

        nc_off = fg_dum + center_off + (seg_center - seg_nc) // 2
        if seg_casc > 0:
            col_dict['casc'] = nc_off + (seg_nc - seg_casc) // 2 + ncol_delta
        elif seg_but > 0:
            col_dict['but0'] = nc_off + pcol_delta
            col_dict['but1'] = nc_off + seg_nc - seg_but + pcol_delta

        col_in = nc_off + (seg_nc - seg_in) // 2 + ncol_delta
        col_dict['in'] = col_in
        col_nen = fg_dum + col_in + seg_in - seg_nen
        if col_nen < col_in:
            col_nen = fg_dum + min(seg_single - seg_nen, col_in)
        col_dict['nen'] = col_nen
        col_tail = fg_dum + col_nen + seg_nen - seg_tail
        if col_tail < col_nen:
            col_tail = fg_dum + min(seg_single - seg_tail, col_nen)
        col_dict['tail'] = col_tail

        # compute source-drain junction type for each net
        if seg_load > 0:
            sd_dict = {('load0', 's'): 'VDD', ('load1', 's'): 'VDD',
                       ('load0', 'd'): 'pm0', ('load1', 'd'): 'pm1', }
            sd_dir_dict = {'load0': (2, 0), 'load1': (2, 0), }
            if (col_dict['pen0'] - col_dict['load0']) % 2 == 0:
                sd_dict[('pen0', 'd')] = 'pm0'
                sd_dict[('pen1', 'd')] = 'pm1'
                sd_dict[('pen0', 's')] = sd_dict[('pen1', 's')] = 'out'
                sd_name = 's'
                sd_dir_dict['pen0'] = sd_dir_dict['pen1'] = (0, 2)
            else:
                sd_dict[('pen0', 's')] = 'pm0'
                sd_dict[('pen1', 's')] = 'pm1'
                sd_dict[('pen0', 'd')] = sd_dict[('pen1', 'd')] = 'out'
                sd_name = 'd'
                sd_dir_dict['pen0'] = sd_dir_dict['pen1'] = (2, 0)
            prev_col = col_dict['pen0']
        else:
            sd_dict = {}
            sd_dir_dict = {}
            sd_name = 'd'
            prev_col = None
        if seg_casc > 0:
            if prev_col is not None and (col_dict['casc'] - prev_col) % 2 == 1:
                sd_name = 'd' if sd_name == 's' else 's'

            sd_dict[('casc', sd_name)] = 'out'
            if sd_name == 'd':
                sd_dir = (0, 2)
                sd_name = 's'
            else:
                sd_dir = (2, 0)
                sd_name = 'd'
            sd_dict[('casc', sd_name)] = 'nm'
            sd_dir_dict['casc'] = sd_dir

            if (col_dict['in'] - col_dict['casc']) % 2 == 1:
                sd_name = 'd' if sd_name == 's' else 's'
            sd_dict[('in', sd_name)] = 'nm'
            if sd_name == 'd':
                sd_dir = (0, 2)
                sd_name = 's'
            else:
                sd_dir = (2, 0)
                sd_name = 'd'
            sd_dict[('in', sd_name)] = 'tail'
            sd_dir_dict['in'] = sd_dir
        else:
            if seg_but > 0:
                sd_dict[('but0', 'd')] = sd_dict[('but1', 'd')] = 'out'
                sd_dir = (0, 2)
                sd_name = 's'
                sd_dict[('but0', sd_name)] = sd_dict[('but1', sd_name)] = 'nm'
                sd_dir_dict['but0'] = sd_dir_dict['but1'] = sd_dir
                prev_col = col_dict['but0']
                in_sd = 'nm'
            else:
                in_sd = 'out'

            if prev_col is not None and (col_dict['in'] - prev_col) % 2 == 1:
                sd_name = 'd' if sd_name == 's' else 's'
            sd_dict[('in', sd_name)] = in_sd
            if sd_name == 'd':
                sd_dir = (0, 2)
                sd_name = 's'
            else:
                sd_dir = (2, 0)
                sd_name = 'd'
            sd_dict[('in', sd_name)] = 'tail'
            sd_dir_dict['in'] = sd_dir

        if (col_dict['nen'] - col_dict['in']) % 2 == 1:
            sd_name = 'd' if sd_name == 's' else 's'
        sd_dict[('nen', sd_name)] = 'tail'
        if sd_name == 'd':
            sd_dir = (0, 2)
            sd_name = 's'
        else:
            sd_dir = (2, 0)
            sd_name = 'd'
        sd_dict[('nen', sd_name)] = 'foot'
        sd_dir_dict['nen'] = sd_dir

        if (col_dict['tail'] - col_dict['nen']) % 2 == 1:
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

    n_name_list = ['tail', 'nen', 'in', 'casc']
    p_name_list = ['pen', 'load']
    tran_list = [('load0', 'load'), ('load1', 'load'), ('pen0', 'pen'), ('pen1', 'pen'),
                 ('casc', 'casc'), ('but0', 'but'), ('but1', 'but'), ('in', 'in'),
                 ('nen', 'nen'), ('tail', 'tail')]
    diff_nets = {'pm0', 'pm1', 'out', 'nm'}
    gate_dict = {'load0': 'pclk0', 'load1': 'pclk1', 'pen0': 'pen0', 'pen1': 'pen1',
                 'casc': 'casc', 'in': 'in', 'nen': 'nen', 'tail': 'nclk',
                 'but0': 'casc<0>', 'but1': 'casc<1>'}

    def __init__(self, temp_db, lib_name, params, used_names, **kwargs):
        # type: (TemplateDB, str, Dict[str, Any], Set[str], **kwargs) -> None
        AnalogBase.__init__(self, temp_db, lib_name, params, used_names, **kwargs)
        self._row_lookup = None

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
        if name == 'but':
            name = 'casc'
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

        self._row_lookup = {}
        nw_list, nth_list, n_wires = [], [], []
        for idx, name in enumerate(self.n_name_list):
            if name in w_dict:
                nw_list.append(w_dict[name])
                nth_list.append(th_dict[name])
                n_wires.append(wire_names[name])
                self._row_lookup[name] = ('nch', idx)
        pw_list, pth_list, p_wires = [], [], []
        for idx, name in enumerate(self.p_name_list):
            if name in w_dict:
                pw_list.append(w_dict[name])
                pth_list.append(th_dict[name])
                p_wires.append(wire_names[name])
                self._row_lookup[name] = ('pch', idx)

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
                            net_suffix='',  # type: str
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
                if snet != 'VDD' and snet != 'VSS':
                    s_pre = net_prefix
                    s_suf = net_suffix
                else:
                    s_pre = s_suf = ''
                if dnet != 'VDD' and dnet != 'VSS':
                    d_pre = net_prefix
                    d_suf = net_suffix
                else:
                    d_pre = d_suf = ''

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
                if tran_name == 'but1':
                    # flip butterfly switch1 drain
                    dnetn, dnetp = dnetp, dnetn

                # draw transistors
                mp = self.draw_mos_conn(mos_type, row_idx, colp, seg, sdir, ddir,
                                        s_net=s_pre + snetp + s_suf, d_net=d_pre + dnetp + d_suf)
                mn = self.draw_mos_conn(mos_type, row_idx, coln, seg, sdir, ddir,
                                        s_net=s_pre + snetn + s_suf, d_net=d_pre + dnetn + d_suf)
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
                       invert=False,  # type: bool
                       fg_min=0,  # type: int
                       fg_dum=0,  # type: int
                       fg_sep_hm=0,  # type: int
                       idx_dict=None,  # type: Optional[Dict[str, int]]]
                       net_prefix='',  # type: str
                       net_suffix='',  # type: str
                       ):
        # type: (...) -> Tuple[Dict[str, Union[WireArray, List[WireArray]]], Dict[str, Any]]
        """Draw a differential amplifier.

        Parameters
        ----------
        col_idx : int
            the left-most transistor index.  0 is the left-most transistor.
        seg_dict : Dict[str, int]
            a dictionary containing number of segments per transistor type.
        invert : bool
            True to flip output sign.
        fg_min : int
            minimum number of total fingers.
        fg_dum : int
            minimum single-sided number of dummy fingers.
        fg_sep_hm : int
            number of fingers separating the load reset switches.
        idx_dict : Optional[Dict[str, int]]
            track index dictionary.
        net_prefix : str
            the prefix to append to net names.  Defaults to empty string.
        net_suffix : str
            the suffix to append to net names.  Defaults to empty string.

        Returns
        -------
        port_dict : Dict[str, Union[WireArray, List[WireArray]]]
            a dictionary from connection name to WireArray on horizontal routing layer.
        amp_info : Dict[str, Any]
            the amplifier layout information dictionary
        """
        if idx_dict is None:
            idx_dict = {}

        # get layout information
        amp_info = self.qdr_info.get_integ_amp_info(seg_dict, fg_min=fg_min, fg_dum=fg_dum,
                                                    fg_sep_hm=fg_sep_hm)
        seg_load = seg_dict.get('load', 0)
        seg_casc = seg_dict.get('casc', 0)
        seg_but = seg_dict.get('but', 0)
        fg_tot = amp_info['fg_tot']
        col_dict = amp_info['col_dict']
        sd_dict = amp_info['sd_dict']
        sd_dir_dict = amp_info['sd_dir_dict']

        ports = self._draw_integ_amp_mos(col_idx, fg_tot, seg_dict, col_dict, sd_dict, sd_dir_dict,
                                         net_prefix=net_prefix, net_suffix=net_suffix)

        # connect wires
        self.connect_to_substrate('ptap', ports['VSS'])
        # get TrackIDs
        foot_tid = self.get_wire_id('nch', 0, 'ds', wire_name='ntail')
        tail_tid = self.get_wire_id('nch', 1, 'ds', wire_name='ntail')
        outn_tid = self.get_wire_id('pch', 0, 'ds', wire_idx=0, wire_name='out')
        outp_tid = self.get_wire_id('pch', 0, 'ds', wire_idx=1, wire_name='out')
        inn_tid = self.get_wire_id('nch', 2, 'g', wire_idx=0, wire_name='in')
        inp_tid = self.get_wire_id('nch', 2, 'g', wire_idx=1, wire_name='in')
        mp_tid = self.get_wire_id('pch', 1, 'ds', wire_name='ptail')
        nclk_tid = self.get_wire_id('nch', 0, 'g', wire_idx=idx_dict.get('nclk', -1))
        nen_tid = self.get_wire_id('nch', 1, 'g', wire_idx=idx_dict.get('nen', -1))

        # connect intermediate nodes
        self.connect_to_tracks(ports['foot'], foot_tid, min_len_mode=0)
        self.connect_to_tracks(ports['tail'], tail_tid, min_len_mode=0)
        # connect gates
        hm_layer = outp_tid.layer_id
        nclk = self.connect_to_tracks(ports['nclk'], nclk_tid)
        nen = self.connect_to_tracks(ports['nen'], nen_tid)

        out_w = outp_tid.width
        outp_idx = outp_tid.base_index
        outn_idx = outn_tid.base_index
        if invert:
            outp_warrs, outn_warrs = ports['outn'], ports['outp']
        else:
            outp_warrs, outn_warrs = ports['outp'], ports['outn']
        outp, outn = self.connect_differential_tracks(outp_warrs, outn_warrs, hm_layer,
                                                      outp_idx, outn_idx, width=out_w)
        in_w = inp_tid.width
        inp_idx = inp_tid.base_index
        inn_idx = inn_tid.base_index
        inp, inn = self.connect_differential_tracks(ports['inp'], ports['inn'], hm_layer,
                                                    inp_idx, inn_idx, width=in_w)

        ans = dict(inp=inp, inn=inn, outp=outp, outn=outn, nen3=nen, biasp=nclk)

        # draw load connections
        if seg_load > 0:
            self.connect_to_substrate('ntap', ports['VDD'])
            for name in ('pm0p', 'pm0n', 'pm1p', 'pm1n'):
                self.connect_to_tracks(ports[name], mp_tid, min_len_mode=0)

            pen0_tid = self.get_wire_id('pch', 0, 'g', wire_idx=idx_dict.get('pen0', 0))
            pen1_tid = self.get_wire_id('pch', 0, 'g', wire_idx=idx_dict.get('pen1', 1))
            pclk0_tid = self.get_wire_id('pch', 1, 'g', wire_idx=idx_dict.get('pclk0', 0))
            pclk1_tid = self.get_wire_id('pch', 1, 'g', wire_idx=idx_dict.get('pclk1', 1))
            pen0, pen1 = self.connect_differential_tracks(ports['pen0'], ports['pen1'], hm_layer,
                                                          pen0_tid.base_index, pen1_tid.base_index,
                                                          width=pen0_tid.width)
            pclk0, pclk1 = self.connect_differential_tracks(ports['pclk0'], ports['pclk1'],
                                                            hm_layer,  pclk0_tid.base_index,
                                                            pclk1_tid.base_index,
                                                            width=pclk0_tid.width)
            ans['pen3'] = pen0
            ans['pen2'] = pen1
            ans['clkp'] = pclk1
            ans['clkn'] = pclk0

        # connect cascode if necessary
        if seg_casc > 0:
            nm_tid = self.get_wire_id('nch', 3, 'ds', wire_name='ptail')
            casc_tid = self.get_wire_id('nch', 3, 'g', wire_idx=idx_dict.get('casc', -1))
            self.connect_to_tracks(ports['nmp'], nm_tid)
            self.connect_to_tracks(ports['nmn'], nm_tid)
            casc = self.connect_to_tracks(ports['casc'], casc_tid)
            ans['casc'] = casc
        elif seg_but > 0:
            nm_tid = self.get_wire_id('nch', 3, 'ds', wire_name='ptail')
            cascp_idx = self.get_wire_id('nch', 3, 'g', wire_idx=-1).base_index
            cascn_idx = self.get_wire_id('nch', 3, 'g', wire_idx=-2).base_index
            self.connect_to_tracks(ports['nmp'], nm_tid)
            self.connect_to_tracks(ports['nmn'], nm_tid)

            casc0, casc1 = self.connect_differential_tracks(ports['casc<0>'], ports['casc<1>'],
                                                            hm_layer, cascp_idx, cascn_idx)
            ans['casc<0>'] = casc0
            ans['casc<1>'] = casc1

        return ans, amp_info
