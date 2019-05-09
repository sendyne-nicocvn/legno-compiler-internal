import lab_bench.lib.enums as enums
import lab_bench.lib.chipcmd.data as chipdata
import lab_bench.lib.chipcmd.state as chipstate
from lab_bench.lib.chipcmd.data import *
from enum import Enum
import sqlite3
import util.config as CFG
import json
import binascii

class BlockStateDatabase:

  def __init__(self):
    path = CFG.STATE_DB
    self._conn = sqlite3.connect(path)
    self._curs = self._conn.cursor()

    cmd = '''
    CREATE TABLE IF NOT EXISTS states (
    cmdkey text NOT NULL,
    block text NOT NULL,
    state text NOT NULL,
    PRIMARY KEY (cmdkey)
    )
    '''
    self._curs.execute(cmd)
    self._conn.commit()
    self.keys = ['cmdkey','block','state']

  def get_all(self):
    cmd = "SELECT * from states;"
    for values in self._curs.execute(cmd):
      yield dict(zip(self.keys,values))

  def put(self,blockstate):
    assert(isinstance(blockstate,BlockState))
    key = blockstate.key.to_key()
    value = blockstate.to_cstruct()
    cmd = '''DELETE FROM states WHERE cmdkey="{cmdkey}"''' \
      .format(cmdkey=key)
    self._curs.execute(cmd)
    self._conn.commit()
    bits = value.hex()
    cmd = '''
    INSERT INTO states (cmdkey,block,state)
    VALUES ("{cmdkey}","{block}","{state}")
    '''.format(
      cmdkey=key,
      block=blockstate.block.value,
      state=bits
    )
    self._curs.execute(cmd)
    self._conn.commit()

  def get(self,blktype,loc,blockkey):
    assert(isinstance(blockkey,BlockState.Key))
    keystr = blockkey.to_key()
    for entry in self.get_all():
      print(entry['cmdkey'])
    print("==========")
    print(keystr)
    cmd = '''SELECT * FROM states WHERE cmdkey = "{cmdkey}"''' \
                                                .format(cmdkey=keystr)
    results = list(self._curs.execute(cmd))
    assert(len(results) == 1)
    state = dict(zip(self.keys,results[0]))['state']
    obj = chipstate.BlockState \
                   .toplevel_from_cstruct(blktype,loc,
                                          bytes.fromhex(state))
    print(obj)
    return obj

class BlockState:

  class Key:
    def __init__(self,blk,loc):
      self.block = blk
      self.loc = loc

    def to_json(self):
      return self.__dict__

    def to_key(self):
      obj = self.to_json()
      def dict_to_key(obj):
        keys = list(obj.keys())
        sorted(keys)
        ident = ""
        for key in keys:
          value = obj[key]
          ident += "%s=" % key
          if isinstance(value,dict):
            ident += "{%s}" % dict_to_key(value)
          elif isinstance(value,float):
            ident += "%.3f" % value
          elif isinstance(value,Enum):
            ident += "%s" % obj[key].name
          else:
            ident += str(value)
          ident += ";"
        return ident

      return dict_to_key(obj)

  def __init__(self,block_type,loc,state):
    self.block = block_type
    self.loc = loc
    if state != None:
      self.from_cstruct(state)

  @staticmethod
  def toplevel_from_cstruct(blk,loc,data):
    pad = bytes([0]*(24-len(data)))
    typ = cstructs.state_t()
    obj = typ.parse(data+pad)
    if blk == enums.BlockType.FANOUT:
      st = FanoutBlockState(loc,obj.fanout)
      print(obj.fanout)
    elif blk == enums.BlockType.INTEG:
      st = IntegBlockState(loc,obj.integ)
      print(obj.integ)
    elif blk == enums.BlockType.MULT:
      st = MultBlockState(loc,obj.mult)
      print(obj.mult)
    elif blk == enums.BlockType.DAC:
      st = DacBlockState(loc,obj.dac)
      print(obj.dac)
    elif blk == enums.BlockType.ADC:
      st = AdcBlockState(loc,obj.adc)
      print(obj.adc)
    else:
      raise Exception("unimplemented block : <%s>" \
                      % blk.name)
    return st

  @property
  def key(self):
    raise NotImplementedError

  def from_cstruct(self,state):
    raise NotImplementedError

  def to_cstruct(self):
    raise NotImplementedError


  def __repr__(self):
    s = ""
    for k,v in self.__dict__.items():
      s += "%s=%s\n" % (k,v)
    return s

class DacBlockState(BlockState):

  class Key(BlockState.Key):

    def __init__(self,loc,inv,rng,source,const_val):
      BlockState.Key.__init__(self,enums.BlockType.DAC,loc)
      self.inv = inv
      self.rng = rng
      self.source = source
      self.const_val = const_val


  def __init__(self,loc,state):
    BlockState.__init__(self,enums.BlockType.DAC,loc,state)

  @property
  def key(self):
    return DacBlockState.Key(self.loc,
                             self.inv,
                             self.rng,
                             self.source,
                             self.const_val)


  def to_cstruct(self):
    return cstructs.state_t().build({
      "dac": {
        "enable": True,
        "inv": self.inv.code(),
        "range": self.rng.code(),
        "source": self.source.code(),
        "pmos": self.pmos,
        "nmos": self.nmos,
        "gain_cal": self.gain_cal,
        "const_code": self.const_code,
        "const_val": self.const_val
      }
    })

  def from_cstruct(self,state):
    self.enable = chipdata.BoolType(state.enable)
    self.inv = chipdata.SignType(state.inv)
    self.rng = chipdata.RangeType(state.range)
    self.source = chipdata.DACSourceType(state.source)
    self.pmos = state.pmos
    self.nmos = state.nmos
    self.gain_cal = state.gain_cal
    self.const_code = state.const_code
    self.const_val = state.const_val

def to_c_list(keymap):
  intmap = {}
  for k,v in keymap.items():
    print("%s=%s" % (k,v))
    intmap[k.code()] = v.code()

  n = max(intmap.keys())
  buf = [0]*(n+1)
  for k,v in intmap.items():
    buf[k] = v
  return buf


class MultBlockState(BlockState):

  class Key(BlockState.Key):

    def __init__(self,loc,
                 vga,
                 invs,
                 ranges,
                 gain_val=None):
      BlockState.Key.__init__(self,enums.BlockType.MULT,loc)
      assert(isinstance(vga,chipdata.BoolType))
      self.invs = invs
      self.ranges = ranges
      self.gain_val = gain_val
      self.vga = vga

  def __init__(self,loc,state):
    BlockState.__init__(self,enums.BlockType.MULT,loc,state)

  def to_cstruct(self):
    return cstructs.state_t().build({
      "mult": {
        "vga": self.vga.code(),
        "enable": chipdata.BoolType.TRUE.code(),
        "inv": to_c_list(self.invs),
        "range": to_c_list(self.ranges),
        "pmos": self.pmos,
        "nmos": self.nmos,
        "port_cal": list(map(lambda c: c.code(), self.port_cals)),
        "gain_cal": self.gain_cal,
        "gain_code": self.gain_code,
        "gain_val": self.gain_val
      }
    })

  @property
  def key(self):
    return MultBlockState.Key(self.loc,
                              self.vga,
                              self.invs,
                              self.ranges,
                              self.gain_val)

  def from_cstruct(self,state):
    in0id = enums.PortName.IN0
    in1id = enums.PortName.IN1
    outid = enums.PortName.OUT0
    self.enable = chipdata.BoolType(state.enable)
    self.vga = chipdata.BoolType(state.vga)
    self.invs = {}
    self.invs[in0id] = chipdata.SignType(state.inv[in0id.code()])
    self.invs[in1id] = chipdata.SignType(state.inv[in1id.code()])
    self.invs[outid] = chipdata.SignType(state.inv[outid.code()])

    self.ranges = {}
    self.ranges[in0id] = chipdata.RangeType(state.range[in0id.code()])
    self.ranges[in1id] = chipdata.RangeType(state.range[in1id.code()])
    self.ranges[outid] = chipdata.RangeType(state.range[outid.code()])

    self.gain_val = state.gain_val

    self.pmos = state.pmos
    self.nmos = state.nmos
    self.port_cals = {}
    self.port_cals[in0id] = state.port_cal[in0id.code()]
    self.port_cals[in1id] = state.port_cal[in1id.code()]
    self.port_cals[outid] = state.port_cal[outid.code()]
    self.gain_cal = state.gain_cal
    self.gain_code = state.gain_code



class IntegBlockState(BlockState):

  class Key(BlockState.Key):

    def __init__(self,loc,
                 exception,
                 invs,
                 ranges,
                 ic_val=None):
      BlockState.Key.__init__(self,enums.BlockType.INTEG,loc)
      self.exception = exception
      self.invs = invs
      self.ranges = ranges
      self.ic_val = ic_val

  def __init__(self,loc,state):
    BlockState.__init__(self,enums.BlockType.INTEG,loc,state)

  @property
  def key(self):
    return IntegBlockState.Key(self.loc,
                              self.exception,
                              self.invs,
                              self.ranges,
                              self.ic_val)

  def from_cstruct(self,state):
    inid = enums.PortName.IN0
    outid = enums.PortName.OUT0

    self.enable = chipdata.BoolType(state.enable)
    self.exception = chipdata.BoolType(state.exception)

    self.invs = {}
    self.invs[inid] = chipdata.SignType(state.inv[inid.code()])
    self.invs[outid] = chipdata.SignType(state.inv[outid.code()])

    self.ranges = {}
    self.ranges[inid] = chipdata.RangeType(state.range[inid.code()])
    self.ranges[outid] = chipdata.RangeType(state.range[outid.code()])

    self.ic_val = state.ic_val

    self.pmos = state.pmos
    self.nmos = state.nmos
    self.port_cals = {}
    self.port_cals[inid] = state.port_cal[inid.code()]
    self.port_cals[outid] = state.port_cal[outid.code()]
    self.ic_cal = state.ic_cal
    self.ic_code = state.ic_code



class FanoutBlockState(BlockState):

  class Key(BlockState.Key):

    def __init__(self,loc,
                 third,
                 invs,
                 rng):
      BlockState.Key.__init__(self,enums.BlockType.FANOUT,loc)
      self.invs = invs
      self.rng = rng
      self.third = third

  def __init__(self,loc,state):
    BlockState.__init__(self,enums.BlockType.FANOUT,loc,state)


  @property
  def key(self):
    return FanoutBlockState.Key(self.loc,
                                self.third,
                                self.invs, \
                                self.rng)

  def from_cstruct(self,state):
    inid = enums.PortName.IN0
    out0id = enums.PortName.OUT0
    out1id = enums.PortName.OUT1
    out2id = enums.PortName.OUT2

    self.enable = chipdata.BoolType(state.enable)
    self.third = chipdata.BoolType(state.third)

    self.rng = chipdata.RangeType(state.range[inid.code()])
    self.invs = {}
    for ident in [out0id,out1id,out2id]:
      self.invs[ident] = chipdata.SignType(state.inv[ident.code()])


    self.pmos = state.pmos
    self.nmos = state.nmos

    self.port_cals = {}
    for ident in [out0id,out1id,out2id]:
      self.port_cals[ident] = state.port_cal[ident.code()]



class AdcBlockState(BlockState):

  class Key(BlockState.Key):

    def __init__(self,loc,
                 test_en,
                 test_adc,
                 test_i2v,
                 test_rs,
                 test_rsinc,
                 inv,
                 rng):
      BlockState.Key.__init__(self,enums.BlockType.ADC,loc)
      self.test_en = test_en
      self.test_adc = test_adc
      self.test_i2v = test_i2v
      self.test_rs = test_rs
      self.test_rsinc = test_rsinc
      self.inv = inv
      self.rng = rng

  def __init__(self,loc,state):
    BlockState.__init__(self,enums.BlockType.ADC,loc,state)

  @property
  def key(self):
    return AdcBlockState.Key(self.loc,
                             self.test_en,
                             self.test_adc,
                             self.test_i2v,
                             self.test_rs,
                             self.test_rsinc,
                             self.inv,
                             self.rng
    )

  def from_cstruct(self,state):
    inid = enums.PortName.IN0
    outid = enums.PortName.OUT0

    self.test_en = chipdata.BoolType(state.test_en)
    self.test_adc = chipdata.BoolType(state.test_adc)
    self.test_i2v = chipdata.BoolType(state.test_i2v)
    self.test_rs = chipdata.BoolType(state.test_rs)
    self.test_rsinc = chipdata.BoolType(state.test_rsinc)
    self.enable = chipdata.BoolType(state.enable)
    self.inv = chipdata.SignType(state.inv)


    self.pmos = state.pmos
    self.nmos = state.nmos
    self.pmos2 = state.pmos2
    self.i2v_cal = state.i2v_cal
    self.upper_fs = state.upper_fs
    self.lower_fs = state.lower_fs
    self.upper = state.upper
    self.lower = state.lower
    self.rng = chipdata.RangeType(state.range)
