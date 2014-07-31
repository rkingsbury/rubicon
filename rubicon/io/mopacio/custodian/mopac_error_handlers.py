import glob
import logging
import os
import tarfile
from custodian.custodian import ErrorHandler
from rubicon.io.mopacio.mopacio import MopOutput, MopTask

__author__ = 'xiaohuiqu'


class MopacErrorHandler(ErrorHandler):
    """
    Erro hander for MOPAC Jobs.
    """
    def __init__(self, input_file="mol.mop"):
        self.input_file = input_file
        basename = os.path.splitext(self.input_file)[0]
        self.output_file = basename + ".out"
        self.arc_file = basename + ".arc"
        self.errors = None
        self.outdata = None
        self.mopinp = None

    def check(self):
        self.outdata = MopOutput(self.output_file).data
        self.mopinp = MopTask.from_file(self.input_file)
        self.errors = None
        if self.outdata["has_error"]:
            self.errors = self.outdata["error"]
            return True
        return False

    def correct(self):
        self.backup()
        actions = []
        e = self.errors[0]
        if e == "Geometry optimization failed":
            self.mopinp.use_bfgs()
            actions.append("Use BFGS")
        else:
            return {"errors": self.errors, "actions": None}
        self.mopinp.write_file(self.input_file)
        return {"errors": self.errors, "actions": actions}


    def backup(self):
        error_num = max([0] + [int(f.split(".")[1])
                               for f in glob.glob("error.*.tar.gz")])
        filename = "error.{}.tar.gz".format(error_num + 1)
        logging.info("Backing up run to {}.".format(filename))
        tar = tarfile.open(filename, "w:gz")
        bak_list = [self.input_file, self.output_file] + \
                   list(self.ex_backup_list)
        for f in bak_list:
            if os.path.exists(f):
                tar.add(f)
        tar.close()

