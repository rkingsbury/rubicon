# coding: utf-8

from __future__ import division, print_function, unicode_literals, \
    absolute_import

import copy
import itertools
import math

import numpy as np
from six.moves import range
from six.moves import zip

# try:
#     import openbabel as ob
# except ImportError:
#     ob = None

from pymatgen.analysis.molecule_structure_comparator import CovalentRadius
from pymatgen.io.babel import BabelMolAdaptor
from pymatgen import Element

from rubicon.utils.ion_arranger.energy_evaluator import EnergyEvaluator

__author__ = 'xiaohuiqu'


class AtomicRadiusUtils(object):
    metals = ['Li', 'Be', 'Na', 'Mg', 'Al', 'K', 'Ca', 'Sc', 'Ti', 'V',
              'Cr', 'Mn', 'Fe', 'Co', 'Ni', 'Cu', 'Zn', 'Ga', 'Rb', 'Sr',
              'Y', 'Zr', 'Nb', 'Mo', 'Tc', 'Ru', 'Rh', 'Pd', 'Ag', 'Cd',
              'In', 'Sn', 'Sb', 'Cs', 'Ba', 'La', 'Ce', 'Pr', 'Nd', 'Pm',
              'Sm', 'Eu', 'Gd', 'Tb', 'Dy', 'Ho', 'Er', 'Tm', 'Yb', 'Lu',
              'Hf', 'Ta', 'W', 'Re', 'Os', 'Ir', 'Pt', 'Au', 'Hg', 'Tl',
              'Pb']
    angstrom2au = 1.0 / 0.52917721092

    def __init__(self, covalent_radius_scale=2.0, metal_radius_scale=0.5):
        self.covalent_radius_scale = covalent_radius_scale
        self.metal_radius_scale = metal_radius_scale

    def get_radius(self, mol):
        '''
        Return a list of scaled radii for each atom in the Molecule,
        in au.
        '''
        radius = []
        ref_radius = CovalentRadius.radius
        num_atoms = mol.NumAtoms()
        # element_table = ob.OBElementTable()
        for i in range(1, num_atoms + 1):
            a = mol.GetAtom(i)
            atomic_num = a.GetAtomicNum()
            # symbol = element_table.GetSymbol(atomic_num)
            symbol = Element.from_Z(atomic_num).symbol
            if symbol in self.metals:
                scale = self.metal_radius_scale
            else:
                scale = self.covalent_radius_scale
            rad = ref_radius[symbol] * self.angstrom2au * scale
            radius.append(rad)
        return radius


class CoulumbEnergyEvaluator(EnergyEvaluator):
    def taboo_current_position(self):
        pass

    def __init__(self, mol_coords, mol_charges, mol_radius, fragments_charges,
                 nums_fragments,
                 fragment_atom_radius):
        super(CoulumbEnergyEvaluator, self).__init__(mol_coords)
        self.mol_charges = mol_charges
        self.fragments_charges = []
        for frag_ch, num in zip(fragments_charges, nums_fragments):
            self.fragments_charges.extend([frag_ch] * num)
        self.mol_radius = mol_radius
        self.fragments_atom_radius = []
        for frag_rad, num in zip(fragment_atom_radius, nums_fragments):
            self.fragments_atom_radius.extend([frag_rad] * num)

    def calc_energy(self, fragments_coords):
        components = []
        components.append(
            tuple([self.mol_coords, self.mol_charges, self.mol_radius]))
        for coords, ch, rad in zip(fragments_coords, self.fragments_charges,
                                   self.fragments_atom_radius):
            components.append(tuple([coords, ch, rad]))
        energy = 0.0
        for (coords1, ch1, rad1), (coords2, ch2, rad2) in \
                itertools.combinations(components):
            energy += self._pair_energy(coords1, ch1, rad1, coords2, ch2, rad2)
        return energy

    @staticmethod
    def _pair_energy(coords1, charges1, radius1, coords2, charges2,
                     radius2):
        energy = 0.0
        for coord1, charge1, rad1 in zip(coords1, charges1, radius1):
            for coord2, charge2, rad2 in zip(coords2, charges2, radius2):
                distance = math.sqrt(sum([(x1 - x2) ** 2 for x1, x2
                                          in zip(coord1, coord2)]))
                if distance <= rad1 + rad2:
                    continue
                else:
                    electrostatic_energy = charge1 * charge2 / distance
                    energy += electrostatic_energy
        return energy


class HardSphereEnergyEvaluator(EnergyEvaluator):
    def taboo_current_position(self):
        pass

    base_energy = 5.0E4
    overlap_energy = 0.01

    def __init__(self, mol_coords, mol_radius, fragments_atom_radius,
                 nums_fragments):
        super(HardSphereEnergyEvaluator, self).__init__(mol_coords)
        self.mol_radius = mol_radius
        self.fragments_atom_radius = []
        for frag_rad, num in zip(fragments_atom_radius, nums_fragments):
            self.fragments_atom_radius.extend([frag_rad] * num)

    def calc_energy(self, fragments_coords):
        components = []
        components.append(tuple([self.mol_coords, self.mol_radius]))
        for coords, rad in zip(fragments_coords, self.fragments_atom_radius):
            components.append(tuple([coords, rad]))
        energy = 0.0
        for (coords1, rad1), (coords2, rad2) in \
                itertools.combinations(components, 2):
            energy += self._pair_energy(coords1, rad1, coords2, rad2)
        if energy < 0.009:
            return 0.0
        else:
            return energy + self.base_energy

    @classmethod
    def _pair_energy(cls, coords1, radius1, coords2, radius2):
        energy = 0.0
        for coord1, rad1 in zip(coords1, radius1):
            for coord2, rad2 in zip(coords2, radius2):
                distance = math.sqrt(sum([(x1 - x2) ** 2 for x1, x2
                                          in zip(coord1, coord2)]))
                if distance <= rad1 + rad2:
                    energy += cls.overlap_energy
        return energy


class UmbrellarForceEnergyEvaluator(EnergyEvaluator):
    def taboo_current_position(self):
        pass

    base_energy = 7.0E4

    def __init__(self, mol_coords, centers, taboo_tolerance_au,
                 best_umbrella_ratio):
        super(UmbrellarForceEnergyEvaluator, self).__init__(mol_coords)
        self.centers = centers
        self.umbrella_radius = taboo_tolerance_au * best_umbrella_ratio

    def calc_energy(self, fragments_coords):
        if len(self.centers) == 0:
            return 0.0
        umbrella_distances = []
        for center in self.centers:
            current_pos = list(itertools.chain(*fragments_coords))
            atom_distances = [
                math.sqrt(sum([(x1 - x2) ** 2 for x1, x2 in zip(c1, c2)]))
                for c1, c2 in
                zip(center, current_pos)]
            rmsd_distance = math.sqrt(
                sum(d ** 2 for d in atom_distances) / len(atom_distances))
            if rmsd_distance <= self.umbrella_radius:
                return 0.0
            else:
                umbrella_distances.append(rmsd_distance)
        energy = min(umbrella_distances)
        if energy < 0.01:
            return 0.0
        else:
            return self.base_energy + min(umbrella_distances)


class OrderredLayoutEnergyEvaluator(EnergyEvaluator):
    def taboo_current_position(self):
        pass

    base_energy = 6.0E4

    def __init__(self, mol_coords, nums_fragments):
        super(OrderredLayoutEnergyEvaluator, self).__init__(mol_coords)
        self.nums_fragments = nums_fragments

    def calc_energy(self, fragments_coords):
        tokens = []
        start_index = 0
        for nf in self.nums_fragments:
            end_index = start_index + nf
            tokens.append(fragments_coords[start_index: end_index])
            start_index = end_index
        if start_index != len(fragments_coords):
            raise Exception("The number of fragments is not consistent")
        spearmans_rank_coeffs = []
        for frag in tokens:
            ranks = self._get_frag_ranks(frag)
            coeff = self._spearsman_rank_coefficient(ranks)
            spearmans_rank_coeffs.append(coeff)
        total_spearmans = sum(spearmans_rank_coeffs)
        # positive spearmans rank coefficient means more ordered, and should
        # be prefered by negative energy, therefore, inverse the spearmans value
        energy = (-total_spearmans) + len(self.nums_fragments)
        if energy < 1.0E-8:
            return 0.0
        else:
            return energy + self.base_energy

    @classmethod
    def _get_frag_ranks(cls, frag_coords):
        grain_size = 1.0
        natoms = len(frag_coords[0])
        nfrags = len(frag_coords)
        center_with_original_rank = []
        for i, frag in enumerate(frag_coords):
            xs, ys, zs = list(zip(*frag))
            center = tuple([sum(xs) / float(natoms), sum(ys) / float(natoms),
                            sum(zs) / float(natoms)])
            center_with_original_rank.append(tuple([center, i + 1]))
        # sorted_center_with_original_rank = []
        # while len(center_with_original_rank) > 0:
        #     xi, yi, zi = center_with_original_rank[0][0]
        #     lowest_index = 0
        #     for j in range(len(center_with_original_rank)):
        #         i_lowest = True
        #         xj, yj, zj = center_with_original_rank[j][0]
        #         if abs(xi - xj) > grain_size:
        #             if xi > xj:
        #                 i_lowest = False
        #         elif abs(yi - yj) > grain_size:
        #             if yi > yj:
        #                 i_lowest = False
        #         elif abs(zi - zj) > grain_size:
        #             if zi > zj:
        #                 i_lowest = False
        #         if not i_lowest:
        #             lowest_index = j
        #             xi, yi, zi = center_with_original_rank[lowest_index][0]
        #     sorted_center_with_original_rank.append(center_with_original_rank.pop(lowest_index))
        sorted_center_with_original_rank = sorted(center_with_original_rank,
                                                  key=lambda x: x[0][0])
        original_ranks = [i for center, i in sorted_center_with_original_rank]
        cur_orig_rank = [tuple([i + 1, j]) for i, j in
                         zip(list(range(nfrags)), original_ranks)]
        cur_orig_rank.sort(key=lambda x: x[1])
        ranks = [i for i, j in cur_orig_rank]
        return ranks

    @classmethod
    def _spearsman_rank_coefficient(self, rank_y):
        n = len(rank_y)
        if n == 0 or n == 1:
            return 1.0
        rank_x = list(range(1, n + 1))
        d_2 = [(rx - ry) ** 2 for rx, ry in zip(rank_x, rank_y)]
        spearsman = 1.0 - (6.0 * sum(d_2)) / (n * (n ** 2 - 1))
        return spearsman


class ContactDetector(object):
    def __init__(self, mol_coords, mol_radius, fragments_atom_radius,
                 nums_fragments, cap=0.0):
        self.mol_coords = mol_coords
        self.mol_radius = mol_radius
        self.fragments_atom_radius = []
        for frag_rad, num in zip(fragments_atom_radius, nums_fragments):
            self.fragments_atom_radius.extend([frag_rad] * num)
        self.cap = cap * AtomicRadiusUtils.angstrom2au

    def is_contact(self, fragments_coords):
        contact_matrix = self._get_contact_matrix(fragments_coords)
        distance_matrix = self._get_distance_matrix(contact_matrix)
        return np.all(distance_matrix < 1000)

    @classmethod
    def _get_distance_matrix(cls, contact_matrix):
        # Find all-pairs shortest path lengths using Floyd's algorithm
        distMatrix = copy.deepcopy(contact_matrix)
        n, m = distMatrix.shape
        um = np.identity(n)
        distMatrix[distMatrix == 0] = 10001  # set zero entries to inf
        distMatrix[um == 1] = 0  # except diagonal which should be zero
        for i in range(n):
            distMatrix = np.minimum(distMatrix,
                                    distMatrix[np.newaxis, i, :] + distMatrix[
                                                                   :, i,
                                                                   np.newaxis])
        return distMatrix

    def _get_contact_matrix(self, fragments_coords):
        fragments = [(self.mol_coords, self.mol_radius)]
        fragments.extend(
            list(zip(fragments_coords, self.fragments_atom_radius)))
        num_frag = len(fragments)
        fragments = [(c, r, i) for i, (c, r) in enumerate(fragments)]
        contact_matrix = np.zeros((num_frag, num_frag), dtype=int)
        frag_pair = itertools.combinations(fragments, r=2)
        for p in frag_pair:
            ((c1s, r1s, i1), (c2s, r2s, i2)) = p
            contact = 0
            for (c1, r1), (c2, r2) in itertools.product(list(zip(c1s, r1s)),
                                                        list(zip(c2s, r2s))):
                distance = math.sqrt(sum([(x1 - x2) ** 2 for x1, x2
                                          in zip(c1, c2)]))
                if distance <= r1 + r2 + self.cap:
                    contact = 1
                    break
            contact_matrix[i1, i2] = contact
            contact_matrix[i2, i1] = contact
        return contact_matrix


class ContactGapRMSDEnergyEvaluator(EnergyEvaluator):
    base_energy = 4.0E4

    def taboo_current_position(self):
        pass

    def __init__(self, mol_coords, mol_radius, fragments_atom_radius,
                 nums_fragments, cap=0.0):
        super(ContactGapRMSDEnergyEvaluator, self).__init__(mol_coords)
        self.mol_coords = mol_coords
        self.mol_radius = mol_radius
        self.fragments_atom_radius = []
        for frag_rad, num in zip(fragments_atom_radius, nums_fragments):
            self.fragments_atom_radius.extend([frag_rad] * num)
        self.cap = cap * AtomicRadiusUtils.angstrom2au

    def calc_energy(self, fragments_coords):
        max_gap = 0.0
        mol_gaps = self._get_mol_gaps(fragments_coords)
        for g, i1, i2 in mol_gaps:
            if g > max_gap:
                max_gap = g
        rmsd_gaps = math.sqrt(
            sum([g ** 2 for g, i1, i2 in mol_gaps]) / len(mol_gaps))
        if max_gap < 0.1:
            return 0.0
        else:
            return self.base_energy + rmsd_gaps

    def _get_mol_gaps(self, fragments_coords):
        fragments = [(self.mol_coords, self.mol_radius)]
        fragments.extend(
            list(zip(fragments_coords, self.fragments_atom_radius)))
        fragments = [(c, r, i) for i, (c, r) in enumerate(fragments)]
        mol_gaps = []
        for c1s, r1s, i1 in fragments:
            min_frag1_gap = 9999999999.9
            nearest_frag_index = -1
            for c2s, r2s, i2 in fragments:
                if i1 == i2:
                    continue
                contact = False
                for (c1, r1), (c2, r2) in itertools.product(
                        list(zip(c1s, r1s)),
                        list(zip(c2s, r2s))):
                    distance = math.sqrt(sum([(x1 - x2) ** 2 for x1, x2
                                              in zip(c1, c2)]))
                    if distance <= r1 + r2 + self.cap:
                        contact = True
                        break
                    else:
                        cur_gap = distance - (r1 + r2 + self.cap)
                        if cur_gap < min_frag1_gap:
                            min_frag1_gap = cur_gap
                            nearest_frag_index = i2
                if contact:
                    min_frag1_gap = 0.0
                    nearest_frag_index = i2
                    break
            mol_gaps.append(tuple([min_frag1_gap, i1, nearest_frag_index]))
        return mol_gaps


class LargestContactGapEnergyEvaluator(EnergyEvaluator):
    base_energy = 4.0E4
    grain_size = 0.3

    def taboo_current_position(self):
        pass

    def __init__(self, mol_coords, mol_radius, fragments_atom_radius,
                 nums_fragments, max_cap, threshold=1.0E-2):
        super(LargestContactGapEnergyEvaluator, self).__init__(mol_coords)
        self.max_cap = max_cap * AtomicRadiusUtils.angstrom2au
        self.threshold = threshold
        self.contact_detector = ContactDetector(mol_coords, mol_radius,
                                                fragments_atom_radius,
                                                nums_fragments, cap=0.0)

    @classmethod
    def _coarse_grain_energy(cls, energy):
        decimal_places = -int(math.floor(math.log10(cls.grain_size)))
        folds = round(cls.grain_size / (10.0 ** -decimal_places), 0)
        coarse_grained_energy = round(energy / folds, decimal_places) * folds
        return coarse_grained_energy

    def calc_energy(self, fragments_coords):
        low = 0.0
        high = self.max_cap
        self.contact_detector.cap = high
        if not self.contact_detector.is_contact(fragments_coords):
            return float("NaN")
        self.contact_detector.cap = low
        if self.contact_detector.is_contact(fragments_coords):
            return low
        while high - low > self.threshold:
            mid = (low + high) / 2.0
            self.contact_detector.cap = mid
            if self.contact_detector.is_contact(fragments_coords):
                high = mid
            else:
                low = mid
        energy = (high + low) / 2.0
        energy = self._coarse_grain_energy(energy)
        if energy < self.grain_size * 0.5:
            return 0.0
        else:
            return energy + self.base_energy


class GravitationalEnergyEvaluator(EnergyEvaluator):
    def taboo_current_position(self):
        pass

    gravity = 0.001

    def __init__(self, mol_coords, mol_radius, fragments_atom_radius,
                 nums_fragments):
        super(GravitationalEnergyEvaluator, self).__init__(mol_coords)
        self.mol_radius = mol_radius
        self.fragments_atom_radius = []
        for frag_rad, num in zip(fragments_atom_radius, nums_fragments):
            self.fragments_atom_radius.extend([frag_rad] * num)

    def calc_energy(self, fragments_coords):
        energy = 0.0
        for frag_coords, frag_radius in zip(fragments_coords,
                                            self.fragments_atom_radius):
            energy += self._gravitational_energy(frag_coords, frag_radius)
        return energy

    def _gravitational_energy(self, ion_coords, ion_radius):
        grav_distance = 10000.0
        for mol_coord, mol_rad in zip(self.mol_coords, self.mol_radius):
            for ion_coord, ion_rad in zip(ion_coords, ion_radius):
                distance = math.sqrt(sum([(x1 - x2) ** 2 for x1, x2
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


class HardSphereElectrostaticEnergyEvaluator(EnergyEvaluator):
    def taboo_current_position(self):
        pass

    def __init__(self, mol_coords, mol_radius, mol_charges, fragments_charges,
                 nums_fragments, fragment_atom_radius):
        super(HardSphereElectrostaticEnergyEvaluator, self).__init__(
            mol_coords)
        self.hardsphere = HardSphereEnergyEvaluator(mol_coords, mol_radius,
                                                    fragment_atom_radius,
                                                    nums_fragments)
        self.coulumb = CoulumbEnergyEvaluator(mol_coords, mol_charges,
                                              mol_radius, fragments_charges,
                                              nums_fragments,
                                              fragment_atom_radius)
        self.gravitation = GravitationalEnergyEvaluator(mol_coords, mol_radius,
                                                        fragment_atom_radius,
                                                        nums_fragments)
        self.calculators = [self.hardsphere, self.coulumb, self.gravitation]

    def calc_energy(self, fragments_coords):
        energy = 0.0
        for c in self.calculators:
            energy += c.calc_energy(fragments_coords)
            if energy > HardSphereEnergyEvaluator.overlap_energy * 0.9:
                return energy
        return energy

    @classmethod
    def from_qchem_output(cls, mol_qcout, cation_qcout, anion_qcout,
                          covalent_radius_scale=2.0, metal_radius_scale=0.5):
        from rubicon.utils.ion_arranger.ion_arranger import IonPlacer
        mol_charges = mol_qcout.data[0]["charges"]["chelpg"]
        cation_charges = cation_qcout.data[0]["charges"]["chelpg"]
        anion_charges = anion_qcout.data[0]["charges"]["chelpg"]
        pymatgen_mol_molecule = mol_qcout.data[0]["molecules"][-1]
        pymatgen_mol_cation = cation_qcout.data[0]["molecules"][-1]
        pymatgen_mol_anion = anion_qcout.data[0]["molecules"][-1]

        obmol_mol = BabelMolAdaptor(pymatgen_mol_molecule)._obmol

        obmol_cation = BabelMolAdaptor(pymatgen_mol_cation)._obmol

        obmol_anion = BabelMolAdaptor(pymatgen_mol_anion)._obmol
        mol_coords = IonPlacer.normalize_molecule(obmol_mol)
        rad_util = AtomicRadiusUtils(covalent_radius_scale, metal_radius_scale)
        mol_radius = rad_util.get_radius(obmol_mol)
        cation_radius = rad_util.get_radius(obmol_cation)
        anion_radius = rad_util.get_radius(obmol_anion)
        evaluator = HardSphereElectrostaticEnergyEvaluator(
            mol_coords, mol_radius, cation_radius, anion_radius,
            mol_charges, cation_charges, anion_charges)
        return evaluator
