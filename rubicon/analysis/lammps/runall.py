# coding: utf-8

__author__ = "mhumbert"

from __future__ import division, print_function, unicode_literals, \
    absolute_import

'''

        Sample driver file to calculate the MSD and diffusivity for all 
        molecules in a system as well as the center of mass radial distribution
        function for all pairs of molecules in the system
        
        Requires the following comments in the lammps data file starting 
        at the third line
            
        # "number" "molecule" molecules
            
        where "number" is the number of that molecule type and
        "molecule" is a name for that molecule
            
        Do not include blank lines in between the molecule types
        
        Outputs are stored in a dictionary called output to later be stored
        in JSON format

'''

from __future__ import absolute_import

if __name__ == '__main__':
    from rubicon.analysis.lammps.MSD import MSD
    from rubicon.analysis.lammps.calcCOM import calcCOM
    from rubicon.analysis.lammps.gettimedata import gettimedata
    from rubicon.analysis.lammps.getmoldata import getmoldata
    from rubicon.analysis.lammps.COMradialnofort import COMradialdistribution
    from rubicon.analysis.lammps.getatomcharges import getatomcharges
    from rubicon.analysis.lammps.calcNEconductivity import calcNEconductivity
    from rubicon.analysis.lammps.getcoordinationnumber import \
        getcoordinationnumber

    c = calcCOM()
    m = MSD()
    gt = gettimedata()
    gm = getmoldata()
    crd = COMradialdistribution()
    gc = getatomcharges()
    ne = calcNEconductivity()
    cn = getcoordinationnumber()

    trjfile = 'sample_files/NaSCN.lammpstrj'
    datfile = 'sample_files/data.water_1NaSCN'
    logfile = 'sample_files/mol.log'
    output = {}
    output['RDF'] = {}
    output['RDF']['units'] = 'unitless and angstroms'
    output['Conductivity'] = {}
    output['Conductivity']['units'] = 'S/m'
    T = 298  # get from lammpsio

    tsjump = gt.getjump(trjfile)
    (nummoltype, moltypel, moltype) = gm.getmoltype(datfile)
    dt = gt.getdt(logfile)
    n = gc.findnumatoms(datfile)
    (molcharges, atomcharges, n) = gc.getmolcharges(datfile, n)
    molcharge = gc.molchargedict(molcharges, moltypel, moltype)
    (comx, comy, comz, Lx, Ly, Lz, Lx2, Ly2, Lz2) = c.calcCOM([trjfile],
                                                              datfile)

    output = m.runMSD(comx, comy, comz, Lx, Ly, Lz, Lx2, Ly2, Lz2, moltype,
                      moltypel, dt, tsjump, output)

    output = ne.calcNEconductivity(output, molcharge, Lx, Ly, Lz, nummoltype,
                                   moltypel, T)
    # print(output)
    # print('Conductivity Finshed')
    output = crd.runradial(datfile, comx, comy, comz, Lx, Ly, Lz, Lx2, Ly2,
                           Lz2, output, nummoltype, moltypel, moltype,
                           firststep=1)


    # output = cn.calccoordinationnumber(output,nummoltype,moltypel,Lx*Ly*Lz)
    # outputfile=open('test.json', 'w')
    # json.dump(output,outputfile,indent=4)
    # outputfile.close()
