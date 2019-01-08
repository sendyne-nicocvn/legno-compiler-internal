from chip.block import Block
import chip.props as props
import chip.hcdc.util as util
import lab_bench.lib.chip_command as chipcmd
import chip.hcdc.globals as glb
import ops.op as ops
import itertools


def get_modes():
    opts = [
        chipcmd.SignType.options(),
        chipcmd.SignType.options(),
        chipcmd.SignType.options(),
        chipcmd.RangeType.options()
    ]
    blacklist = [
        (None,None,None,chipcmd.RangeType.LOW)
    ]
    modes = list(util.apply_blacklist(itertools.product(*opts),
                                      blacklist))
    return modes

def blackbox_model(fanout):
    modes = get_modes()
    print("[TODO]: fanout.blackbox")
'''
    for mode in nodes:
        _,_,_,rng = mode
        noise_model = nop.NZero()
        fmax_model = 20*1000
        fanout. \
            .set_blackbox_model("*",mode,"out0",noise_model) \
            .set_blackbox_model("*",mode,"out1",noise_model) \
            .set_blackbox_model("*",mode,"out2",noise_model)
'''

def scale_model(fanout):
    modes = get_modes()
    fanout.set_scale_modes("*",modes)
    for mode in modes:
        inv0,inv1,inv2,rng = mode
        fanout\
            .set_scale_factor("*",mode,"out0",inv0.coeff()) \
            .set_scale_factor("*",mode,"out1",inv1.coeff()) \
            .set_scale_factor("*",mode,"out2",inv2.coeff())
        fanout\
            .set_info("*",mode,["out0","out1","out2","in"],
                      util.make_ana_props(rng,
                                          glb.ANALOG_MIN, \
                                          glb.ANALOG_MAX))

    fanout.check()


block = Block('fanout',type=Block.COPIER) \
.add_outputs(props.CURRENT,["out1","out2","out0"]) \
.add_inputs(props.CURRENT,["in"]) \
.set_op("*","out0",ops.Var("in")) \
.set_copy("*","out1","out0") \
.set_copy("*","out2","out0")
blackbox_model(block)
scale_model(block)
