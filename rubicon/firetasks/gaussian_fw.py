from rubicon.gaussian.gaussian_input_task import WritegaussianGeoTask, \
    WritegaussianFreqTask

__author__ = 'navnidhirajput'

from fireworks import  Workflow, LaunchPad
from fireworks.core.firework import Firework


from pymatgen import write_mol, Molecule
import glob
from pymatgen.io import gaussian

import glob
from pymatgen import Molecule


if __name__ == '__main__':

    task_geo = WritegaussianGeoTask()
    task_freq = WritegaussianFreqTask()
    coords = []
    sp = []
    moleculelist = glob.glob("/Users/navnidhirajput/Dropbox/solvent_molecules/*")
    for filename in moleculelist:
        mol = Molecule.from_file(filename)

        fw1 = Firework([task_geo],name = 'Gaussian geometry optimization', fw_id=1, spec= {"charge": 1,"spin_multiplicity":-1})
        fw2 = Firework([task_freq],name='Gaussian frequency and charge', fw_id=2, spec= {"charge": 1,"spin_multiplicity":-1})

        depen = {1:[2]}
        wf = Workflow([fw1,fw2], name="GAUSSIAN", links_dict=depen)

        lp = LaunchPad.auto_load()
        lp.add_wf(wf)
