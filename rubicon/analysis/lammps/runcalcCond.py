# coding: utf-8

from __future__ import division, print_function, unicode_literals, \
    absolute_import

__author__ = "mhumbert"


if __name__ == '__main__':
    from rubicon.analysis.lammps.getatomcharges import getatomcharges
    from rubicon.analysis.lammps.getmoldata import getmoldata
    from rubicon.analysis.lammps.calcCond import calcCond

    g = getatomcharges()
    gm = getmoldata()
    cc = calcCond()

    T = 350  # from lammpsio

    trjfilename = ['sample_files/NaSCN.lammpstrj']
    datfilename = 'sample_files/data.water_1NaSCN'
    logfilename = 'sample_files/mol.log'
    output = {}
    output['Conductivity'] = {}
    output['Conductivity']['units'] = 'S/m'

    (nummoltype, moltypel, moltype) = gm.getmoltype(datfilename)
    n = g.findnumatoms(datfilename)
    (molcharges, atomcharges, n) = g.getmolcharges(datfilename, n)
    output = cc.calcConductivity(molcharges, trjfilename, logfilename,
                                 datfilename, T, output)
    print((output['Conductivity']['Green_Kubo']))
