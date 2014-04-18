from random import Random
from time import time
import math
import itertools

import inspyred
from pymatgen.analysis.molecule_structure_comparator import CovalentRadius
import openbabel as ob
from pymatgen.core.structure import Molecule
from pymatgen.io.babelio import BabelMolAdaptor
from pymatgen.io.qchemio import QcOutput
from pymatgen.io.smartio import write_mol
import numpy as np


class HardSphereIonPlacer():
    overlap_energy = 1.0E4
    angstrom2au = 1.0/0.52917721092
    gravity = 0.001
    metals = ['Li', 'Be', 'Na', 'Mg', 'Al', 'K', 'Ca', 'Sc', 'Ti', 'V',
              'Cr', 'Mn', 'Fe', 'Co', 'Ni', 'Cu', 'Zn', 'Ga', 'Rb', 'Sr',
              'Y', 'Zr', 'Nb', 'Mo', 'Tc', 'Ru', 'Rh', 'Pd', 'Ag', 'Cd',
              'In', 'Sn', 'Sb', 'Cs', 'Ba', 'La', 'Ce', 'Pr', 'Nd', 'Pm',
              'Sm', 'Eu', 'Gd', 'Tb', 'Dy', 'Ho', 'Er', 'Tm', 'Yb', 'Lu',
              'Hf', 'Ta', 'W', 'Re',  'Os', 'Ir', 'Pt', 'Au', 'Hg', 'Tl',
              'Pb']

    def __init__(self, molecule, molecule_charges, cation,
                 cation_charges, anion, anion_charges,
                 num_cation=1, num_anion=1, prng=None,
                 covalent_radius_scale=2.0,
                 metal_radius_scale=0.5,
                 seed=None):
        self.prng = prng if prng else Random()
        self.covalent_radius_scale = covalent_radius_scale
        self.metal_radius_scale = metal_radius_scale
        self.seed = seed if seed else time()
        self.prng.seed(self.seed)
        self.final_pop = None
        self.best = None
        self.ea = inspyred.swarm.PSO(self.prng)
        self.ea.terminator = inspyred.ec.terminators.evaluation_termination
        self.ea.topology = inspyred.swarm.topologies.ring_topology
        self.molecule = molecule
        self.cation = cation
        self.anion = anion
        self.num_cation = num_cation
        self.num_anion = num_anion
        self.mol_charges = molecule_charges
        self.cation_charges = cation_charges
        self.anion_charges = anion_charges
        self.mol_coords, self.mol_radius, self.mol_elements =\
            self.normalize_molecule(
                self.molecule, self.covalent_radius_scale,
                self.metal_radius_scale)
        cation_coords, self.cation_radius, self.cation_elements = \
            self.normalize_molecule(
                self.cation, self.covalent_radius_scale,
                self.metal_radius_scale)
        anion_coords, self.anion_radius, self.anion_elements = \
            self.normalize_molecule(
                self.anion, self.covalent_radius_scale, self.metal_radius_scale)
        if len(self.mol_coords) != len(self.mol_charges):
            raise ValueError("The charge length and number of atoms in the"
                             "molecule are inconsitent")
        if len(cation_coords) != len(self.cation_charges):
            raise ValueError("The charge length and number of atoms in the"
                             "cation are inconsitent")
        if len(anion_coords) != len(self.anion_charges):
            raise ValueError("The charge length and number of atoms in the"
                             "anion are inconsitent")
        self.bounder = None
        self.set_bounder()
        self.best_pymatgen_mol = None
        self.playing_time = None

    def set_bounder(self):
        lower_bound = []
        upper_bound = []
        cation_num_atoms = self.cation.NumAtoms()
        anion_num_atoms = self.anion.NumAtoms()
        mol_radius = max([math.sqrt(sum([x**2 for x in c]))
                          for c in self.mol_coords])
        cation_coords = self.get_mol_coords(self.cation)
        cation_radius = max([math.sqrt(sum([x**2 for x in c]))
                             for c in cation_coords])
        anion_coords = self.get_mol_coords(self.anion)
        anion_radius = max([math.sqrt(sum([x**2 for x in c]))
                            for c in anion_coords])
        max_length = 2 * (mol_radius + cation_radius * self.num_cation +
                          anion_radius * self.num_anion)
        x_min = max_length + 5.0 * (self.num_cation + self.num_anion)
        for i in range(self.num_cation):
            lower_bound.extend([-x_min] * 3)
            upper_bound.extend([x_min] * 3)
            if cation_num_atoms > 1:
                lower_bound.extend([0.0, -math.pi])
                upper_bound.extend([math.pi, math.pi])
        for i in range(self.num_anion):
            lower_bound.extend([-x_min] * 3)
            upper_bound.extend([x_min] * 3)
            if anion_num_atoms > 1:
                lower_bound.extend([0.0, -math.pi])
                upper_bound.extend([math.pi, math.pi])
        self.bounder = inspyred.ec.Bounder(lower_bound, upper_bound)
        return self.bounder

    @staticmethod
    def normalize_molecule(mol, covalent_radius_scale, metal_radius_scale):
        mol.Center()
        radius = []
        species = []
        ref_radius = CovalentRadius.radius
        num_atoms = mol.NumAtoms()
        element_table = ob.OBElementTable()
        for i in range(1, num_atoms + 1):
            a = mol.GetAtom(i)
            atomic_num = a.GetAtomicNum()
            symbol = element_table.GetSymbol(atomic_num)
            species.append(symbol)
            if symbol in HardSphereIonPlacer.metals:
                scale = metal_radius_scale
            else:
                scale = covalent_radius_scale
            rad = ref_radius[symbol] * HardSphereIonPlacer.angstrom2au * scale
            radius.append(rad)
        coords = HardSphereIonPlacer.get_mol_coords(mol)
        return coords, radius, species

    @staticmethod
    def get_mol_coords(mol):
        coords = []
        num_atoms = mol.NumAtoms()
        for i in range(1, num_atoms + 1):
            a = mol.GetAtom(i)
            coords.append([a.GetX() * HardSphereIonPlacer.angstrom2au,
                           a.GetY() * HardSphereIonPlacer.angstrom2au,
                           a.GetZ() * HardSphereIonPlacer.angstrom2au])
        return coords

    @staticmethod
    def rotate(mol, theta, phi):
        m_theta = np.array([[1.0, 0.0, 0.0],
                            [0.0, math.cos(theta), -math.sin(theta)],
                            [0.0, math.sin(theta), math.cos(theta)]])
        m_phi = np.array([[math.cos(phi), 0.0, math.sin(phi)],
                          [0.0, 1.0, 0.0],
                          [-math.sin(phi), 0.0, math.cos(phi)]])
        m = np.dot(m_phi, m_theta)
        m_list = list(itertools.chain(*m))
        mol.Rotate(ob.double_array(m_list))
        return mol

    def decode_solution(self, x):
        cation_coords = []
        anion_coords = []
        cation_num_atoms = self.cation.NumAtoms()
        anion_num_atoms = self.anion.NumAtoms()
        xi = 0
        for i in range(self.num_cation):
            cc = ob.OBMol(self.cation)
            tx, ty, tz = x[xi: xi+3]
            xi += 3
            if cation_num_atoms > 1:
                theta = x[xi]
                xi += 1
                phi = x[xi]
                xi += 1
                self.rotate(cc, theta, phi)
            cc.Translate(ob.vector3(tx, ty, tz))
            cation_coords.append(self.get_mol_coords(cc))
        for i in range(self.num_anion):
            ac = ob.OBMol(self.anion)
            tx, ty, tz = x[xi: xi+3]
            xi += 3
            if anion_num_atoms > 1:
                theta = x[xi]
                xi += 1
                phi = x[xi]
                xi += 1
                HardSphereIonPlacer.rotate(ac, theta, phi)
            ac.Translate(ob.vector3(tx, ty, tz))
            anion_coords.append(HardSphereIonPlacer.get_mol_coords(ac))
        return cation_coords, anion_coords

    @staticmethod
    def pair_energy(coords1, charges1, radius1, coords2, charges2,
                    radius2):
        energy = 0.0
        for coord1, charge1, rad1 in zip(coords1, charges1, radius1):
            for coord2, charge2, rad2 in zip(coords2, charges2, radius2):
                distance = math.sqrt(sum([(x1-x2)**2 for x1, x2
                                          in zip(coord1, coord2)]))
                if distance <= rad1 + rad2:
                    energy += HardSphereIonPlacer.overlap_energy
                    continue
                electrostatic_energy = charge1 * charge2 / distance
                energy += electrostatic_energy
        return energy

    def gravitational_energy(self, ion_coords, ion_radius):
        grav_distance = 10000.0
        for mol_coord, mol_rad in zip(self.mol_coords, self.mol_radius):
            for ion_coord, ion_rad in zip(ion_coords, ion_radius):
                distance = math.sqrt(sum([(x1-x2)**2 for x1, x2
                                          in zip(mol_coord, ion_coord)]))
                if distance > mol_rad + ion_rad:
                    gd = distance - (mol_rad + ion_rad)
                    if gd < grav_distance:
                        grav_distance = gd
                else:
                    return 0.0
        if grav_distance > 9999.0:
            return 0.0
        else:
            return self.gravity * grav_distance

    def calc_energy(self, cation_coords, anion_coords):
        energy = 0.0
        for frag_coords in cation_coords:
            energy += self.pair_energy(
                self.mol_coords, self.mol_charges, self.mol_radius,
                frag_coords, self.cation_charges, self.cation_radius)
            energy += self.gravitational_energy(frag_coords, self.cation_radius)
        for frag_coords in anion_coords:
            energy += self.pair_energy(
                self.mol_coords, self.mol_charges, self.mol_radius,
                frag_coords, self.anion_charges, self.anion_radius)
            energy += self.gravitational_energy(frag_coords, self.anion_radius)
        for cc in cation_coords:
            for ac in anion_coords:
                energy += self.pair_energy(
                    cc, self.cation_charges, self.cation_radius,
                    ac, self.anion_charges, self.anion_radius)
        return energy

    @staticmethod
    def generate_conformers(random, args):
        # generator
        lower_bound = args['_ec'].bounder.lower_bound
        upper_bound = args['_ec'].bounder.upper_bound
        return [random.uniform(l, u) for l, u in zip(lower_bound, upper_bound)]

    # noinspection PyUnusedLocal
    def evaluate_conformers(self, candidates, args):
        # evaluator
        fitness = []
        for c in candidates:
            cation_coords, anion_coords = self.decode_solution(c)
            energy = self.calc_energy(cation_coords, anion_coords)
            fitness.append(energy)
        return fitness

    def place(self, max_evaluations=30000, pop_size=100, neighborhood_size=5):
        t1 = time()
        self.final_pop = self.ea.evolve(generator=self.generate_conformers,
                                        evaluator=self.evaluate_conformers,
                                        pop_size=pop_size,
                                        bounder=self.bounder,
                                        maximize=False,
                                        max_evaluations=max_evaluations,
                                        neighborhood_size=neighborhood_size)
        self.best = max(self.final_pop)
        # max means best, not necessarily smallest
        best_cation_coords, best_anion_coords = self.decode_solution(
            self.best.candidate)
        species = []
        coords_au = []
        species.extend(self.mol_elements)
        coords_au.extend(self.mol_coords)
        for c in best_cation_coords:
            species.extend(self.cation_elements)
            coords_au.extend(c)
        for c in best_anion_coords:
            species.extend(self.anion_elements)
            coords_au.extend(c)
        coords_ang = [[x/self.angstrom2au for x in c] for c in coords_au]
        self.best_pymatgen_mol = Molecule(species, coords_ang)
        t2 = time()
        self.playing_time = t2 - t1
        return self.best_pymatgen_mol


def main():
    def gcd(a, b):
        if b == 0:
                return a
        else:
                return gcd(b, a % b)

    def lcm(a, b):
            return a * b / gcd(a, b)
    import argparse
    parser = argparse.ArgumentParser(
        description="Place salt around a molecule")
    parser.add_argument("-m", "--molecule", dest="molecule", type=str,
                        required=True,
                        help="the QChem output file name of molecule")
    parser.add_argument("-c", "--cation", dest="cation", type=str,
                        required=True,
                        help="the QChem output file name of cation")
    parser.add_argument("-a", "--anion", dest="anion", type=str,
                        required=True,
                        help="the QChem output file name of anion")
    parser.add_argument("-o", "--outputfile", dest="outputfile", type=str,
                        required=True,
                        help="the file name of the aligned conformer")
    parser.add_argument("-n", "--num_iter", dest="num_iter", type=int,
                        default=30000,
                        help="maximum number of evaluations")
    parser.add_argument("-s", "--size", dest="size", type=int, default=100,
                        help="population size")
    options = parser.parse_args()
    qcout_molecule = QcOutput(options.molecule)
    qcout_cation = QcOutput(options.cation)
    qcout_anion = QcOutput(options.anion)
    total_charge_cation = qcout_cation.data[0]["molecules"][-1].charge
    total_charge_anion = qcout_anion.data[0]["molecules"][-1].charge
    num_lcm = lcm(total_charge_cation, -total_charge_anion)
    num_cation = num_lcm/total_charge_cation
    num_anion = num_lcm/-total_charge_anion
    charges_molecule = qcout_molecule.data[0]["charges"]["chelpg"]
    charges_cation = qcout_cation.data[0]["charges"]["chelpg"]
    charges_anion = qcout_anion.data[0]["charges"]["chelpg"]
    pymatgen_mol_molecule = qcout_molecule.data[0]["molecules"][-1]
    pymatgen_mol_cation = qcout_cation.data[0]["molecules"][-1]
    pymatgen_mol_anion = qcout_anion.data[0]["molecules"][-1]
    # noinspection PyProtectedMember
    obmol_molecule = BabelMolAdaptor(pymatgen_mol_molecule)._obmol
    # noinspection PyProtectedMember
    obmol_cation = BabelMolAdaptor(pymatgen_mol_cation)._obmol
    # noinspection PyProtectedMember
    obmol_anion = BabelMolAdaptor(pymatgen_mol_anion)._obmol
    placer = HardSphereIonPlacer(
        obmol_molecule, charges_molecule, obmol_cation, charges_cation,
        obmol_anion, charges_anion, num_cation, num_anion)
    placer.place(max_evaluations=options.num_iter,
                 pop_size=options.size)
    print 'It took {:.1f} seconds to place the salt'.format(placer
                                                            .playing_time)
    write_mol(placer.best_pymatgen_mol, options.outputfile)

if __name__ == '__main__':
    main()