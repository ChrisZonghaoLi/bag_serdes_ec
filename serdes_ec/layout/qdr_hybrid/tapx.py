# -*- coding: utf-8 -*-

from typing import TYPE_CHECKING, Dict, Any, Set, List, Union

"""This module defines classes needed to build the Hybrid-QDR FFE/DFE summer."""


from itertools import chain

from bag.layout.util import BBox
from bag.layout.routing import TrackManager, TrackID
from bag.layout.template import TemplateBase

from .base import HybridQDRBaseInfo, HybridQDRBase
from .laygo import SinClkDivider
from .amp import IntegAmp


if TYPE_CHECKING:
    from bag.layout.template import TemplateDB


