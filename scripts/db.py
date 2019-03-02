import util.config as cfg
import util.paths as paths
import bmark.diffeqs as diffeqs
import sqlite3
from enum import Enum
import os
import datetime
import lab_bench.lib.command as cmd
import lab_bench.lib.expcmd.micro_getter as microget
import lab_bench.lib.expcmd.osc as osc

def get_output_files(grendel_script):
  with open(grendel_script,'r') as fh:
    for line in fh:
      instr = cmd.parse(line)
      if isinstance(instr,osc.OscGetValuesCmd):
        yield instr.filename
      elif isinstance(instr,microget.MicroGetADCValuesCmd):
        yield instr.filename

def make_args(bmark,arco_inds,jaunt_indx,opt,menv_name,hwenv_name):
  return  {
    'bmark':bmark,
    'arco0':arco_inds[0],
    'arco1':arco_inds[1],
    'arco2':arco_inds[2],
    'arco3':arco_inds[3],
    'jaunt':jaunt_indx,
    'opt': opt,
    'menv':menv_name,
    'hwenv': hwenv_name
  }

class OutputStatus(Enum):
  PENDING = "pending"
  RAN = "ran"
  ANALYZED = "analyzed"


class ExperimentStatus(Enum):
  PENDING = "pending"
  RAN = "ran"
  ANALYZED = "analyzed"

class OutputEntry:

  def __init__(self,db,bmark,arco_indices,jaunt_index,
               objective_fun,math_env,hw_env,varname):
    self._db = db
    self._bmark = bmark
    self._arco_indices = arco_indices
    self._jaunt_index = jaunt_index
    self._objective_fun = objective_fun
    self._math_env = math_env
    self._hw_env = hw_env
    self._varname = varname
    self._out_file = None
    self._status = None
    self._quality = None
    self._rank = None
    self._modif = None
    self._columns = None

  @property
  def rank(self):
    return self._rank


  @property
  def quality(self):
    return self._quality


  @property
  def bmark(self):
    return self._bmark

  @property
  def objective_fun(self):
    return self._objective_fun

  @property
  def arco_indices(self):
    return self._arco_indices

  @property
  def jaunt_index(self):
    return self._jaunt_index

  @property
  def hw_env(self):
    return self._hw_env

  @property
  def math_env(self):
    return self._math_env

  @property
  def columns(self):
    return self._columns

  @property
  def varname(self):
    return self._varname

  @property
  def status(self):
    return self._status

  @property
  def out_file(self):
    return self._out_file

  @staticmethod
  def from_db_row(db,args):
    entry = OutputEntry(
      db=db,
      bmark=args['bmark'],
      arco_indices=[args['arco0'],args['arco1'], \
                  args['arco2'], args['arco3']],
      objective_fun=args['opt'],
      jaunt_index=args['jaunt'],
      math_env=args['menv'],
      hw_env=args['hwenv'],
      varname=args['varname']
    )
    entry._columns = args
    entry._out_file=args['out_file']
    entry._quality=args['quality']
    entry._rank=args['rank']
    entry._status=OutputStatus(args['status'])
    entry._modif=args['modif']
    entry._columns = args
    return entry

  def delete(self):
     self._db.delete_output(self._bmark,
                           self._arco_indices,
                           self._jaunt_index,
                           self._objective_fun,
                           self._math_env,
                           self._hw_env,
                           self._varname)

  def update_db(self,args):
    self._db.update_output(self._bmark,
                           self._arco_indices,
                           self._jaunt_index,
                           self._objective_fun,
                           self._math_env,
                           self._hw_env,
                           self._varname,
                           args)


  def set_status(self,new_status):
    assert(isinstance(new_status,OutputStatus))
    self.update_db({'status':new_status.value})
    self._status = new_status


  def set_rank(self,new_rank):
    if new_rank == float('inf'):
      new_rank = 1e9
    if new_rank == float('-inf'):
      new_rank = -1e9

    self.update_db({'rank':new_rank})
    self._rank = new_rank

  def set_quality(self,new_quality):
    self.update_db({'quality':new_quality})
    self._quality = new_quality



  @property
  def ident(self):
    return "%s(%s,%s,%s,%s,%s).%s" % (self._bmark,
                                         self._arco_indices,
                                         self._jaunt_index,
                                         self._objective_fun,
                                         self._math_env,
                                         self._hw_env,
                                         self._varname)
  def __repr__(self):
    s = "{\n"
    s += "ident=%s\n" % self.ident
    s += "status=%s\n" % (self._status.value)
    s += "out_file=%s\n" % (self._out_file)
    s += "rank=%s\n" % (self._rank)
    s += "quality=%s\n" % (self._quality)
    s += "}\n"
    return s



class ExperimentEntry:

  def __init__(self,db,bmark,arco_indices,jaunt_index,
               objective_fun,math_env,hw_env):
    self._bmark = bmark
    self._arco_indices = arco_indices
    self._jaunt_index = jaunt_index
    self._objective_fun = objective_fun
    self._math_env = math_env
    self._hw_env = hw_env
    self._grendel_file = None
    self._jaunt_circ_file = None
    self._skelt_circ_file = None
    self._rank= None
    self._energy= None
    self._runtime= None
    self._quality= None
    self._mismatch = None
    self._db = db
    self._columns = None

  @property
  def rank(self):
    return self._rank


  @property
  def runtime(self):
    return self._runtime


  @property
  def quality(self):
    return self._quality

  @property
  def columns(self):
    return self._columns


  @property
  def status(self):
    return self._status


  @property
  def bmark(self):
    return self._bmark


  @property
  def objective_fun(self):
    return self._objective_fun


  @property
  def math_env(self):
    return self._math_env


  @property
  def skelt_circ_file(self):
    return self._conc_circ_file



  @property
  def skelt_circ_file(self):
    return self._skelt_circ_file


  @property
  def jaunt_circ_file(self):
    return self._jaunt_circ_file

  @property
  def mismatch(self):
    return self._mismatch


  @property
  def grendel_file(self):
    return self._grendel_file

  def outputs(self):
    for outp in self._db.get_outputs(self._bmark, \
                         self._arco_indices,
                         self._jaunt_index,
                         self._objective_fun,
                         self._math_env,
                         self._hw_env):
      yield outp

  def synchronize(self):
    # delete if we're missing relevent files
    if not os.path.isfile(self.grendel_file) or \
       not os.path.isfile(self.skelt_circ_file) or \
       not os.path.isfile(self.jaunt_circ_file):
      self.delete()
      return

    clear_computed = False
    for output in self.outputs():
      if os.path.isfile(output.out_file):
        if output.status == OutputStatus.PENDING:
          output.set_status(OutputStatus.RAN)


    not_done = any(map(lambda out: out.status == OutputStatus.PENDING, \
                      self.outputs()))
    if not not_done:
      self.set_status(ExperimentStatus.RAN)
    else:
      self.set_status(ExperimentStatus.PENDING)

  def update_db(self,args):
    self._db.update_experiment(self._bmark,
                               self._arco_indices,
                               self._jaunt_index,
                               self._objective_fun,
                               self._math_env,
                               self._hw_env,
                               args)

  def set_status(self,new_status):
    assert(isinstance(new_status,ExperimentStatus))
    self.update_db({'status':new_status.value})
    self._status = new_status

  def set_mismatch(self,new_mismatch):
    assert(isinstance(new_mismatch,bool))
    if new_mismatch:
      self.update_db({'mismatch':1})
    else:
      self.update_db({'mismatch':0})
    self._mismatch = new_mismatch


  def set_rank(self,new_rank):
    if new_rank == float('inf'):
      new_rank = 1e9
    if new_rank == float('-inf'):
      new_rank = -1e9

    self.update_db({'rank':new_rank})
    self._rank = new_rank

  def set_quality(self,new_quality):
    self.update_db({'quality':new_quality})
    self._quality = new_quality

  def set_runtime(self,new_runtime):
    self.update_db({'runtime':new_runtime})
    self._runtime = new_runtime

  def delete(self):
    for outp in self.get_outputs():
      outp.delete()

    self._db.delete_experiment(self._bmark,
                               self._arco_indices,
                               self._jaunt_index,
                               self._objective_fun,
                               self._math_env,
                               self._hw_env)

  def get_outputs(self):
    return self._db.get_outputs(self._bmark, \
                                self._arco_indices,
                                self._jaunt_index,
                                self._objective_fun,
                                self._math_env, self._hw_env)

  @staticmethod
  def from_db_row(db,args):
    entry = ExperimentEntry(
      db=db,
      bmark=args['bmark'],
      arco_indices=[args['arco0'],args['arco1'], \
                  args['arco2'], args['arco3']],
      objective_fun=args['opt'],
      jaunt_index=args['jaunt'],
      math_env=args['menv'],
      hw_env=args['hwenv']
    )

    entry._grendel_file,=args['grendel_file'],
    entry._jaunt_circ_file,=args['jaunt_circ_file'],
    entry._skelt_circ_file,=args['skelt_circ_file'],
    entry._rank=args['rank']
    entry._quality=args['quality']
    entry._energy=args['energy']
    entry._runtime=args['runtime']
    entry._status=ExperimentStatus(args['status'])
    entry._modif = args['modif']
    entry._mismatch = True if args['mismatch'] == 1 else False
    entry._columns = args
    return entry

  @property
  def ident(self):
    return "%s(%s,%s,%s,%s,%s)" % (self._bmark,
                                         self._arco_indices,
                                         self._jaunt_index,
                                         self._objective_fun,
                                         self._math_env,
                                         self._hw_env)
 
  def __repr__(self):
    s = "{\n"
    s += "ident=%s\n" % (self.ident)
    s += "status=%s\n" % (self._status.value)
    s += "grendel_file=%s\n" % (self._grendel_file)
    s += "skelt_circ=%s\n" % (self._skelt_circ_file)
    s += "jaunt_circ=%s\n" % (self._jaunt_circ_file)
    s += "rank=%s\n" % (self._rank)
    s += "energy=%s\n" % (self._energy)
    s += "runtime=%s\n" % (self._runtime)
    s += "quality=%s\n" % (self._quality)
    s += "}\n"
    return s



class ExperimentDB:

  def __init__(self):
    path = cfg.EXPERIMENT_DB
    self._conn = sqlite3.connect(path)
    self._curs = self._conn.cursor()
    cmd = '''CREATE TABLE IF NOT EXISTS experiments
             (bmark text NOT NULL,
              status text NOT NULL,
              modif timestamp,
              arco0 int NOT NULL,
              arco1 int NOT NULL,
              arco2 int NOT NULL,
              arco3 int NOT NULL,
              jaunt int NOT NULL,
              opt text NOT NULL,
              menv text NOT NULL,
              hwenv text NOT NULL,
              grendel_file text,
              jaunt_circ_file text,
              skelt_circ_file text,
              rank real,
              mismatch int,
              quality real,
              energy real,
              runtime real,
              PRIMARY KEY (bmark,arco0,arco1,
                           arco2,arco3,jaunt,
                           opt,menv,hwenv)
             );
    '''
    self._experiment_order = ['bmark','status','modif','arco0', \
                              'arco1','arco2', \
                              'arco3','jaunt','opt','menv','hwenv',
                              'grendel_file', \
                              'jaunt_circ_file',
                              'skelt_circ_file','rank','mismatch',
                              'quality', \
                              'energy','runtime']

    self._experiment_modifiable =  \
                                   ['rank','status','modif','quality', \
                                    'energy','runtime','mismatch']
    self._curs.execute(cmd)

    cmd = '''CREATE TABLE IF NOT EXISTS outputs( bmark text NULL,
    status text NOT NULL,
    arco0 int NOT NULL,
    arco1 int NOT NULL,
    arco2 int NOT NULL,
    arco3 int NOT NULL,
    jaunt int NOT NULL,
    opt text NOT NULL,
    menv text NOT NULL,
    hwenv text NOT NULL,
    varname text NOT NULL,
    out_file text,
    rank real,
    quality real,
    modif timestamp,
    PRIMARY KEY (bmark,arco0,arco1,arco2,arco3,jaunt,
                 opt,menv,hwenv,varname)
    FOREIGN KEY (bmark,arco0,arco1,arco2,arco3,jaunt,opt,menv,hwenv)
    REFERENCES experiments(bmark,arco0,arco1,arco2,arco3,jaunt,
                           opt,menv,hwenv)
    )
    '''
    self._output_order = ['bmark','status','arco0', \
                          'arco1','arco2', \
                          'arco3','jaunt','opt','menv','hwenv',
                          'varname','out_file', \
                          'rank','quality','modif']

    self._output_modifiable = ['quality','modif','status','rank']
    self._curs.execute(cmd)
    self._conn.commit()


  def _get_output_rows(self,where_clause):
    cmd = '''SELECT * FROM outputs {where_clause}'''
    conc_cmd = cmd.format(where_clause=where_clause)
    for values in list(self._curs.execute(conc_cmd)):
      assert(len(values) == len(self._output_order))
      args = dict(zip(self._output_order,values))
      yield OutputEntry.from_db_row(self,args)


  def _get_experiment_rows(self,where_clause):
    cmd = '''SELECT * FROM experiments {where_clause}'''
    conc_cmd = cmd.format(where_clause=where_clause)
    for values in list(self._curs.execute(conc_cmd)):
      assert(len(values) == len(self._experiment_order))
      args = dict(zip(self._experiment_order,values))
      yield ExperimentEntry.from_db_row(self,args)


  def get_all(self):
    for entry in self._get_experiment_rows(""):
      yield entry

  def get_by_status(self,status):
    assert(isinstance(status,ExperimentStatus))
    where_clause = "WHERE status=\"%s\"" % status.value
    for entry in self._get_experiment_rows(where_clause):
      yield entry

  def to_where_clause(self,bmark,arco_inds,jaunt_inds,opt, \
                      menv_name,hwenv_name,varname=None):
    cmd = '''WHERE bmark = "{bmark}"
    AND arco0 = {arco0}
    AND arco1 = {arco1}
    AND arco2 = {arco2}
    AND arco3 = {arco3}
    AND jaunt = {jaunt}
    AND opt = "{opt}"
    AND menv = "{menv}"
    AND hwenv = "{hwenv}"
    '''
    args = make_args(bmark,arco_inds,jaunt_inds,opt, \
                     menv_name,hwenv_name)
    if not varname is None:
      cmd += "AND varname = \"{varname}\""
      args['varname'] = varname

    conc_cmd = cmd.format(**args)
    return conc_cmd

  def update_output(self,bmark,arco_inds,jaunt_inds,opt, \
                    menv_name,hwenv_name,varname,new_fields):
    cmd = '''
    UPDATE outputs
    SET {assign_clause} {where_clause};
    '''
    where_clause = self.to_where_clause(bmark,\
                                        arco_inds,jaunt_inds,opt, \
                                        menv_name,hwenv_name,
                                        varname=varname)
    new_fields['modif'] = datetime.datetime.now()
    assign_subclauses = []
    for field,value in new_fields.items():
      assert(field in self._output_modifiable)
      if field == 'modif' or field == 'status':
        subcmd = "%s=\"%s\"" % (field,value)
      else:
        subcmd = "%s=%s" % (field,value)
      assign_subclauses.append(subcmd)

    assign_clause = ",".join(assign_subclauses)
    conc_cmd = cmd.format(where_clause=where_clause, \
                          assign_clause=assign_clause)
    self._curs.execute(conc_cmd)
    self._conn.commit()


  def update_experiment(self,bmark,arco_inds,jaunt_inds,opt,menv_name,hwenv_name,new_fields):
    cmd = '''
    UPDATE experiments
    SET {assign_clause} {where_clause};
    '''
    where_clause = self.to_where_clause(bmark,\
                                        arco_inds,jaunt_inds,opt, \
                                        menv_name,hwenv_name)
    new_fields['modif'] = datetime.datetime.now()
    assign_subclauses = []
    for field,value in new_fields.items():
      assert(field in self._experiment_modifiable)
      if field == 'modif' or field == 'status':
        subcmd = "%s=\"%s\"" % (field,value)
      else:
        subcmd = "%s=%s" % (field,value)
      assign_subclauses.append(subcmd)

    assign_clause = ",".join(assign_subclauses)
    conc_cmd = cmd.format(where_clause=where_clause, \
                          assign_clause=assign_clause)
    self._curs.execute(conc_cmd)
    self._conn.commit()


  def get_outputs(self,bmark,arco_inds,jaunt_inds,opt,menv_name,hwenv_name):
    cmd = '''
     SELECT *
     FROM outputs
     {where_clause};
    '''
    where_clause = self.to_where_clause(bmark,\
                                        arco_inds,jaunt_inds,opt, \
                                        menv_name,hwenv_name)
    for entry in self._get_output_rows(where_clause):
      yield entry

  def filter_experiments(self,filt):
    for entry in self.get_all():
      args = entry.columns
      skip = False
      for k,v in args.items():
        if k in filt and v != filt[k]:
          skip = True
      if skip:
        continue
      yield entry



  def delete(self,bmark=None,objfun=None):
    assert(not bmark is None or not objfun is None)
    if not bmark is None and not objfun is None:
      itertr= self.filter_experiments({'bmark':bmark,'opt':objfun})
    elif not objfun is None:
      itertr= self.filter_experiments({'opt':objfun})
    elif not bmark is None:
      itertr= self.filter_experiments({'bmark':bmark})
    else:
      raise Exception("???")

    for entry in itertr:
      entry.delete()
      yield entry

  def get_experiment(self,bmark,arco_inds,jaunt_inds,opt,menv_name,hwenv_name):
    where_clause = self.to_where_clause(bmark,\
                                        arco_inds,jaunt_inds,opt, \
                                        menv_name,hwenv_name)
    result = list(self._get_experiment_rows(where_clause))
    if len(result) == 0:
      return None
    elif len(result) == 1:
      return result[0]
    else:
      raise Exception("nonunique experiment")

  def delete_output(self,bmark,arco_inds,jaunt_inds, \
                    opt,menv_name,hwenv_name,output):
    cmd = '''
    DELETE FROM outputs {where_clause};
    '''
    where_clause = self.to_where_clause(bmark,\
                                        arco_inds,jaunt_inds,opt, \
                                        menv_name,hwenv_name,
                                        varname=output)
    conc_cmd = cmd.format(where_clause=where_clause)
    self._curs.execute(conc_cmd)
    self._conn.commit()


  def delete_experiment(self,bmark,arco_inds,jaunt_inds, \
                    opt,menv_name,hwenv_name):
    cmd = '''
    DELETE FROM experiments {where_clause};
    '''
    where_clause = self.to_where_clause(bmark,\
                                        arco_inds,jaunt_inds,opt, \
                                        menv_name,hwenv_name)
    conc_cmd = cmd.format(where_clause=where_clause)
    self._curs.execute(conc_cmd)
    self._conn.commit()




  def add_output(self,path_handler,bmark,arco_inds, \
                 jaunt_inds, \
                 opt, \
                 menv_name,hwenv_name,output):
    cmd = '''
      INSERT INTO outputs (
         bmark,arco0,arco1,arco2,arco3,jaunt,
         opt,menv,hwenv,out_file,status,modif,varname
      ) VALUES
      (
         "{bmark}",{arco0},{arco1},{arco2},{arco3},{jaunt},
         "{opt}","{menv}","{hwenv}",
         "{out_file}",
         "{status}",
         "{modif}",
         "{varname}"
      )
      '''
    args = make_args(bmark,arco_inds,jaunt_inds,opt, \
                     menv_name,hwenv_name)
    args['modif'] = datetime.datetime.now()
    args['status'] = OutputStatus.PENDING.value
    args['varname'] = output
    args['out_file'] = path_handler.measured_waveform_file(bmark,arco_inds, \
                                                           jaunt_inds, \
                                                           opt,menv_name, \
                                                           hwenv_name, \
                                                           output)
    conc_cmd = cmd.format(**args)
    self._curs.execute(conc_cmd)
    self._conn.commit()

  def add_experiment(self,path_handler,bmark,arco_inds, \
                     jaunt_inds, \
                     opt, \
                     menv_name,hwenv_name):
    entry = self.get_experiment(bmark,arco_inds,jaunt_inds, \
                                opt,menv_name,hwenv_name)
    if entry is None:
      cmd = '''
      INSERT INTO experiments (
         bmark,arco0,arco1,arco2,arco3,jaunt,
         opt,menv,hwenv,jaunt_circ_file,skelt_circ_file,
         grendel_file,status,modif,mismatch
      ) VALUES
      (
         "{bmark}",{arco0},{arco1},{arco2},{arco3},{jaunt},
         "{opt}","{menv}","{hwenv}",
         "{conc_circ}",
         "{skelt_circ}",
         "{grendel_file}",
         "{status}",
         "{modif}",{mismatch}
      )
      '''
      args = make_args(bmark,arco_inds,jaunt_inds,opt, \
                       menv_name,hwenv_name)
      args['modif'] = datetime.datetime.now()
      args['status'] = ExperimentStatus.PENDING.value
      args['grendel_file'] = path_handler.grendel_file(bmark,arco_inds, \
                                                    jaunt_inds, opt,
                                                    menv_name,
                                                    hwenv_name)
      args['conc_circ'] = path_handler.conc_circ_file(bmark,arco_inds, \
                                                    jaunt_inds,
                                                    opt)
      args['skelt_circ'] = path_handler.skelt_circ_file(bmark,arco_inds, \
                                                    jaunt_inds,
                                                    opt)

      # not mismatched
      args['mismatch'] = 0
      conc_cmd = cmd.format(**args)
      self._curs.execute(conc_cmd)
      self._conn.commit()
      entry = self.get_experiment(bmark,arco_inds,jaunt_inds, \
                                  opt,menv_name,hwenv_name)
      for out_file in get_output_files(args['grendel_file']):
        _,_,_,_,_,_,var_name = path_handler \
                               .measured_waveform_file_to_args(out_file)
        self.add_output(path_handler,bmark,arco_inds,jaunt_inds,opt, \
                        menv_name,hwenv_name,var_name)

      entry.synchronize()
      return entry

  def scan(self):
    for name in diffeqs.get_names():
      ph = paths.PathHandler('default',name,make_dirs=False)
      grendel_dir = ph.grendel_file_dir()
      for dirname, subdirlist, filelist in os.walk(grendel_dir):
        for fname in filelist:
          if fname.endswith('.grendel'):
            bmark,arco_inds,jaunt_inds,opt,menv_name,hwenv_name = \
                                    ph.grendel_file_to_args(fname)
            exp = self.add_experiment(ph,bmark,arco_inds,jaunt_inds, \
                                      opt,menv_name,hwenv_name)
            if not exp is None:
              yield exp