# -*- coding: utf-8 -*-

"""This module defines various helper methods."""

from abs_templates_ec.analog_core.base import AnalogBase


def get_row_params(grid, row_heights, vss_tids, vdd_tids):
    """Returns parameters for fixing row heights."""
    if row_heights is None:
        bot_params = dict(
            min_height=0,
            vss_tid=None,
            vdd_tid=None,
        )
        top_params = bot_params.copy()
    else:
        hm_layer = AnalogBase.get_mos_conn_layer(grid.tech_info) + 1
        ytop = row_heights[0] + row_heights[1]
        tr_off = grid.find_next_track(hm_layer, ytop, half_track=True, mode=-1,
                                      unit_mode=True)
        if vss_tids is None:
            vss_bot_tid = vss_top_tid = None
        else:
            vss_bot_tid = vss_tids[0]
            vss_top_tid = (tr_off - vss_tids[1][0], vss_tids[1][1])
        if vdd_tids is None:
            vdd_bot_tid = vdd_top_tid = None
        else:
            vdd_bot_tid = vdd_tids[0]
            vdd_top_tid = (tr_off - vdd_tids[1][0], vdd_tids[1][1])

        bot_params = dict(
            min_height=row_heights[0],
            vss_tid=vss_bot_tid,
            vdd_tid=vdd_bot_tid,
        )
        top_params = dict(
            min_height=row_heights[1],
            vss_tid=vss_top_tid,
            vdd_tid=vdd_top_tid,
        )

        return bot_params, top_params
