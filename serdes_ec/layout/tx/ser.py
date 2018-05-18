# -*- coding: utf-8 -*-

"""This module defines layout generator for the TX serializer."""

from typing import TYPE_CHECKING, Dict, Set, Any

import yaml

from bag.layout.util import BBox
from bag.layout.routing import TrackID
from bag.layout.template import TemplateBase

if TYPE_CHECKING:
    from bag.layout.template import TemplateDB


class SerializerCoreStd(TemplateBase):
    """The serializer standard cell.

    Parameters
    ----------
    temp_db : :class:`bag.layout.template.TemplateDB`
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
        TemplateBase.__init__(self, temp_db, lib_name, params, used_names, **kwargs)
        self._sch_params = None

    @classmethod
    def get_params_info(cls):
        return dict(
            config_fname='Laygo configuration file.',
            show_pins='True to draw pin layous.',
        )

    @classmethod
    def get_default_param_values(cls):
        return dict(
            show_pins=True,
        )

    def create_bbox_from_laygo_port(self, port):
        return BBox(port['bbox'][0], port['bbox'][1], port['bbox'][2], port['bbox'][3],
                    self.grid.resolution, unit_mode=False)

    def draw_layout(self):
        config_fname = self.params['config_fname']
        show_pins = self.params['show_pins']

        with open(config_fname, 'r') as f:
            config_file_dict = yaml.load(f)

        inst_cell = config_file_dict['cells']['ser_2Nto1_16to1']
        self.add_instance_primitive(lib_name=inst_cell['lib_name'],
                                    cell_name=inst_cell['cell_name'], loc=(0, 0), orient='R0',
                                    unit_mode=True)

        port_names_not_export = []
        port_names_export = []
        for layer_export in range(3, 7, 2):
            for port_name, ports in inst_cell['ports'].items():
                for port in ports:
                    if port['layer'] == layer_export:
                        port_bbox = self.create_bbox_from_laygo_port(port)
                        port_track = self.grid.coord_to_nearest_track(layer_id=layer_export,
                                                                      coord=port_bbox.xc_unit,
                                                                      half_track=True,
                                                                      unit_mode=True)
                        port_warr = self.add_wires(layer_id=layer_export, track_idx=port_track,
                                                   width=1, lower=port_bbox.bottom_unit,
                                                   upper=port_bbox.top_unit, unit_mode=True)
                        self.add_pin(port_name, port_warr, show=show_pins)
                        port_names_export.append(port_name)
                    else:
                        port_names_not_export.append(port_name)

        for layer_export in range(2, 6, 2):
            for port_name, ports in inst_cell['ports'].items():
                for port in ports:
                    if port['layer'] == layer_export:
                        port_bbox = self.create_bbox_from_laygo_port(port)
                        port_track = self.grid.coord_to_nearest_track(layer_id=layer_export,
                                                                      coord=port_bbox.yc_unit,
                                                                      half_track=True,
                                                                      unit_mode=True)
                        port_warr = self.add_wires(layer_id=layer_export, track_idx=port_track,
                                                   width=2, lower=port_bbox.left_unit,
                                                   upper=port_bbox.right_unit, unit_mode=True)
                        self.add_pin(port_name, port_warr, show=show_pins)
                        port_names_export.append(port_name)
                    else:
                        port_names_not_export.append(port_name)

        cell_width = inst_cell['size_um'][0]
        cell_height = inst_cell['size_um'][1]

        self.array_box = BBox(left=0, bottom=0, right=cell_width, top=cell_height,
                              resolution=self.grid.resolution, unit_mode=False)
        self.set_size_from_bound_box(4, self.array_box, round_up=True)
        self.add_rect('M8', self.bound_box)
        self._sch_params = {}


class SerDriver(TemplateBase):
    """A differential NMOS passgate track-and-hold circuit with clock driver.

    This template is mainly used for ADC purposes.

    Parameters
    ----------
    temp_db : :class:`bag.layout.template.TemplateDB`
            the template database.
    lib_name : str
        the layout library name.
    params : dict[str, any]
        the parameter values.
    used_names : set[str]
        a set of already used cell names.
    kwargs : dict[str, any]
        dictionary of optional parameters.  See documentation of
        :class:`bag.layout.template.TemplateBase` for details.
    """

    def __init__(self, temp_db, lib_name, params, used_names, **kwargs):
        TemplateBase.__init__(self, temp_db, lib_name, params, used_names, **kwargs)
        self._sch_params = None
        self._clk_cen_coord = None

    @property
    def sch_params(self):
        return self._sch_params

    @property
    def clk_cen_coord(self):
        return self._clk_cen_coord

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
            mux_2to1_params='mux_2to1 parameters',
            tx_driver_params='tx_driver parameters',
            div_params='div parameters',
            ser_params='ser parameters',
            ESD_diode_params='ESD diode parameters',
            show_pins='True to show pins',
        )

    @classmethod
    def get_default_param_values(cls):
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
            show_pins=True,
        )

    def draw_layout(self, **kwargs):
        self._draw_layout_helper(**self.params)

    def _draw_layout_helper(self, mux_2to1_params, tx_driver_params, div_params,
                            ser_params, ESD_diode_params, show_pins, **kwargs):
        """Draw the layout of a transistor for characterization.
        Notes
        -------
        The number of fingers are for only half (or one side) of the tank.
        Total number should be 2x
        """

        # get resolution
        res = self.grid.resolution

        # mux_2to1
        mux_2to1_params['show_pins'] = True
        mux_master = self.new_template(params=mux_2to1_params, temp_cls=Inst_prim, debug=True)
        # get mux size
        mux_toplay = mux_master.size[0]
        mux_width = mux_master.bound_box.right_unit
        mux_height = mux_master.bound_box.top_unit
        w_loc_mux, h_loc_mux = self.grid.get_block_size(mux_toplay, unit_mode=True)

        # tx driver
        tx_driver_params['show_pins'] = True
        drv_master = self.new_template(params=tx_driver_params, temp_cls=CMLAmpPMOS, debug=True)
        # get driver size
        drv_toplay = drv_master.size[0]
        drv_width = drv_master.bound_box.right_unit
        drv_height = drv_master.bound_box.top_unit
        w_loc_drv, h_loc_drv = self.grid.get_block_size(drv_toplay, unit_mode=True)

        # divider
        div_params['show_pins'] = True
        div_master = self.new_template(params=div_params, temp_cls=DividerColumn, debug=True)
        # get div size
        div_toplay = div_master.size[0]
        div_width = div_master.bound_box.right_unit
        div_height = div_master.bound_box.top_unit
        w_loc_div, h_loc_div = self.grid.get_block_size(div_toplay, unit_mode=True)

        # serializer
        ser_params['show_pins'] = True
        ser_master = self.new_template(params=ser_params, temp_cls=ser_single, debug=True)
        # get ser size
        ser_toplay = ser_master.size[0]
        ser_width = ser_master.bound_box.right_unit
        ser_height = ser_master.bound_box.top_unit
        # ser_height = 22800
        w_loc_ser, h_loc_ser = self.grid.get_block_size(ser_toplay, unit_mode=True)

        # ESD
        ESD_diode_params['show_pins'] = True
        ESD_master = self.new_template(params=ESD_diode_params, temp_cls=Inst_prim, debug=True)
        # get ESD size
        ESD_toplay = ESD_master.size[0]
        ESD_width = ESD_master.bound_box.right_unit
        ESD_height = ESD_master.bound_box.top_unit
        w_loc_ESD, h_loc_ESD = self.grid.get_block_size(ESD_toplay, unit_mode=True)

        # get instances
        height = max(ser_height * 2, div_height, mux_height, drv_height, ESD_height * 2)
        # serializer
        coord_y = (height // 2 - ser_height) // h_loc_ser * h_loc_ser
        ser0_inst = self.add_instance(ser_master, inst_name='SER0', loc=(0, coord_y), orient='R0',
                                      unit_mode=True)
        coord_y = (height // 2 + ser_height) // h_loc_ser * h_loc_ser
        ser1_inst = self.add_instance(ser_master, inst_name='SER1', loc=(0, coord_y), orient='MX',
                                      unit_mode=True)
        # divider
        coord_x = (ser0_inst.bound_box.right_unit) // w_loc_drv * w_loc_drv
        coord_y = (height // 2 - div_height // 2) // h_loc_div * h_loc_div
        div_inst = self.add_instance(div_master, inst_name='DIV', loc=(coord_x, coord_y),
                                     orient='R0',
                                     unit_mode=True)
        coord_x = div_inst.bound_box.right_unit // w_loc_mux * w_loc_mux
        coord_y = (height // 2 - mux_height // 2) // h_loc_mux * h_loc_mux
        mux_inst = self.add_instance(mux_master, inst_name='MUX', loc=(coord_x, coord_y),
                                     orient='R0', unit_mode=True)
        coord_x = mux_inst.bound_box.right_unit // w_loc_drv * w_loc_drv
        coord_y = (height // 2 - drv_height // 2) // h_loc_drv * h_loc_drv
        drv_inst = self.add_instance(drv_master, inst_name='DRV', loc=(coord_x, coord_y),
                                     orient='R0', unit_mode=True)
        coord_x = drv_inst.bound_box.right_unit // w_loc_ESD * w_loc_ESD + 1 * w_loc_ESD  # TODO: some magic number
        coord_y = height // 2 // h_loc_ESD * h_loc_ESD
        ESD_inst1 = self.add_instance(ESD_master, inst_name='ESD1', loc=(coord_x, coord_y),
                                      orient='R0', unit_mode=True)
        ESD_inst0 = self.add_instance(ESD_master, inst_name='ESD0', loc=(coord_x, coord_y),
                                      orient='MX', unit_mode=True)

        # # connect different cells
        # max_height = max(ser_height*2, div_height*2, mux_height, drv_height, ESD_height*2)
        #
        # # a) connect serializer
        # ser0_clkp = ser0_inst.get_all_port_pins('CLK')[0]
        # ser0_clkn = ser0_inst.get_all_port_pins('CLKB')[0]
        # ser1_clkp = ser1_inst.get_all_port_pins('CLK')[0]
        # ser1_clkn = ser1_inst.get_all_port_pins('CLKB')[0]
        #
        # # get new wires
        # clk_width_ntr = 2
        # vdd_width_ntr = 3
        # data_width_ntr = 2
        # ibias_width_ntr = 3
        # power_width_ntr = 3
        #
        # coord_x_left = ser0_clkp.get_bbox_array(self.grid).left_unit
        # coord_x_right = ser0_clkp.get_bbox_array(self.grid).right_unit
        # idx = self.grid.coord_to_nearest_track(ser0_clkp.layer_id, ser0_clkp.get_bbox_array(self.grid).yc_unit,
        #                                        half_track=True, unit_mode=True)
        # ser0_clkp = self.add_wires(ser0_clkp.layer_id, idx, lower=coord_x_left, upper=coord_x_right,
        #                            unit_mode=True, width=2)
        # idx = self.grid.coord_to_nearest_track(ser0_clkn.layer_id, ser0_clkn.get_bbox_array(self.grid).yc_unit,
        #                                        half_track=True, unit_mode=True)
        # ser0_clkn = self.add_wires(ser0_clkn.layer_id, idx, lower=coord_x_left, upper=coord_x_right,
        #                            unit_mode=True, width=2)
        #
        # idx = self.grid.coord_to_nearest_track(ser1_clkp.layer_id, ser1_clkp.get_bbox_array(self.grid).yc_unit,
        #                                        half_track=True, unit_mode=True)
        # ser1_clkp = self.add_wires(ser1_clkp.layer_id, idx, lower=coord_x_left, upper=coord_x_right,
        #                            unit_mode=True, width=2)
        # idx = self.grid.coord_to_nearest_track(ser1_clkn.layer_id, ser1_clkn.get_bbox_array(self.grid).yc_unit,
        #                                        half_track=True, unit_mode=True)
        # ser1_clkn = self.add_wires(ser1_clkn.layer_id, idx, lower=coord_x_left, upper=coord_x_right,
        #                            unit_mode=True, width=2)
        #
        # idx = self.grid.coord_to_nearest_track(ser0_clkp.layer_id+1, ser0_clkp.middle)
        # clkp_div, clkn_div = self.connect_differential_tracks([ser0_clkp, ser1_clkp], [ser0_clkn, ser1_clkn],
        #                                                       ser0_clkp.layer_id+1, idx-clk_width_ntr//2,
        #                                                       idx+clk_width_ntr//2, width=clk_width_ntr)
        #
        # # conect supply
        # ser0_vdd= ser0_inst.get_all_port_pins('VDD')
        # ser0_vss= ser0_inst.get_all_port_pins('VSS')
        # ser1_vdd = ser1_inst.get_all_port_pins('VDD')
        # ser1_vss = ser1_inst.get_all_port_pins('VSS')
        #
        # ser_vdd0 = []
        # ser_vdd1 = []
        # for i in range(len(ser0_vdd)):
        #     if ser0_vdd[i].get_bbox_array(self.grid).xc_unit <= ser0_inst.bound_box.xc_unit:
        #         ser_vdd0.append(self.connect_wires([ser0_vdd[i], ser1_vdd[i]])[0])
        #     else:
        #         ser_vdd1.append(self.connect_wires([ser0_vdd[i], ser1_vdd[i]])[0])
        #
        # ser_vss0 = []
        # ser_vss1 = []
        # for i in range(len(ser0_vss)):
        #     if ser0_vss[i].get_bbox_array(self.grid).xc_unit <= ser0_inst.bound_box.xc_unit:
        #         ser_vss0.append(self.connect_wires([ser0_vss[i], ser1_vss[i]])[0])
        #     else:
        #         ser_vss1.append(self.connect_wires([ser0_vss[i], ser1_vss[i]])[0])
        #
        # ser_vdd = []
        # ser_vss = []
        # # bottom
        # idx = self.grid.coord_to_nearest_track(ser_vdd0[0].layer_id+1, 0, unit_mode=True)
        # sp_ntr = self.grid.get_num_space_tracks(ser_vdd0[0].layer_id+1, power_width_ntr)
        # tid = TrackID(ser_vdd0[0].layer_id+1, idx+power_width_ntr, power_width_ntr)
        # ser_vdd0_x = self.connect_to_tracks(ser_vdd0, tid)
        # ser_vdd1_x = self.connect_to_tracks(ser_vdd1, tid)
        # ser_vdd0_x = self.draw_wire_stack(ser_vdd0_x, ser_vdd0_x.layer_id+2)[-1]
        # ser_vdd1_x = self.draw_wire_stack(ser_vdd1_x, ser_vdd1_x.layer_id+2)[-1]
        # ser_vdd.append(self.connect_wires([ser_vdd0_x, ser_vdd1_x]))
        #
        # tid = TrackID(ser_vdd0[0].layer_id+1, idx+power_width_ntr*2+sp_ntr, power_width_ntr)
        # ser_vss0_x = self.connect_to_tracks(ser_vss0, tid)
        # ser_vss1_x = self.connect_to_tracks(ser_vss1, tid)
        # ser_vss0_x = self.draw_wire_stack(ser_vss0_x, ser_vss0_x.layer_id + 2)[-1]
        # ser_vss1_x = self.draw_wire_stack(ser_vss1_x, ser_vss1_x.layer_id + 2)[-1]
        # ser_vss.append(self.connect_wires([ser_vss0_x, ser_vss1_x]))
        # # middle
        # idx = self.grid.coord_to_nearest_track(ser_vdd0[0].layer_id + 1, ser_height, unit_mode=True)
        # sp_ntr = self.grid.get_num_space_tracks(ser_vdd0[0].layer_id + 1, power_width_ntr)
        # tid = TrackID(ser_vdd0[0].layer_id + 1, idx - power_width_ntr - sp_ntr//2, power_width_ntr)
        # ser_vdd0_x = self.connect_to_tracks(ser_vdd0, tid)
        # ser_vdd1_x = self.connect_to_tracks(ser_vdd1, tid)
        # ser_vdd0_x = self.draw_wire_stack(ser_vdd0_x, ser_vdd0_x.layer_id + 2)[-1]
        # ser_vdd1_x = self.draw_wire_stack(ser_vdd1_x, ser_vdd1_x.layer_id + 2)[-1]
        # ser_vdd.append(self.connect_wires([ser_vdd0_x, ser_vdd1_x]))
        #
        # tid = TrackID(ser_vdd0[0].layer_id + 1, idx + power_width_ntr + sp_ntr, power_width_ntr)
        # ser_vss0_x = self.connect_to_tracks(ser_vss0, tid)
        # ser_vss1_x = self.connect_to_tracks(ser_vss1, tid)
        # ser_vss0_x = self.draw_wire_stack(ser_vss0_x, ser_vss0_x.layer_id + 2)[-1]
        # ser_vss1_x = self.draw_wire_stack(ser_vss1_x, ser_vss1_x.layer_id + 2)[-1]
        # ser_vss.append(self.connect_wires([ser_vss0_x, ser_vss1_x]))
        #
        # # upper
        # idx = self.grid.coord_to_nearest_track(ser_vdd0[0].layer_id + 1, ser_height*2, unit_mode=True)
        # sp_ntr = self.grid.get_num_space_tracks(ser_vdd0[0].layer_id + 1, power_width_ntr)
        # tid = TrackID(ser_vdd0[0].layer_id + 1, idx - power_width_ntr * 2 - sp_ntr, power_width_ntr)
        # ser_vdd0_x = self.connect_to_tracks(ser_vdd0, tid)
        # ser_vdd1_x = self.connect_to_tracks(ser_vdd1, tid)
        # ser_vdd0_x = self.draw_wire_stack(ser_vdd0_x, ser_vdd0_x.layer_id + 2)[-1]
        # ser_vdd1_x = self.draw_wire_stack(ser_vdd1_x, ser_vdd1_x.layer_id + 2)[-1]
        # ser_vdd.append(self.connect_wires([ser_vdd0_x, ser_vdd1_x]))
        #
        # tid = TrackID(ser_vdd0[0].layer_id + 1, idx - power_width_ntr, power_width_ntr)
        # ser_vss0_x = self.connect_to_tracks(ser_vss0, tid)
        # ser_vss1_x = self.connect_to_tracks(ser_vss1, tid)
        # ser_vss0_x = self.draw_wire_stack(ser_vss0_x, ser_vss0_x.layer_id + 2)[-1]
        # ser_vss1_x = self.draw_wire_stack(ser_vss1_x, ser_vss1_x.layer_id + 2)[-1]
        # ser_vss.append(self.connect_wires([ser_vss0_x, ser_vss1_x]))
        #
        # # try to end at M6
        # # rst
        # ser_rst0 = ser0_inst.get_all_port_pins('RST:')
        # ser_rst1 = ser1_inst.get_all_port_pins('RST:')
        # ser_rst = []
        # idx = self.grid.coord_to_nearest_track(ser_rst0[0].layer_id+1, ser_rst0[0].middle)
        # tid = TrackID(ser_rst0[0].layer_id+1, idx)
        # ser_rst.append(self.connect_to_tracks(ser_rst0[0], tid, min_len_mode=0))
        # idx = self.grid.coord_to_nearest_track(ser_rst0[1].layer_id + 1, ser_rst0[1].middle)
        # tid = TrackID(ser_rst0[1].layer_id + 1, idx)
        # ser_rst.append(self.connect_to_tracks(ser_rst0[1], tid, min_len_mode=0))
        # idx = self.grid.coord_to_nearest_track(ser_rst1[0].layer_id + 1, ser_rst1[0].middle)
        # tid = TrackID(ser_rst1[0].layer_id + 1, idx)
        # ser_rst.append(self.connect_to_tracks(ser_rst1[0], tid, min_len_mode=0))
        # idx = self.grid.coord_to_nearest_track(ser_rst1[1].layer_id + 1, ser_rst1[1].middle)
        # tid = TrackID(ser_rst1[1].layer_id + 1, idx)
        # ser_rst.append(self.connect_to_tracks(ser_rst1[1], tid, min_len_mode=0))
        #
        # idx = self.grid.coord_to_nearest_track(ser_rst[0].layer_id+1, ser_rst[0].middle)
        # tid = TrackID(ser_rst[0].layer_id+1, idx, width=2)  # TODO: magic number
        # ser_rst = self.connect_to_tracks(ser_rst, tid, track_lower=0, track_upper=ser_height*2, unit_mode=True)
        #
        #
        # # connect output divclk
        # ser0_divclk = ser0_inst.get_all_port_pins('divclk')[0]
        # ser1_divclk = ser1_inst.get_all_port_pins('divclk')[0]
        #
        # idx = self.grid.coord_to_nearest_track(ser0_divclk.layer_id+1, ser0_divclk.middle)
        # tid = TrackID(ser0_divclk.layer_id+1, idx+4)        # TODO: magic number
        # ser0_divclk = self.connect_to_tracks(ser0_divclk, tid, track_lower=0)
        #
        # idx = self.grid.coord_to_nearest_track(ser1_divclk.layer_id + 1, ser1_divclk.middle)
        # tid = TrackID(ser1_divclk.layer_id + 1, idx-4)      # TODO: magic number
        # ser1_divclk = self.connect_to_tracks(ser1_divclk, tid, track_lower=0)
        #
        # # b) connect divider
        # # connect divider to new clkp_div/clkn_div
        # clk_i = div_inst.get_all_port_pins('en<3>')[0]
        # clk_q = div_inst.get_all_port_pins('en<2>')[0]
        # clk_ib = div_inst.get_all_port_pins('en<1>')[0]
        # clk_qb = div_inst.get_all_port_pins('en<0>')[0]
        #
        # clk_width = self.grid.get_track_width(clk_i.layer_id, clk_width_ntr, unit_mode=True)
        # clk_i = self.add_wires(clk_i.layer_id, clk_i.track_id.base_index, width=clk_i.width,
        #                        lower=clk_i.get_bbox_array(self.grid).left_unit,
        #                        upper=clk_i.get_bbox_array(self.grid).left_unit+clk_width*8,
        #                        unit_mode=True)      # TODO: magic number
        # clk_ib = self.add_wires(clk_ib.layer_id, clk_ib.track_id.base_index, width=clk_ib.width,
        #                        lower=clk_ib.get_bbox_array(self.grid).left_unit,
        #                        upper=clk_ib.get_bbox_array(self.grid).left_unit + clk_width * 8,
        #                        unit_mode=True)
        # # connect to M6
        # q_div = self.draw_wire_stack(clk_i, top_layid=clk_i.layer_id+2)[0]
        # qb_div = self.draw_wire_stack(clk_ib, top_layid=clk_ib.layer_id+2)[0]
        # clkp_div, clkn_div = self.connect_differential_tracks(clkp_div, clkn_div, clkp_div.layer_id+1,
        #                                                       q_div.track_id.base_index, qb_div.track_id.base_index,
        #                                                       width=clk_width_ntr, track_upper=q_div.upper_unit,
        #                                                       unit_mode=True)
        #
        # # connect scan s and en
        # scan_div_3 = div_inst.get_all_port_pins('scan_div<3>')[0]
        # scan_div_2 = div_inst.get_all_port_pins('scan_div<2>')[0]
        # div_en = div_inst.get_all_port_pins('en_div')
        #
        # idx = self.grid.coord_to_nearest_track(div_en[0].layer_id+1, ser_width, unit_mode=True)
        # # tid = TrackID(div_scan_s.layer_id+1, idx-1)
        # # div_scan = self.connect_to_tracks([div_scan_s, dum_scan_s], tid,
        # #                                     track_lower=0,
        # #                                     # track_lower=div_inst.bound_box.bottom_unit,
        # #                                     track_upper=max_height,
        # #                                     unit_mode=True)
        # tid = TrackID(div_en[0].layer_id+1, idx-2)
        # div_en = self.connect_to_tracks(div_en, tid,
        #                             # track_lower=div_inst.bound_box.bottom_unit,
        #                             track_lower=0,
        #                             track_upper=height,
        #                             unit_mode=True)
        # # # put VSS/VDD on M7
        # div_vss = div_inst.get_all_port_pins('VSS')
        # div_vdd = div_inst.get_all_port_pins('VDD')
        # #
        # # idx0 = self.grid.coord_to_nearest_track(div_vss.layer_id+1, div_vss.get_bbox_array(self.grid).left_unit,
        # #                                         unit_mode=True)
        # # idx1 = self.grid.coord_to_nearest_track(div_vss.layer_id + 1, div_vss.get_bbox_array(self.grid).xc_unit,
        # #                                         unit_mode=True)
        # # idx2 = self.grid.coord_to_nearest_track(div_vss.layer_id + 1, div_vss.get_bbox_array(self.grid).right_unit,
        # #                                         unit_mode=True)
        # # idx_warr = [idx0, idx1, idx2]
        # # div_vss_warr = []
        # # div_vdd_warr = []
        # # for idx in idx_warr:
        # #     tid = TrackID(div_vss.layer_id+1, idx, width=vdd_width_ntr)
        # #     div_vss_warr.append(self.connect_to_tracks(div_vss, tid, min_len_mode=True))
        # #     div_vss_warr.append(self.connect_to_tracks(dum_vss, tid, min_len_mode=True))
        # #     div_vdd_warr.append(self.connect_to_tracks(div_vdd, tid, min_len_mode=True))
        # #     div_vdd_warr.append(self.connect_to_tracks(dum_vdd, tid, min_len_mode=True))
        # #
        # # div_vss_warr_x = []
        # # div_vdd_warr_x = []
        # # for div_vss in div_vss_warr:
        # #     div_vss_warr_x.append(self.draw_wire_stack(div_vss, div_vss.layer_id+2)[0])
        # # for div_vdd in div_vdd_warr:
        # #     div_vdd_warr_x.append(self.draw_wire_stack(div_vdd, div_vdd.layer_id+2)[0])
        #
        # # c) connect mux
        # # connect clocks
        # # get div clkp/clkn
        # div_clkp_0 = div_inst.get_all_port_pins('clkp')[0]
        # div_clkn_0 = div_inst.get_all_port_pins('clkn')[0]
        # div_clkp_1 = div_inst.get_all_port_pins('clkp')[1]
        # div_clkn_1 = div_inst.get_all_port_pins('clkn')[1]
        # div_clkp_2 = div_inst.get_all_port_pins('clkp')[2]
        # div_clkn_2 = div_inst.get_all_port_pins('clkn')[2]
        #
        # # get mux clkp/clkn
        # mux_clkp = mux_inst.get_all_port_pins('clkp')[0]
        # mux_clkn = mux_inst.get_all_port_pins('clkn')[0]
        # mux_clkp = self.extend_wires(mux_clkp, lower=0)[0]
        # mux_clkn = self.extend_wires(mux_clkn, lower=0)[0]
        #
        # # connect div_clkp/clkn to M5
        # idx = self.grid.coord_to_nearest_track(div_clkp_0.layer_id+1, div_clkp_0.upper)
        # div_clkp, div_clkn = self.connect_differential_tracks([div_clkp_0, div_clkp_1, div_clkp_2],
        #                                                       [div_clkn_0, div_clkn_1, div_clkn_2],
        #                                                       div_clkp_2.layer_id+1, idx+clk_width_ntr,
        #                                                       idx+clk_width_ntr*2,
        #                                                       width=clk_width_ntr)
        # idx = self.grid.coord_to_nearest_track(div_clkp.layer_id+1, div_clkp.middle)
        # self.connect_differential_tracks([div_clkp, mux_clkp], [div_clkn, mux_clkn],
        #                                  div_clkp.layer_id+1,
        #                                  idx-clk_width_ntr,
        #                                  idx+clk_width_ntr,
        #                                  width=clk_width_ntr)
        # # connect data
        # ser0_data = ser0_inst.get_all_port_pins('out')[0]
        # ser1_data = ser1_inst.get_all_port_pins('out')[0]
        #
        # idx = self.grid.coord_to_nearest_track(ser0_data.layer_id, ser0_data.get_bbox_array(self.grid).yc_unit,
        #                                        half_track=True, unit_mode=True)
        # ser0_data = self.add_wires(ser0_data.layer_id, idx, width=data_width_ntr,
        #                            lower=ser0_data.get_bbox_array(self.grid).left_unit,
        #                            upper=ser0_data.get_bbox_array(self.grid).right_unit, unit_mode=True)
        # idx = self.grid.coord_to_nearest_track(ser1_data.layer_id, ser1_data.get_bbox_array(self.grid).yc_unit,
        #                                        half_track=True, unit_mode=True)
        # ser1_data = self.add_wires(ser1_data.layer_id, idx, width=data_width_ntr,
        #                            lower=ser1_data.get_bbox_array(self.grid).left_unit,
        #                            upper=ser1_data.get_bbox_array(self.grid).right_unit,
        #                            unit_mode=True)
        #
        # data0 = mux_inst.get_all_port_pins('data1')[0]   # swap data0/data1 !!
        # data1 = mux_inst.get_all_port_pins('data0')[0]   # in MUX data0 is first in time
        # idx = self.grid.coord_to_nearest_track(data0.layer_id+1, data0.lower)
        # tid = TrackID(data0.layer_id+1, idx, width=data_width_ntr)
        # data0 = self.connect_to_tracks([data0, ser0_data], tid)
        # data1 = self.connect_to_tracks([data1, ser1_data], tid)
        #
        # # d) connect driver
        # # connect data
        # mux_outp = mux_inst.get_all_port_pins('outp')[0]
        # mux_outn = mux_inst.get_all_port_pins('outn')[0]
        # drv_inp = drv_inst.get_all_port_pins('inp')[0]
        # drv_inn = drv_inst.get_all_port_pins('inn')[0]
        #
        # idx = self.grid.coord_to_nearest_track(mux_outp.layer_id+1, mux_inst.bound_box.right_unit, unit_mode=True)
        # tid = TrackID(mux_outp.layer_id+1, idx)
        # mux_outp = self.connect_to_tracks([mux_outp, drv_inp], tid)
        # mux_outn = self.connect_to_tracks([mux_outn, drv_inn], tid)
        #
        # # ibias
        # drv_ibias = drv_inst.get_all_port_pins('ibias')[0]
        # idx = self.grid.coord_to_nearest_track(drv_ibias.layer_id+1, drv_inst.bound_box.right_unit, unit_mode=True)
        # tid = TrackID(drv_ibias.layer_id+1, idx, width=ibias_width_ntr)
        # drv_ibias = self.connect_to_tracks(drv_ibias, tid, track_lower=drv_inst.bound_box.bottom_unit,
        #                                    track_upper=drv_inst.bound_box.top_unit,
        #                                    unit_mode=True)
        #
        # # outp/outn
        # drv_outp = drv_inst.get_all_port_pins('outp')
        # drv_outn = drv_inst.get_all_port_pins('outn')
        # rf_io0 = ESD_inst0.get_all_port_pins('RF_IO', layer=drv_outp[0].layer_id)[0]
        # rf_io1 = ESD_inst1.get_all_port_pins('RF_IO', layer=drv_outn[0].layer_id)[0]
        #
        # idx0 = self.grid.coord_to_nearest_track(drv_outp[0].layer_id+1, drv_outp[0].middle)
        # tid0 = TrackID(drv_outp[0].layer_id+1, idx0)
        # idx1 = self.grid.coord_to_nearest_track(drv_outn[0].layer_id+1, drv_outn[0].middle)
        # tid1 = TrackID(drv_outn[0].layer_id+1, idx1)
        #
        # drv_outp.append(rf_io1)
        # drv_outn.append(rf_io0)
        # outp = self.connect_to_tracks(drv_outp, tid0,
        #                               track_upper=ESD_inst1.bound_box.right_unit,
        #                               unit_mode=True)
        # outn = self.connect_to_tracks(drv_outn, tid1,
        #                               track_upper=ESD_inst0.bound_box.right_unit,
        #                               unit_mode=True)
        #
        # # add pins
        # # data pins for serializer
        # ser_ratio = 16
        # for i in range(ser_ratio):
        #     self.reexport(ser1_inst.get_port('in<%d>' % i), 'data_tx<%d>' % (2 * i + 1), show=show_pins)
        #     self.reexport(ser0_inst.get_port('in<%d>' % i), 'data_tx<%d>' % (2 * i + 0), show=show_pins)
        # # vdd/vss
        # for vdd in ser_vdd:
        #     self.add_pin('VDDA', vdd, label='VDDA:', show=show_pins)
        # for vss in ser_vss:
        #     self.add_pin('VSS', vss, label='VSS:', show=show_pins)
        # self.add_pin('ser_reset', ser_rst, show=show_pins)
        # # ser_clk
        # self.add_pin('clock_tx_div', ser0_divclk, show=show_pins)
        # self.add_pin('ser1_divclk', ser1_divclk, show=show_pins)
        #
        # # divider
        # self.add_pin('div_en', div_en, show=show_pins)
        # # self.add_pin('div_scan_s', div_scan, show=show_pins)
        # self.add_pin('clkp_div', clkp_div, show=show_pins)
        # self.add_pin('clkn_div', clkn_div, show=show_pins)
        # for vdd in div_vdd:
        #     self.add_pin('VDDA', vdd, label='VDDA:', show=show_pins)
        # for vss in div_vss:
        #     self.add_pin('VSS', vss, label='VSS:', show=show_pins)
        #
        # # TODO: use label for now, hope it will work will power fill
        # self.add_pin('VSS', scan_div_3, label='VSS:', show=show_pins)
        # self.add_pin('VSS', scan_div_2, label='VSS:', show=show_pins)
        #
        # # mux
        # self.add_pin('clkp', mux_clkp, show=show_pins)
        # self.add_pin('clkn', mux_clkn, show=show_pins)
        # self.add_pin('data0', data0, show=show_pins)
        # self.add_pin('data1', data1, show=show_pins)
        # self.reexport(mux_inst.get_port('VDD'), 'VDDA', label='VDDA:', show=show_pins)
        # self.reexport(mux_inst.get_port('VSS'), 'VSS', label='VSS:', show=show_pins)
        #
        # # driver
        # self.add_pin('mux_outp', mux_outp, show=show_pins)
        # self.add_pin('mux_outn', mux_outn, show=show_pins)
        # self.add_pin('drv_ibias', drv_ibias, show=show_pins)
        # self.add_pin('outp', outp, show=show_pins)
        # self.add_pin('outn', outn, show=show_pins)
        # self.reexport(drv_inst.get_port('VDD'), 'VDDA', label='VDDA:', show=show_pins)
        # self.reexport(drv_inst.get_port('VSS'), 'VSS', label='VSS:', show=show_pins)
        #
        # # ESD
        # self.reexport(ESD_inst0.get_port('VDD_ESD'), 'VDDA', label='VDDA:', show=show_pins)
        # self.reexport(ESD_inst1.get_port('VDD_ESD'), 'VDDA', label='VDDA:', show=show_pins)
        # self.reexport(ESD_inst0.get_port('VSS_ESD'), 'VSS', label='VSS:', show=show_pins)
        # self.reexport(ESD_inst1.get_port('VSS_ESD'), 'VSS', label='VSS:', show=show_pins)
        #
        # # get size
        # width = ser_width+div_width+mux_width+drv_width+ESD_width+1*w_loc_ESD  # TODO: magic number
        # # get size and array box
        # top_layer = max(ser_toplay, div_toplay, mux_toplay, drv_toplay, ESD_toplay) + 1
        # w_pitch, h_pitch = self.grid.get_size_pitch(top_layer, unit_mode=True)
        #
        # # get block size rounded by top 2 layers pitch
        # blk_w = -(-1 * width // w_pitch) * w_pitch
        # blk_h = -(-1 * height // h_pitch) * h_pitch
        #
        # # get block size based on top 2 layers
        # blk_w_tr = blk_w // w_pitch
        # blk_h_tr = blk_h // h_pitch
        #
        # # size and array box
        # self.size = top_layer, blk_w_tr, blk_h_tr
        # self.array_box = BBox(0, 0, blk_w, blk_h, res, unit_mode=True)
        #
        # # return schematic parameters
        # div_sch_params = div_master.sch_params
        # ser_sch_params = ser_master.sch_params
        # self._sch_params = dict(
        #     div_sch_params=div_sch_params,
        #     ser_sch_params=ser_sch_params,
        # )
        #
        # self._clk_cen_coord = (mux_clkp.get_bbox_array(self.grid).xc_unit +
        #                       mux_clkn.get_bbox_array(self.grid).xc_unit) // 2

    def draw_wire_stack(self, wire, top_layid, x0=None, y0=None, x1=None, y1=None, x_mode=-1,
                        y_mode=-1,
                        half_track=True, unit_mode=True, tr_list=None, max_mode=True,
                        min_len_mode=None):
        """
        create WireArray from bot_layid to top_layid-1 within the given coordinates
        TO DO: Important function for me!!
        """
        # get resolution
        res = self.grid.resolution
        # get wire layer
        bot_layid = wire.layer_id

        if tr_list is not None:
            if len(tr_list) != top_layid - bot_layid:
                raise ValueError(
                    'If given tr_list, its length should same as layers(top_layid-bot_layid)')

        # get coordinate
        if x0 is None:
            x0 = wire.get_bbox_array(self.grid).left_unit
        else:
            if unit_mode is False:
                x0 = round(x0 / res)
        if x1 is None:
            x1 = wire.get_bbox_array(self.grid).right_unit
        else:
            if unit_mode is False:
                x1 = round(x1 / res)
        if y0 is None:
            y0 = wire.get_bbox_array(self.grid).bottom_unit
        else:
            if unit_mode is False:
                y0 = round(y0 / res)
        if y1 is None:
            y1 = wire.get_bbox_array(self.grid).top_unit
        else:
            if unit_mode is False:
                y1 = round(y1 / res)

        if x1 <= x0:
            print('\nSwap x0 with x1...')
            x0, x1 = x1, x0
        if y1 <= y0:
            print('\nSwap y0 with y1...')
            y0, y1 = y1, y0

        if bot_layid >= top_layid:
            raise ValueError("Need bot_layid smaller than top_layid.")

        x_cen = (x0 + x1) // 2
        x_width = x1 - x0
        y_cen = (y0 + y1) // 2
        y_width = y1 - y0

        wire_arr = [wire]
        for i in range(bot_layid, top_layid):
            if self.grid.get_direction(i + 1) == 'y':
                tr = self.grid.coord_to_nearest_track(i + 1, x_cen, half_track=half_track,
                                                      unit_mode=True)
                tr_w = self.grid.get_track_width_inverse(i + 1, x_width, mode=x_mode,
                                                         unit_mode=True)
                if tr_w is None:
                    tr_w = 1
                # could specify tr from outside and choose the larger one
                if tr_list is not None:
                    if tr_list[i - bot_layid] is not None:
                        if max_mode is True:
                            tr_w = max(tr_w, tr_list[i - bot_layid])
                        else:
                            tr_w = tr_list[i - bot_layid]
                tr_tid = TrackID(i + 1, tr, width=tr_w)
                wire_n = self.connect_to_tracks(wire_arr[-1], tr_tid, track_lower=y0,
                                                track_upper=y1,
                                                unit_mode=True, min_len_mode=min_len_mode)
            else:
                tr = self.grid.coord_to_nearest_track(i + 1, y_cen, half_track=half_track,
                                                      unit_mode=True)
                tr_w = self.grid.get_track_width_inverse(i + 1, y_width, mode=y_mode,
                                                         unit_mode=True)
                if tr_w is None:
                    tr_w = 1
                # could specify tr from outside and choose the larger one
                if tr_list is not None:
                    if tr_list[i - bot_layid] is not None:
                        if max_mode is True:
                            tr_w = max(tr_w, tr_list[i - bot_layid])
                        else:
                            tr_w = tr_list[i - bot_layid]
                tr_tid = TrackID(i + 1, tr, width=tr_w)
                wire_n = self.connect_to_tracks(wire_arr[-1], tr_tid, track_lower=x0,
                                                track_upper=x1,
                                                unit_mode=True, min_len_mode=min_len_mode)
            wire_arr.append(wire_n)

        return wire_arr
