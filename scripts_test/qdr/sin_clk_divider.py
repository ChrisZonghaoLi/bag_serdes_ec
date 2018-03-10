# -*- coding: utf-8 -*-

from typing import Dict, Any, Set

import yaml

from bag.core import BagProject
from bag.layout.routing import RoutingGrid, TrackManager
from bag.layout.template import TemplateDB

from serdes_ec.layout.qdr.base import HybridQDRBaseInfo, HybridQDRBase
from serdes_ec.layout.qdr.laygo import SinClkDivider


class IntegAmp(HybridQDRBase):
    """An integrating amplifier.

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
        HybridQDRBase.__init__(self, temp_db, lib_name, params, used_names, **kwargs)
        self._sch_params = None

    @property
    def sch_params(self):
        # type: () -> Dict[str, Any]
        return self._sch_params

    @classmethod
    def get_default_param_values(cls):
        # type: () -> Dict[str, Any]
        return dict(
            guard_ring_nf=0,
            top_layer=None,
            show_pins=True,
            options=None,
        )

    @classmethod
    def get_params_info(cls):
        # type: () -> Dict[str, str]
        return dict(
            lch='channel length, in meters.',
            ptap_w='NMOS substrate width, in meters/number of fins.',
            ntap_w='PMOS substrate width, in meters/number of fins.',
            w_dict='NMOS/PMOS width dictionary.',
            th_dict='NMOS/PMOS threshold flavor dictionary.',
            seg_dict='NMOS/PMOS number of segments dictionary.',
            fg_dum='Number of single-sided edge dummy fingers.',
            guard_ring_nf='Width of the guard ring, in number of fingers. 0 to disable.',
            top_layer='the top routing layer.',
            tr_widths='Track width dictionary.',
            tr_spaces='Track spacing dictionary.',
            show_pins='True to create pin labels.',
            options='AnalogBase options',
        )

    def draw_layout(self):
        lch = self.params['lch']
        ptap_w = self.params['ptap_w']
        ntap_w = self.params['ntap_w']
        w_dict = self.params['w_dict']
        th_dict = self.params['th_dict']
        seg_dict = self.params['seg_dict']
        fg_dum = self.params['fg_dum']
        guard_ring_nf = self.params['guard_ring_nf']
        top_layer = self.params['top_layer']
        tr_widths = self.params['tr_widths']
        tr_spaces = self.params['tr_spaces']
        show_pins = self.params['show_pins']
        options = self.params['options']

        if options is None:
            options = {}

        # get track manager and wire names
        tr_manager = TrackManager(self.grid, tr_widths, tr_spaces)
        wire_names = {
            'tail': dict(g=['clk', 'clk'], ds=['ntail']),
            'nen': dict(g=['en', 'en', 'en'], ds=['ntail']),
            'in': dict(g=['in', 'in'], ds=[]),
            'pen': dict(ds=['out', 'out'], g=['en', 'en', 'en']),
            'load': dict(ds=['ptail'], g=['clk', 'clk']),
        }

        # get total number of fingers
        qdr_info = HybridQDRBaseInfo(self.grid, lch, guard_ring_nf, top_layer=top_layer, **options)
        amp_info = qdr_info.get_integ_amp_info(seg_dict, fg_dum=fg_dum)
        fg_tot = amp_info['fg_tot']

        self.draw_rows(lch, fg_tot, ptap_w, ntap_w, w_dict, th_dict, tr_manager,
                       wire_names, top_layer=top_layer, **options)

        # draw amplifier
        ports, _ = self.draw_integ_amp(0, seg_dict, fg_dum=fg_dum)
        vss_warrs, vdd_warrs = self.fill_dummy()

        for name, warr in ports.items():
            self.add_pin(name, warr, show=show_pins)
        self.add_pin('VSS', vss_warrs, show=show_pins)
        self.add_pin('VDD', vdd_warrs, show=show_pins)


def make_tdb(prj, target_lib, specs):
    grid_specs = specs['routing_grid']
    layers = grid_specs['layers']
    widths = grid_specs['widths']
    spaces = grid_specs['spaces']
    bot_dir = grid_specs['bot_dir']
    width_override = grid_specs.get('width_override', None)

    routing_grid = RoutingGrid(prj.tech_info, layers, spaces, widths, bot_dir,
                               width_override=width_override)
    tdb = TemplateDB('template_libs.def', routing_grid, target_lib, use_cybagoa=True)
    return tdb


def generate(prj, specs, gen_sch=True, run_lvs=False):
    impl_lib = specs['impl_lib']
    impl_cell = specs['impl_cell']
    sch_lib = specs['sch_lib']
    sch_cell = specs['sch_cell']
    ana_params = specs['ana_params']
    params = specs['params']

    temp_db = make_tdb(prj, impl_lib, specs)

    name_list = [impl_cell]
    temp1 = temp_db.new_template(params=ana_params, temp_cls=IntegAmp, debug=False)

    params['row_layout_info'] = temp1.row_layout_info
    temp2 = temp_db.new_template(params=params, temp_cls=SinClkDivider, debug=False)

    temp_list = [temp2]
    print('creating layout')
    temp_db.batch_layout(prj, temp_list, name_list)
    print('layout done')

    if gen_sch:
        dsn = prj.create_design_module(lib_name=sch_lib, cell_name=sch_cell)
        dsn.design(**temp2.sch_params)
        print('creating schematics')
        dsn.implement_design(impl_lib, top_cell_name=impl_cell)
        print('schematic done.')

    if run_lvs:
        print('running lvs')
        lvs_passed, lvs_log = prj.run_lvs(impl_lib, impl_cell)
        print('LVS log: %s' % lvs_log)
        if lvs_passed:
            print('LVS passed!')
        else:
            print('LVS failed...')


if __name__ == '__main__':
    with open('specs_test/qdr/sin_clk_divider.yaml', 'r') as f:
        block_specs = yaml.load(f)

    local_dict = locals()
    if 'bprj' not in local_dict:
        print('creating BAG project')
        bprj = BagProject()

    else:
        print('loading BAG project')
        bprj = local_dict['bprj']

    generate(bprj, block_specs, gen_sch=True, run_lvs=True)
