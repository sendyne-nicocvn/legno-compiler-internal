from chip.block import Block, BlockType
import chip.props as props
from chip.phys import PhysicalModel
import chip.units as units
import chip.hcdc.util as util
from chip.cont import *
import lab_bench.lib.chipcmd.data as chipcmd
from chip.hcdc.globals import CTX, GLProp
import chip.hcdc.globals as glb
import ops.op as ops
import itertools

def dac_get_modes():
   opts = [
      [chipcmd.SignType.POS],
      chipcmd.RangeType.options()
   ]
   blacklist = [
      (None,chipcmd.RangeType.LOW)
   ]
   modes = list(util.apply_blacklist(itertools.product(*opts),
                                     blacklist))
   return modes


def dac_continuous_scale_model(dac):
  modes = dac_get_modes()
  csm = ContinuousScaleModel()
  csm.set_baseline((chipcmd.SignType.POS, chipcmd.RangeType.MED))
  out = csm.decl_var(CSMOpVar("out"))
  inp = csm.decl_var(CSMOpVar("in"))
  coeff = csm.decl_var(CSMCoeffVar("out"))
  csm.eq(ops.Mult(ops.Var(inp.varname),
                  ops.Var(coeff.varname)), \
         ops.Var(out.varname))
  for scm in modes:
     _,scm_o = scm
     csm.discrete.add_mode(scm)
     csm.discrete.add_cstr(scm,out,scm_o.coeff())
     csm.discrete.add_cstr(scm,coeff,scm_o.coeff())

  dac.set_scale_model("*", csm)

def dac_scale_model(dac):
   modes = dac_get_modes()
   dac.set_scale_modes("*",modes)
   for mode in modes:
      get_prop = lambda p : CTX.get(p, dac.name,
                                    '*',mode,None)

      sign,rng = mode
      # ERRATA: dac does scale up.
      coeff = sign.coeff()*rng.coeff()*get_prop(GLProp.COEFF)
      digital_props = util.make_dig_props(chipcmd.RangeType.MED,
                                         get_prop(GLProp.DIGITAL_INTERVAL),
                                         get_prop(GLProp.DIGITAL_QUANTIZE)
      )
      ana_props = util.make_ana_props(rng,
                                      get_prop(GLProp.CURRENT_INTERVAL))
      digital_props.set_continuous(0,get_prop(GLProp.MAX_FREQ))
      dac.set_coeff("*",mode,'out', coeff)
      dac.set_props("*",mode,["in"], digital_props)
      dac.set_props("*",mode,["out"], ana_props)


dac = Block('tile_dac',type=BlockType.DAC) \
.add_outputs(props.CURRENT,["out"]) \
.add_inputs(props.DIGITAL,["in"]) \
.set_op("*","out",ops.Var("in"))
dac_scale_model(dac)
dac_continuous_scale_model(dac)
dac.check()

def adc_get_modes():
   return [chipcmd.RangeType.HIGH, chipcmd.RangeType.MED]

def adc_black_box_model(adc):
   def config_phys_model(phys,rng):
        if rng == chipcmd.RangeType.MED:
            new_phys =  PhysicalModel.read(util.datapath('adc-m.bb'))
        elif rng == chipcmd.RangeType.HIGH:
            new_phys = PhysicalModel.read(util.datapath('adc-h.bb'))
        else:
            raise Exception("unknown physical model: %s" % str(rng))

        phys.set_to(new_phys)

   scale_modes = dac_get_modes()
   for sc in scale_modes:
      _,rng = sc
      config_phys_model(adc.physical('*',sc,"out"),rng)


def adc_continuous_scale_model(adc):
   modes = adc_get_modes()
   csm = ContinuousScaleModel()
   csm.set_baseline(chipcmd.RangeType.MED)
   out = csm.decl_var(CSMOpVar("out"))
   inp = csm.decl_var(CSMOpVar("in"))
   coeff = csm.decl_var(CSMCoeffVar("out"))
   csm.eq(ops.Mult(ops.Var(inp.varname),
                   ops.Var(coeff.varname)), \
          ops.Var(out.varname))
   for scm_i in modes:
     csm.discrete.add_mode(scm_i)
     csm.discrete.add_cstr(scm_i,inp,scm_i.coeff())
     csm.discrete.add_cstr(scm_i,coeff,1.0/scm_i.coeff())

   adc.set_scale_model("*", csm)

def adc_scale_model(adc):
   modes = adc_get_modes()
   adc.set_scale_modes("*",modes)
   for mode in modes:
      get_prop = lambda p : CTX.get(p, adc.name,
                                    '*',mode,None)

      coeff = (1.0/mode.coeff())*get_prop(GLProp.COEFF)
      analog_props = util.make_ana_props(mode,
                                         get_prop(GLProp.CURRENT_INTERVAL))
      #analog_props.set_bandwidth(0,20,units.khz)

      digital_props = util.make_dig_props(chipcmd.RangeType.MED,
                                          get_prop(GLProp.DIGITAL_INTERVAL),
                                          get_prop(GLProp.DIGITAL_QUANTIZE)
      )
      digital_props.set_continuous(0,get_prop(GLProp.MAX_FREQ))
      adc.set_props("*",mode,["in"],analog_props)
      adc.set_props("*",mode,["out"], digital_props)
      adc.set_coeff("*",mode,'out', coeff)



adc = Block('tile_adc',type=BlockType.ADC) \
.add_outputs(props.DIGITAL,["out"]) \
.add_inputs(props.CURRENT,["in"]) \
.set_op("*","out",ops.Var("in")) \
.set_props("*","*",["out"],None) \
.set_props("*","*",["in"],None) \
.set_coeff("*","*","out",0.5)
adc_scale_model(adc)
adc_continuous_scale_model(adc)
adc.check()
