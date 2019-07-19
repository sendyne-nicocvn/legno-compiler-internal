import lab_bench.lib.enums as enums
import lab_bench.lib.cstructs as cstructs
from lab_bench.lib.base_command import Command,AnalogChipCommand
from lab_bench.lib.chipcmd.data import CircLoc
from lab_bench.lib.chipcmd.common import *
import lab_bench.lib.chipcmd.state as chipstate
import json
import struct
import os
import random
import matplotlib.pyplot as plt
from matplotlib import gridspec


class ExecuteInput(AnalogChipCommand):

    def __init__(self,blk,chip,tile,slce, \
                 inputs, \
                 index=None, \
                 mode=0):
        AnalogChipCommand.__init__(self)
        self._blk = enums.BlockType(blk)
        self._loc = CircLoc(chip,tile,slce,index=0 if index is None \
                            else index)
        self._inputs = inputs
        self._mode = mode
        self.test_loc(self._blk, self._loc)

    def build_ctype(self):
        loc_type = self._loc.build_ctype()
        return build_circ_ctype({
            'type':enums.CircCmdType.CHARACTERIZE.name,
            'data':{
                'prof':{
                  'blk': self._blk.code(),
                  'loc': loc_type,
                  'in0': self._inputs[0],
                  'in1': self._inputs[1] if len(self._inputs) > 1 else 0.0,
                  'mode': self._mode
                }
            }
        })

    def execute_command(self,env):
      resp = ArduinoCommand.execute_command(self,env)
      result_size = int(resp.data(0)[0])
      state_size = int(resp.data(0)[1])
      base = 2
      result_data = bytes(resp.data(0)[base:(base+result_size)])
      result = cstructs.profile_t() \
                       .parse(result_data);

      state_data = bytes(resp.data(0)[(base+state_size):])
      st = chipstate.BlockState \
                    .toplevel_from_cstruct(self._blk,
                                           self._loc,
                                           state_data,
                                           targeted=False)
      print(result)
      bias = result.bias
      noise = result.noise
      out = result.output
      in0 = result.input0
      in1 = result.input1
      port = enums.PortName.from_code(result.port)
      prof = {
          'bias':bias,
          'noise':noise,
          'mode':result.mode,
          'out':out,
          'in0':in0,
          'in1':in1,
          'port':port
      }
      print(prof)
      return st,prof



def sample_reverse_normal():
    z_inv = np.random.normal(0,0.8)
    while abs(z_inv) > 1.0:
        z_inv = np.random.normal(0,0.5)

    if z_inv < 0:
        z = -1.0 - z_inv
    else:
        z = 1.0 - z_inv

    return z

class ProfileCmd(Command):

    def __init__(self,blk,chip,tile,slce, \
                 index=None,clear=False,bootstrap=False,n=5):
        AnalogChipCommand.__init__(self)
        self._blk = enums.BlockType(blk)
        self._loc = CircLoc(chip,tile,slce,index)
        self._clear = clear
        self._n = n
        self._max_n = 500
        self._bootstrap=bootstrap
        if self._blk == enums.BlockType.MULT:
          self._n_inputs = 2
        else:
          self._n_inputs = 1

    @staticmethod
    def name():
        return 'profile'

    def get_output(self,env,inputs,mode=0):
        print("PROFILE inputs=%s mode=%d" % (inputs,mode))
        cmd = ExecuteInput(self._blk, \
                           self._loc.chip, \
                           self._loc.tile, \
                           self._loc.slice, \
                           index=self._loc.index, \
                           inputs=inputs,
                           mode=mode)
        state,profile = cmd.execute(env)
        n = self.update_database(env,state,profile)
        return n >= self._max_n

    def clear_database(self,env,state):
        entry = env.state_db.get(state.key)
        env.state_db.put(state,entry.targeted,
                         profile=[],
                         success=entry.success,
                         max_error=entry.tolerance)

    def update_database(self,env,state,profile):
        entry = env.state_db.get(state.key)
        if self._clear:
            print("-> clear database")
            self.clear_database(env,state)
            entry.profile = []
            self._clear = False

        env.state_db.put(state,entry.targeted,
                         profile=[profile] + entry.profile,
                         success=entry.success,
                         max_error=entry.tolerance)
        return len(entry.profile+[profile])

    def insert_result(self,env,resp):
        title = "profiled %s.%s " % (self._blk,self._loc)
        send_mail(title,log)
        return True


    def execute_command(self,env):
      if self._n_inputs == 1:
        if self._blk == enums.BlockType.INTEG:
            if self._bootstrap:
                for x0 in [0]:
                    if self.get_output(env,[x0],mode=0):
                        break



            for i in range(0,self._n):
                x0 = sample_reverse_normal()
                if self.get_output(env,[x0],mode=0):
                    break

            if self._bootstrap:
                for x0 in [0]:
                    if self.get_output(env,[x0],mode=1):
                        return

            for i in range(0,self._n):
                x0 = sample_reverse_normal()
                if self.get_output(env,[x0],mode=1):
                    return

        elif self._blk == enums.BlockType.FANOUT:
            if self._bootstrap:
                for x0 in [0]:
                    succ=self.get_output(env,[x0],mode=0)
                    succ&=self.get_output(env,[x0],mode=1)
                    succ&=self.get_output(env,[x0],mode=2)
                    if succ:
                        return

            for i in range(0,self._n):
                x0 = sample_reverse_normal()
                succ = self.get_output(env,[x0],mode=0)
                succ &= self.get_output(env,[x0],mode=1)
                succ &= self.get_output(env,[x0],mode=2)
                if succ:
                    return
        else:
            for i in range(0,self._n):
                x0 = sample_reverse_normal()
                if self.get_output(env,[x0],mode=0):
                    return

      elif self._n_inputs == 2:
          if self._bootstrap:
            for x0,x1 in [(0,0)]:
                if self.get_output(env,[x0,x1],mode=0):
                    return

          for i in range(0,self._n):
              print(">>> profiling operation %d/%d <<<" \
                    % (i+1,self._n))
              z = sample_reverse_normal()
              x0 = random.uniform(-1,1)
              while abs(z/x0) > 1.0:
                  z = sample_reverse_normal()
                  x0 = random.uniform(-1,1)

              x1 = z/x0
              self.get_output(env,[x0,x1],mode=0)
              print("%f*%f" % (x0,x1))

      else:
        raise Exception("profiling eliminated")


    @staticmethod
    def parse(args):
        result = parse_pattern_block_loc(args,ProfileCmd.name(),
                                         targeted=True)
        if result.success:
            data = result.value
            return CharacterizeCmd(data['blk'],
                                   data['chip'],
                                   data['tile'],
                                   data['slice'],
                                   data['index'],
                                   targeted=data['targeted'])

        else:
            print(result.message)
            raise Exception("<parse_failure>: %s" % args)



