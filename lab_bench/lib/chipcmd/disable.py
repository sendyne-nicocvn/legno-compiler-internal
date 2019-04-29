import lab_bench.lib.enums as enums
from lab_bench.lib.chipcmd.data import CircLoc
from lab_bench.lib.base_command import AnalogChipCommand
from lab_bench.lib.chipcmd.common import *

class DisableCmd(AnalogChipCommand):

    def __init__(self,block,chip,tile,slice,index=None):
        AnalogChipCommand.__init__(self)
        self._block = enums.BlockType(block);
        self._loc = CircLoc(chip,tile,slice,index)
        self.test_loc(self._block,self._loc)

    def disable():
        return self

    def __eq__(self,other):
        if isinstance(other,DisableCmd):
            return self._loc == other._loc and \
                self._block.name == other._block.name
        else:
            return False

    def __hash__(self):
        return hash(str(self))

    @staticmethod
    def name():
        return 'disable'

    @staticmethod
    def desc():
        return "disable a block on the hdacv2 board"


    def build_ctype(self):
        if self._block == enums.BlockType.DAC:
            return build_circ_ctype({
                'type':enums.CircCmdType.DISABLE_DAC.name,
                'data':{
                    'circ_loc':self._loc.build_ctype()
                }
            })
        if self._block == enums.BlockType.LUT:
            return build_circ_ctype({
                'type':enums.CircCmdType.DISABLE_LUT.name,
                'data':{
                    'circ_loc':self._loc.build_ctype()
                }
            })

        if self._block == enums.BlockType.ADC:
            return build_circ_ctype({
                'type':enums.CircCmdType.DISABLE_ADC.name,
                'data':{
                    'circ_loc':self._loc.build_ctype()
                }
            })

        elif self._block == enums.BlockType.MULT:
            return build_circ_ctype({
                'type':enums.CircCmdType.DISABLE_MULT.name,
                'data':{
                    'circ_loc_idx1':self._loc.build_ctype()
                }
            })
        elif self._block == enums.BlockType.FANOUT:
            return build_circ_ctype({
                'type':enums.CircCmdType.DISABLE_FANOUT.name,
                'data':{
                    'circ_loc_idx1':self._loc.build_ctype()
                }
            })
        elif self._block == enums.BlockType.INTEG:
            return build_circ_ctype({
                'type':enums.CircCmdType.DISABLE_INTEG.name,
                'data':{
                    'circ_loc':self._loc.build_ctype()
                }
            })
        elif self._block == enums.BlockType.LUT:
            return build_circ_ctype({
                'type':enums.CircCmdType.DISABLE_LUT.name,
                'data':{
                    'circ_loc':self._loc.build_ctype()
                }
            })
        else:
            print("no disable command <%s>" % self._block)
            return None


    def parse(args):
        result1 = parse_pattern_block(args[1:],0,0,0,
                                      "disable %s" % args[0],
                                      index=True)
        result2 = parse_pattern_block(args[1:],0,0,0,
                                      "disable %s" % args[0],
                                      index=False)

        if not result1 is None:
            return DisableCmd(args[0],
                              result1['chip'],
                              result1['tile'],
                              result1['slice'],
                              result1['index'])
        if not result2 is None:
            return DisableCmd(args[0],
                              result2['chip'],
                              result2['tile'],
                              result2['slice'])

    def __repr__(self):
        return "disable %s.%s" % (self._loc,self._block)
