# -*- coding: utf-8 -*-

from bag.core import BagProject,


def run_main(prj):
    lib_name = 'bag_serdes_testbenches_ec'
    cell_name = 'gm_char_dc'



if __name__ == '__main__':
    local_dict = locals()
    if 'bprj' not in local_dict:
        print('creating BAG project')
        bprj = BagProject()

    else:
        print('loading BAG project')
        bprj = local_dict['bprj']

    run_main(bprj)