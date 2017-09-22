# -*- coding: utf-8 -*-
########################################################################################################################
#
# Copyright (c) 2014, Regents of the University of California
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without modification, are permitted provided that the
# following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this list of conditions and the following
#   disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the
#    following disclaimer in the documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES,
# INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY,
# WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
########################################################################################################################


from __future__ import (absolute_import, division,
                        print_function, unicode_literals)
# noinspection PyUnresolvedReferences,PyCompatibility
from builtins import *
from future.utils import with_metaclass

import abc
from typing import TYPE_CHECKING, Optional, Dict, Any


from abs_templates_ec.analog_core import AnalogBase, AnalogBaseInfo

if TYPE_CHECKING:
    from bag.layout.routing import RoutingGrid


class SerdesRXBaseInfo(AnalogBaseInfo):
    """A class that calculates informations to assist in SerdesRXBase layout calculations.

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
        The default value is 15, which means we assume this AnalogBase is surrounded by empty spaces.
    min_fg_sep : int
        minimum number of separation fingers.
    fg_tot : Optional[int]
        number of fingers in a row.
    """

    def __init__(self, grid, lch, guard_ring_nf, top_layer=None, end_mode=15, min_fg_sep=0, fg_tot=None):
        # type: (RoutingGrid, float, int, Optional[int], int, int, Optional[int]) -> None
        super(SerdesRXBaseInfo, self).__init__(grid, lch, guard_ring_nf, top_layer=top_layer,
                                               end_mode=end_mode, min_fg_sep=min_fg_sep, fg_tot=fg_tot)

    def get_gm_info(self, fg_dict, flip_sd=False):
        # type: (Dict[str, int]) -> Dict[str, Any]
        """Return Gm layout information dictionary.

        Parameters
        ----------
        fg_dict : Dict[str, int]
            a dictionary containing number of fingers per transistor type.
            in addition to transistor types, you can specify the following entries:

            min :
                minimum number of total fingers.
            sep_min :
                minimum number of fingers that separates the differential sides.

        flip_sd : bool
            True to flip source/drain connections.

        Returns
        -------
        info : Dict[str, Any]
            the Gm stage layout information dictionary.
        """
        fg_cap = fg_dict.get('tail_cap', 0)
        if fg_cap % 2 != 0:
            raise ValueError('fg_tail_cap = %d must be multiples of two.' % fg_cap)

        fg_min = fg_dict.get('min', 0)
        fg_sep = max(fg_dict.get('sep_min', self.min_fg_sep), fg_dict.get('tail_ref', 0))

        valid_keys = ['casc', 'in', 'sw', 'en', 'tail']
        fg_single = max((fg_dict.get(key, 0) for key in valid_keys))
        fg_tot = fg_single * 2 + self._min_fg_sep

        if fg_tot < fg_min:
            # add dummies to get to fg_min
            # TODO: figure out when to even/not even depending on technology
            if (fg_min - fg_tot) % 4 != 0:
                # this code makes sure number of dummies is always even
                fg_min = fg_min + 4 - ((fg_min - fg_tot) % 4)
            nduml = ndumr = (fg_min - fg_tot) // 2
            fg_tot = fg_min
        else:
            nduml = ndumr = 0

        # determine output source/drain type.
        fg_but = fg_params.get('but', 0)
        if (fg_but // 2) % 2 == 1:
            out_type = 's'
        else:
            out_type = 'd'

        if flip_sd:
            out_type = 's' if out_type == 'd' else 's'

        results = dict(
            fg_tot=fg_tot,
            fg_max=fg_max,
            fg_sep=self._min_fg_sep,
            nduml=nduml,
            ndumr=ndumr,
            out_type=out_type,
        )

        # calculate column offsets.
        col_offsets = {}
        for name in ('but', 'casc', 'in', 'sw', 'en', 'tail'):
            fg = fg_params.get(name, 0)
            if fg > 0:
                col_offsets[name] = (fg_max - fg) + nduml

        results['col_offsets'] = col_offsets

        return results