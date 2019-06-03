import util.util as util
import chip.units as units
from lab_bench.lib.chipcmd.data import RangeType
from enum import Enum
#NOMINAL_NOISE = 1e-9
#NOMINAL_DELAY = 1e-10

'''
TODO Calibration lessons

High units must be > 0.1 (gain of 0.08 caused it to crap out)
Email: is entire dynamic range -1.2V t0 1.2V used? Are A0 and A1 flipped? Initial condition experiments seem to indicate so.

integ/hi-hi: max-ic=0.81*10.0 (error is 0.02)
mult/hi-hi-/vga/gain-min: min-gain=0.2 (error is 0.02)


# issues to debug
integ/hi-hi: ic=0.4*10.0 (there's an issue with the initial condition not matching)
'''

class GLProp(Enum):
  CURRENT_INTERVAL = "curr_ival"
  VOLTAGE_INTERVAL = "volt_ival"
  DIGITAL_INTERVAL = "dig_ival"
  DIGITAL_EXCLUDE = "dig_exclude"
  DIGITAL_QUANTIZE = "dig_quantize"
  MAX_FREQ = "max_freq"
  DIGITAL_SAMPLE = "dig_samp"
  INBUF_SIZE = "in_buf"
  OUTBUF_SIZE = "out_buf"
  COEFF = "coeff"

class GlobalCtx:

  def __init__(self):
    self._ctx = {}
    for prop in GLProp:
      self._ctx[prop] = {}
    self.freeze = False

  def __insert(self,prop,block,cm,sm,port,value):
    assert(not (block,cm,sm) in self._ctx[prop])
    self._ctx[prop][(block,cm,sm,port)] = value

  def get(self,prop,block,cm,sm,port):
    if (block,cm,sm,port) in self._ctx[prop]:
      return self._ctx[prop][(block,cm,sm,port)]

    if (block,cm,sm,None) in self._ctx[prop]:
      return self._ctx[prop][(block,cm,sm,None)]

    if (block,cm,None,None) in self._ctx[prop]:
      return self._ctx[prop][(block,cm,None,None)]

    if (block,None,None,None) in self._ctx[prop]:
      return self._ctx[prop][(block,None,None,None)]

    if (None,None,None,None) in self._ctx[prop]:
      return self._ctx[prop][(None,None,None,None)]

    raise Exception("no default value <%s>" % prop)

  def insert(self,prop,value,block=None,cm=None,sm=None,port=None):
    assert(not self.freeze)
    self.__insert(prop,block,cm,sm,port,value)

CTX = GlobalCtx()
CTX.insert(GLProp.DIGITAL_INTERVAL, (-1.0,1.0))
CTX.insert(GLProp.DIGITAL_EXCLUDE, (0.0,0.0))
#CTX.insert(GLProp.CURRENT_INTERVAL, (-1.9,1.9))
CTX.insert(GLProp.CURRENT_INTERVAL, (-2.0,2.0))
CTX.insert(GLProp.VOLTAGE_INTERVAL, (-1.0,1.0))
CTX.insert(GLProp.DIGITAL_QUANTIZE, 256)

#CTX.insert(GLProp.MAX_FREQ, 200*units.khz)
CTX.insert(GLProp.MAX_FREQ, 1000*units.khz)
CTX.insert(GLProp.DIGITAL_SAMPLE, 3.0*units.us)
CTX.insert(GLProp.INBUF_SIZE,1200)
CTX.insert(GLProp.OUTBUF_SIZE,1e9)

#CTX.insert(GLProp.DIGITAL_EXCLUDE, (-0.19,0.19), block="integrator")

# exclude these constant ranges, because the system is unable to calibrate.
# the 0.19 is a tight bound, the 0.4 is a guess.
#CTX.insert(GLProp.DIGITAL_EXCLUDE, (-0.19,0.19), block="multiplier")
for mode in [(RangeType.HIGH, RangeType.MED), \
             (RangeType.MED, RangeType.LOW)]:
  CTX.insert(GLProp.DIGITAL_EXCLUDE, (-0.4,0.4), block="multiplier",cm="vga", \
             sm=mode)

freq_khz = 40
CTX.insert(GLProp.MAX_FREQ, freq_khz*units.khz, block='tile_dac')
CTX.insert(GLProp.COEFF, 2.0, block='tile_dac')

CTX.insert(GLProp.MAX_FREQ, freq_khz*units.khz, block='tile_adc')
CTX.insert(GLProp.COEFF, 0.5, block='tile_adc')

CTX.insert(GLProp.MAX_FREQ, freq_khz*units.khz, block='tile_lut')

# specialized ext_chip_in
CTX.insert(GLProp.COEFF, 2.0, block='ext_chip_analog_in')
CTX.insert(GLProp.COEFF, 2.0, block='ext_chip_analog_in')

# specialized ext_chip_in
CTX.insert(GLProp.DIGITAL_QUANTIZE, 4096, block='ext_chip_in')
CTX.insert(GLProp.DIGITAL_SAMPLE, 10*units.us, block='ext_chip_in')
CTX.insert(GLProp.COEFF, 2.0, block='ext_chip_in')

# specialized ext_chip_out
CTX.insert(GLProp.DIGITAL_QUANTIZE, 4096, block='ext_chip_out')
CTX.insert(GLProp.DIGITAL_SAMPLE, 1*units.ns, block='ext_chip_out')
CTX.insert(GLProp.COEFF, 0.5, block='ext_chip_out')

CTX.freeze = True

TIME_FREQUENCY = 200*units.khz
