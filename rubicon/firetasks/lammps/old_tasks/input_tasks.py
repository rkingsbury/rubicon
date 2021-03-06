# coding: utf-8

from __future__ import division, print_function, unicode_literals, \
    absolute_import

from fireworks import explicit_serialize, FireTaskBase
from pymatgen.io.lammps.data import LammpsForceFieldData
from pymatgen.io.lammps.input import NPTNVTLammpsInput
from rubicon.io.packmol.packmol import PackmolRunner

"""
This module defines 
"""


@explicit_serialize
class WritelammpsInputFromGaussian(FireTaskBase):
    """
    Writes LAMMPS Input files with the forcefield data obtained from antechmaber.
    Gaussian output files are used as input for the antechamber to generate the
    forcefield paramters.

    """

    def run_task(self, fw_spec):
        gaussian_file = fw_spec['prev_gaussian_freq']
        mol = fw_spec["molecule"]
        molecules = [mol]
        # list of gaussian files, one for each molecule type in molecules
        gaussian_files = [gaussian_file]
        # pack the molecules using packmol
        param_list = [{"number": 100, "inside box": [-14.82, -14.82, -14.82, 14.82, 14.82, 14.82]}]
        pmr = PackmolRunner(molecules, param_list)
        packed_molecule = pmr.run()
        # lammps input
        input_filename = 'mol.inp'
        data_filename = 'mol.data'
        # generate amber force field data
        lammps_data = LammpsForceFieldData.from_amber(molecules, param_list["number"],
                                                      param_list["inside box"],
                                                      packed_molecule, gaussian_files)
        user_lammps_settings = { "fix1": "NPT all npt temp 298 298 100.0 iso 1.0 1.0 100.0",
                                 "fix2": "NVT all nvt temp 298 298 100.0" }
        lammps_input = NPTNVTLammpsInput(data_obj=lammps_data, user_lammps_settings=user_lammps_settings)
        lammps_input.write_input(input_filename, data_file=data_filename)