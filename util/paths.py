import os
from enum import Enum
import util.config as config
import util.util as util

class PathHandler:
    def __init__(self,name,bmark,make_dirs=True):
        self.set_root_dir(name,bmark)
        for path in [
                self.ROOT_DIR,
                self.BMARK_DIR,
                self.LGRAPH_ADP_DIR,
                self.LGRAPH_ADP_DIAG_DIR,
                self.LSCALE_ADP_DIR,
                self.LSCALE_ADP_DIAG_DIR,
                self.MEAS_WAVEFORM_FILE_DIR,
                self.GRENDEL_FILE_DIR,
                self.PLOT_DIR
        ]:
          if make_dirs:
              util.mkdir_if_dne(path)

        self._name = name
        self._bmark = bmark

    @property
    def name(self):
        return self._name

    @staticmethod
    def path_to_args(dirname):
        args = dirname.split("/")
        assert(args[0] == 'outputs')
        assert(args[1] == 'legno')
        subset = args[2]
        bmark = args[3]
        return subset,bmark
    def set_root_dir(self,name,bmark):
        self.ROOT_DIR = "%s/legno/%s" % (config.OUTPUT_PATH,name)
        self.BMARK_DIR = self.ROOT_DIR + ("/%s" % bmark)
        self.LGRAPH_ADP_DIR = self.BMARK_DIR + "/lgraph-adp"
        self.LGRAPH_ADP_DIAG_DIR = self.BMARK_DIR + "/lgraph-diag"
        self.LSCALE_ADP_DIR = self.BMARK_DIR + "/lscale-adp"
        self.LSCALE_ADP_DIAG_DIR = self.BMARK_DIR + "/lscale-diag"
        self.GRENDEL_FILE_DIR = self.BMARK_DIR + "/grendel"
        self.PLOT_DIR = self.BMARK_DIR + "/plots"
        self.MEAS_WAVEFORM_FILE_DIR = self.BMARK_DIR + "/out-waveform"
        self.TIME_DIR = self.ROOT_DIR + "/times"


    def lscale_adp_file(self,bmark,indices,scale_index,model,opt):
      index_str = "_".join(map(lambda ind : str(ind),indices))
      return self.LSCALE_ADP_DIR+ "/%s_%s_s%s_%s_%s.circ" % \
        (self._bmark,index_str,scale_index,model,opt)


    def lscale_adp_diagram_file(self,bmark,indices,scale_index,model,opt,tag="notag"):
      index_str = "_".join(map(lambda ind : str(ind),indices))
      return self.LSCALE_ADP_DIAG_DIR+ "/%s_%s_s%s_%s_%s_%s.dot" % \
        (self._bmark,index_str,scale_index,model,opt,tag)


    def plot(self,bmark,indices,scale_index,model,opt, \
             menv_name,henv_name,tag):
      index_str = "_".join(map(lambda ind : str(ind),indices))
      return self.PLOT_DIR+ "/%s_%s_s%s_%s_%s_%s_%s_%s.png" % \
        (self._bmark,index_str,scale_index,model,opt, \
         menv_name,henv_name,\
         tag)


    def grendel_file(self,bmark,indices,scale_index,model,opt, \
                     menv_name,henv_name):
      index_str = "_".join(map(lambda ind : str(ind),indices))
      return self.GRENDEL_FILE_DIR+ "/%s_%s_s%s_%s_%s_%s_%s.grendel" % \
        (self._bmark,index_str,scale_index,model,opt,menv_name,henv_name)


    def measured_waveform_dir(self):
      return self.MEAS_WAVEFORM_FILE_DIR


    def measured_waveform_file(self,bmark,indices,scale_index, \
                               model,opt,\
                               menv_name,hwenv_name,variable,trial):
      index_str = "_".join(map(lambda ind : str(ind),indices))
      return self.MEAS_WAVEFORM_FILE_DIR+ "/%s_%s_s%s_%s_%s_%s_%s_%s_%d.json" % \
        (self._bmark,index_str,scale_index,model,opt, \
         menv_name,hwenv_name,variable,trial)


    def measured_waveform_files(self,bmark,indices,scale_index,\
                               menv_name,hwenv_name,variable):
      index_str = "_".join(map(lambda ind : str(ind),indices))
      prefix = "%s_%s_s%s_%s_%s_" % \
        (self._bmark,index_str,scale_index,menv_name,hwenv_name)

      raise Exception("TODO: this is not the correct prefix.")
      for dirname, subdirlist, filelist in \
          os.walk(self.MEAS_WAVEFORM_FILE_DIR):
        for fname in filelist:
          if fname.endswith('.json') and fname.startswith(prefix):
            yield "%s/%s" % (self.MEAS_WAVEFORM_FILE_DIR,fname)


    def measured_waveform_file_to_args(self,name):
      basename = name.split(".json")[0]
      args = basename.split("_")
      bmark = args[0]
      indices = list(map(lambda token: int(token), args[1:-7]))
      scale_index = int(args[-7].split('s')[1])
      model = args[-6]
      opt = args[-5]
      menv_name = args[-4]
      hwenv_name = args[-3]
      var_name = args[-2]
      trial = int(args[-1])

      return bmark,indices,scale_index,model,opt, \
          menv_name,hwenv_name,var_name,trial


    @staticmethod
    def grendel_file_to_args(name):
      basename = name.split(".grendel")[0]
      args = basename.split("_")
      bmark = args[0]
      indices = list(map(lambda token: int(token), args[1:-5]))
      scale_index = int(args[-5].split('s')[1])
      model = args[-4]
      opt = args[-3]
      menv_name = args[-2]
      hwenv_name = args[-1]
      return bmark,indices,scale_index,model,opt,menv_name,hwenv_name



    def extract_metadata_from_filename(self, conc_circ, fname):
      bmark,indices,scale_index,tag,opt = self.conc_circ_to_args(fname)
      conc_circ.meta['bmark'] = bmark
      conc_circ.meta['arco_index'] = indices
      conc_circ.meta['jaunt_index'] = scale_index
      model,analog_error,digital_error,bandwidth = util.unpack_tag(tag)
      conc_circ.meta['model'] = model
      conc_circ.meta['analog_error'] = analog_error
      conc_circ.meta['digital_error'] = digital_error
      conc_circ.meta['bandwidth'] = bandwidth

    @staticmethod
    def lscale_adp_to_args(name):
      basename = name.split(".adp")[0]
      args = basename.split("_")
      bmark = args[0]
      indices = list(map(lambda token: int(token), args[1:-3]))
      scale_index = int(args[-3].split('s')[1])
      model = args[-2]
      opt = args[-1]
      return bmark,indices,scale_index,model,opt


    @staticmethod
    def lgraph_adp_to_args(name):
      basename = name.split(".adp")[0]
      args = basename.split("_")
      bmark = args[0]
      indices = list(map(lambda token: int(token), args[1:]))
      return bmark,indices

    def lgraph_adp_diagram_file(self,indices):
        index_str = "_".join(map(lambda ind : str(ind),indices))
        return self.LGRAPH_ADP_DIAG_DIR+ "/%s_%s.dot" % \
          (self._bmark,index_str)


    def lgraph_adp_file(self,indices):
        index_str = "_".join(map(lambda ind : str(ind),indices))
        return self.LGRAPH_ADP_DIR+ "/%s_%s.adp" % \
          (self._bmark,index_str)

    def grendel_file_dir(self):
        return self.GRENDEL_FILE_DIR


    def lscale_adp_dir(self):
        return self.LSCALE_ADP_DIR


    def lgraph_adp_dir(self):
        return self.LGRAPH_ADP_DIR

    def has_file(self,filepath):
        if not os.path.exists(filepath):
          return False

        directory,filename = os.path.split(filepath)
        return filename in os.listdir(directory)
