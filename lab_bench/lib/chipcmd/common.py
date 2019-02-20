import parse as parselib
import numpy as np
from lab_bench.lib.chipcmd.data import *
import lab_bench.lib.cstructs as cstructs
from lab_bench.lib.base_command import OptionalValue

def build_circ_ctype(circ_data):
    return {
        'test':ArduinoCommand.DEBUG,
        'type':enums.CmdType.CIRC_CMD.name,
        'data': {
            'circ_cmd':circ_data
        }
    }

def signed_float_to_byte(fvalue):
    assert(fvalue <= 1.0 and fvalue <= 1.0)
    value = int((fvalue+1.0)/2.0*255)
    assert(value >= 0 and value <= 255)
    return value

def float_to_byte(fvalue):
    assert(fvalue >= 0.0 and fvalue <= 1.0)
    value = int(fvalue*255)
    assert(value >= 0 and value <= 255)
    return value

def parse_pattern_conn(args,name):
    line = " ".join(args)

    src_cmds = [
        '{sblk:w} {schip:d} {stile:d} {sslice:d} {sindex:d} port {sport:d}',
        '{sblk:w} {schip:d} {stile:d} {sslice:d} port {sport:d}',
        '{sblk:w} {schip:d} {stile:d} {sslice:d} {sindex:d}',
        '{sblk:w} {schip:d} {stile:d} {sslice:d}'
    ]

    dst_cmds = [
        '{dblk:w} {dchip:d} {dtile:d} {dslice:d} {dindex:d} port {dport:d}',
        '{dblk:w} {dchip:d} {dtile:d} {dslice:d} port {dport:d}',
        '{dblk:w} {dchip:d} {dtile:d} {dslice:d} {dindex:d}',
        '{dblk:w} {dchip:d} {dtile:d} {dslice:d}'
    ]
    result = None
    for dst in dst_cmds:
        for src in src_cmds:
            if result is None:
                cmd = "%s %s %s" % (name,src,dst)
                result = parselib.parse(cmd,line)

    if result is None:
        return OptionalValue.error("usage:<%s>\nline:<%s>" % (cmd,line))

    result = dict(result.named.items())
    if not 'sindex' in result:
        result['sindex'] = None
    if not 'dindex' in result:
        result['dindex'] = None
    if not 'sport' in result:
        result['sport'] = None
    if not 'dport' in result:
        result['dport'] = None

    return OptionalValue.value(result)

def parse_pattern_block(args,n_signs,n_consts,n_range_codes, \
                        name,index=False,debug=False,source=None,expr=False):
    line = " ".join(args)
    DEBUG = {'debug':True,'prod':False}

    cmd = "%s {chip:d} {tile:d} {slice:d}" % name
    if index:
        cmd += " {index:d}"

    if not source is None:
        cmd += " src "
        cmd += "{source}"

    if n_signs > 0:
        cmd += " sgn "
        cmd += ' '.join(map(lambda idx: "{sign%d:W}" % idx,
                            range(0,n_signs)))
    if n_consts > 0:
        cmd += ' val '
        cmd += ' '.join(map(lambda idx: "{value%d:g}" % idx,
                           range(0,n_consts)))

    if n_range_codes > 0:
        cmd += ' rng '
        cmd += ' '.join(map(lambda idx: "{range%d:w}" % idx,
                           range(0,n_range_codes)))


    if debug:
        cmd += " {debug:w}"

    if expr:
        cmd += " {vars} {expr}"

    cmd = cmd.strip()
    result = parselib.parse(cmd,line)
    if result is None:
        msg = "usage: <%s>\n" % (cmd)
        msg += "line: <%s>" % line
        return OptionalValue.error(msg)

    result = dict(result.named.items())
    for idx in range(0,n_signs):
        key = 'sign%d' % idx
        value = result[key]
        result[key] = SignType.from_abbrev(value)

    for idx in range(0,n_range_codes):
        key = 'range%d' % idx
        value = result[key]
        result[key] = RangeType.from_abbrev(value)

    if not source is None:
        key = "source"
        value = result[key]
        result[key] = source.from_abbrev(value)

    if debug:
        result['debug'] = DEBUG[result['debug']]


    if expr:
        args = result['vars'].split('[')[1] \
                             .split(']')[0].split()
        result['vars'] = args


    return OptionalValue.value(result)

class ConstVal:
    #POS_BUF = np.arange(0.75,-0.8,-(0.8+0.75)/256)
    #NEG_BUF = np.arange(-0.8,0.8,(0.8+0.8)/256)
    NEG_BUF = np.arange(0.9375,-1.0,-(1.9375)/256)
    POS_BUF = np.arange(-1.0,1.0,(2.0)/256)

    @staticmethod
    def POS_get_closest(value):
        pos_dist,pos_near_val = util.find_closest(ConstVal.POS_BUF, \
                                          value,util.RoundMode.NEAREST)
        code = int(np.where(ConstVal.POS_BUF == pos_near_val)[0])
        return pos_near_val,code

    @staticmethod
    def NEG_get_closest(value):
        neg_dist,neg_near_val = util.find_closest(ConstVal.NEG_BUF, \
                                          value,util.RoundMode.NEAREST)
        code = int(np.where(ConstVal.NEG_BUF == neg_near_val)[0])
        return neg_near_val,code


    @staticmethod
    def get_closest(value):
        pos_dist,pos_near_val = util.find_closest(ConstVal.POS_BUF, \
                                          value,util.RoundMode.NEAREST)
        neg_dist,neg_near_val = util.find_closest(ConstVal.NEG_BUF, \
                                          value,util.RoundMode.NEAREST)
        if pos_dist <= neg_dist:
            inv = False
            code = int(np.where(ConstVal.POS_BUF == pos_near_val)[0])
            near_val = pos_near_val
        else:
            inv = True
            code = int(np.where(ConstVal.NEG_BUF == neg_near_val)[0])
            near_val = neg_near_val
        return near_val,inv,code
