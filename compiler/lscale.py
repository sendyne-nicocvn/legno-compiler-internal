import util.util as util

import ops.scop as scop
import ops.op as ops
import ops.interval as interval

import hwlib.model as hwmodel
import hwlib.props as props
from hwlib.adp import AnalogDeviceProg


import compiler.common.prop_interval as prop_interval

import compiler.lscale_pass.lscale_util as lscale_util
import compiler.lscale_pass.lscale_common as lscale_common
import compiler.lscale_pass.scenv as scenvlib
import compiler.lscale_pass.scenv_gpkit as scenv_gpkit
import compiler.lscale_pass.scenv_linear as scenv_linear

import compiler.lscale_pass.expr_visitor as exprvisitor
import compiler.lscale_pass.lscale_util as lscale_util
import compiler.lscale_pass.lscale_common as lscale_common
import compiler.lscale_pass.lscale_infer as lscale_infer
import compiler.lscale_pass.lscale_physlog as lscale_physlog
from compiler.lscale_pass.objective.obj_mgr import LScaleObjectiveFunctionManager





def sc_interval_constraint(scenv,circ,prob,block,loc,port,handle=None):
    config = circ.config(block.name,loc)
    prop = block.props(config.comp_mode,config.scale_mode,port,handle=handle)
    annot = "%s.%s.%s" % (block.name,loc,port)
    if isinstance(prop, props.AnalogProperties):
        lscale_common.analog_op_range_constraint(scenv,circ,block,loc,port, handle,\
                                                annot=annot)
        lscale_common.analog_bandwidth_constraint(scenv,circ,block,loc,port,handle,\
                                                 annot)

    elif isinstance(prop, props.DigitalProperties):
        lscale_common.digital_op_range_constraint(scenv,circ,block,loc,port,handle, \
                                                 annot)
        # phys,prop,scfvar,jop.JConst(1.0),mrng
        lscale_common.digital_quantize_constraint(scenv,circ,block,loc,port,handle, \
                                                 "")
        lscale_common.digital_bandwidth_constraint(scenv,prob,circ,block,loc,port,handle,
                                                  annot)
    else:
        raise Exception("unknown")


# traverse dynamics, also including coefficient variable
def sc_traverse_dynamics(scenv,circ,block,loc,out):
    visitor = exprvisitor.SCFPropExprVisitor(scenv,circ,block,loc,out)
    visitor.visit()


def sc_port_used(scenv,block_name,loc,port,handle=None):
    return scenv.in_use((block_name,loc,port,handle), \
                       tag=scenvlib.LScaleVarType.SCALE_VAR)

def sc_generate_problem(scenv,prob,circ):

    for block_name,loc,config in circ.instances():
        block = circ.board.block(block_name)
        for out in block.outputs:
            # ensure we can propagate the dynamics
            sc_traverse_dynamics(scenv,circ,block,loc,out)

        for port in block.outputs + block.inputs:
            if sc_port_used(scenv,block_name,loc,port):
                sc_interval_constraint(scenv,circ,prob,block,loc,port)

            for handle in block.handles(config.comp_mode,port):
                if sc_port_used(scenv,block_name,loc,port,handle=handle):
                    sc_interval_constraint(scenv,circ,prob,block, \
                                           loc,port,handle=handle)


    if not scenv.uses_tau() or not scenv.time_scaling:
        print("uses tau: %s" % scenv.uses_tau())
        print("time scale: %s" % scenv.time_scaling)
        scenv.eq(scop.SCVar(scenv.tau()), scop.SCConst(1.0),'tau_fixed')
    else:
        scenv.lte(scop.SCVar(scenv.tau()), scop.SCConst(1e6),'tau_min')
        scenv.gte(scop.SCVar(scenv.tau()), scop.SCConst(1e-6),'tau_max')
        lscale_common.max_sim_time_constraint(scenv,prob,circ)


def sc_build_lscale_env(scenv,prog,circ):
    # declare scaling factors
    lscale_common.decl_scale_variables(scenv,circ)
    # build continuous model constraints
    sc_generate_problem(scenv,prog,circ)
    return scenv


def apply_result(scenv,circ,sln):
    new_circ = circ.copy()
    lut_updates = {}
    for variable,value in sln.items():
        lscale_util.log_debug("%s = %s" % (variable,value))
        #print("%s = %s" % (variable,value))
        if variable == scenv.tau():
            new_circ.set_tau(value)
        else:
            tag,(block_name,loc,port,handle)= scenv.get_lscale_var_info(variable)
            if(tag == scenvlib.LScaleVarType.SCALE_VAR):
                new_circ.config(block_name,loc) \
                        .set_scf(port,value,handle=handle)
            elif(tag == scenvlib.LScaleVarType.INJECT_VAR):
                new_circ.config(block_name,loc) \
                    .set_inj(port,value)
            else:
                raise Exception("unhandled: <%s>" % tag)

    return new_circ

def compute_scale(scenv,prog,infer_circ,objfun):
    assert(isinstance(infer_circ,AnalogDeviceProg))
    print("build environment")
    scenv = sc_build_lscale_env(scenv,prog,infer_circ)
    scopt = LScaleObjectiveFunctionManager(scenv)
    scopt.method = objfun.name()

    print("objective: %s" % objfun.name())
    for lprob,thisobj in \
        scenv_linear.build_linear_problem(infer_circ,scenv,scopt):
        if lprob is None:
            print("<< could not linear geometric problem>>")
            continue

        print("solve")
        sln = scenv_linear.solve_linear_problem(lprob)
        if sln == None:
            print("<< solution is none >>")
            continue

        new_circ = apply_result(scenv,infer_circ,sln)
        yield thisobj,new_circ

def report_missing_models(model,circ):
    for block,loc,port,comp_mode,scale_mode in hwmodel.ModelDB.MISSING:
        lscale_physlog.log(circ,block,loc, \
                          comp_mode,
                          scale_mode)
        msg = "NO model: %s[%s].%s %s %s error" % \
              (block,loc,port, \
               comp_mode,scale_mode)

def scale(prog,adp,nslns, \
          model, \
          mdpe, \
          mape, \
          mc, \
          max_freq_khz=None, \
          do_log=True, \
          test_existence=False):
    def gen_models(model):
        models = [model]
        if model.uses_delta_model():
            models.append(model.naive_model())

            if model.calibrate_objective() == \
               util.CalibrateObjective.MAX_FIT:
                models.append(util.DeltaModel.DELTA_MINERR);
                models.append(util.DeltaModel.NAIVE_MINERR);

        return models

    assert(isinstance(model,util.DeltaModel))
    prop_interval.clear_intervals(adp)
    prop_interval.compute_intervals(prog,adp)
    objs = LScaleObjectiveFunctionManager.basic_methods()
    n_missing = 0
    has_solution = False
    for idx,infer_adp in enumerate(lscale_infer.infer_scale_config(prog, \
                                                                   adp, \
                                                                   nslns, \
                                                                   model=model,
                                                                   max_freq_khz=max_freq_khz, \
                                                                   mdpe=mdpe,
                                                                   mape=mape,
                                                                   mc=mc)):
        if test_existence:
            has_solution = True
            break
        for obj in objs:
            skip = False
            for this_model in gen_models(model):
                scenv = scenvlib.LScaleEnv(model=this_model, \
                                           max_freq_khz=max_freq_khz, \
                                           mdpe=mdpe, \
                                           mape=mape,
                                           mc=mc)

                if skip:
                    continue

                if this_model.uses_delta_model() and \
                   len(hwmodel.ModelDB.MISSING) > n_missing:
                    scenv.fail("missing models")
                    skip = True

                print("missing: %d -> %d" % \
                      (n_missing, len(hwmodel.ModelDB.MISSING)))
                n_missing = len(hwmodel.ModelDB.MISSING)

                for scaled_obj,scaled_adp in compute_scale(scenv,prog, \
                                                           infer_adp, \
                                                           obj):
                    yield idx,scaled_obj.tag(),scenv.params.tag(),scaled_adp

    if test_existence:
        if has_solution:
            yield None

        if not do_log:
            return


    print("logging: %s" % do_log)
    if do_log:
        pars = scenvlib.LScaleEnvParams(model=model,
                                        max_freq_khz=max_freq_khz, \
                                        mdpe=mdpe,
                                        mape=mape,
                                        mc=mc)
        report_missing_models(model,adp)
        lscale_physlog.save(pars.calib_obj)
        if not lscale_physlog.is_empty() and \
           model.uses_delta_model():
            raise Exception("must calibrate components")

        lscale_physlog.clear()
