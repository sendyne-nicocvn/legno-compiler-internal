import gpkit
import itertools

import lab_bench.lib.chipcmd.data as chipcmd

from chip.config import Labels
import chip.cont as cont
from chip.conc import ConcCirc
import chip.model as modelib

from compiler.common import infer
import compiler.jaunt_pass.jenv as jenvlib
import compiler.jaunt_pass.jenv_gpkit as jgpkit
import compiler.jaunt_pass.jenv_smt as jsmt
import compiler.jaunt_pass.objective.basic_obj as basicobj
import compiler.jaunt_pass.expr_visitor as exprvisitor
from compiler.jaunt_pass.objective.obj_mgr import JauntObjectiveFunctionManager

import compiler.jaunt_pass.jaunt_util as jaunt_util
import compiler.jaunt_pass.jaunt_common as jaunt_common

import ops.jop as jop
import ops.op as ops
import chip.props as props
import ops.interval as interval

import signal
import random
import time
import numpy as np
import util.util as util
import util.config as CONFIG
from tqdm import tqdm

def sc_get_scm_var(jenv,block_name,loc,v):
    if v.type == cont.CSMVar.Type.OPVAR:
        jvar = jenv.get_op_range_var(block_name,loc,v.port,v.handle)
    elif v.type == cont.CSMVar.Type.COEFFVAR:
        jvar = jenv.get_gain_var(block_name,loc,v.port,v.handle)
    else:
        raise Exception("unknown var type")
    return jvar


class ScaleModelExprVisitor(exprvisitor.ExprVisitor):

    def __init__(self,jenv,circ,block,loc):
        exprvisitor.ExprVisitor.__init__(self,jenv,circ,block,loc,None)

    def visit_var(self,expr):
        block,loc = self.block,self.loc
        config = self.circ.config(block.name,loc)
        scale_model = block.scale_model(config.comp_mode)
        var= scale_model.var(expr.name)
        jaunt_var = sc_get_scm_var(self.jenv,block.name,loc,var)
        return jop.JVar(jaunt_var)

    def visit_pow(self,expr):
        expr1 = self.visit_expr(expr.arg1)
        expr2 = self.visit_expr(expr.arg2)
        return jop.expo(expr1,expr2.value)


    def visit_const(self,expr):
        return jop.JConst(expr.value)

    def visit_mult(self,expr):
        expr1 = self.visit_expr(expr.arg1)
        expr2 = self.visit_expr(expr.arg2)
        return jop.JMult(expr1,expr2)

class SCFInferExprVisitor(exprvisitor.SCFPropExprVisitor):

    def __init__(self,jenv,circ,block,loc,port):
        exprvisitor.SCFPropExprVisitor.__init__(self,\
                                                jenv,circ, \
                                                block,loc,port)

    def coeff(self,handle):
      block,loc = self.block,self.loc
      config = self.circ.config(block.name,loc)
      model = block.scale_model(config.comp_mode)
      scale_mode = model.baseline
      coeff_const = block.coeff(config.comp_mode, \
                                scale_mode,self.port)
      coeff_var = self.jenv.get_coeff_var(self.block.name, \
                                          self.loc, \
                                          self.port,handle=handle)
      return jop.JMult(jop.JConst(coeff_const), \
                       jop.JVar(coeff_var))

def sc_physics_model(jenv,scale_mode,circ,block_name,loc,port,handle):
        block = circ.board.block(block_name)
        config = circ.config(block.name,loc)

        baseline = block.baseline
        baseline = block.baseline(config.comp_mode)
        config.set_scale_mode(scale_mode)

        modevar = jenv.decl_mode_var(block_name,loc,scale_mode)
        jvar_gain = jenv.decl_gain_var(block_name, \
                                       loc, \
                                       port,handle)
        jvar_ops = jenv.decl_op_range_var(block_name, \
                                          loc, \
                                          port,handle)

        gain = block.coeff(config.comp_mode,scale_mode,port,handle)
        jenv.implies(modevar,jvar_gain, gain)

        props_sc = block.props(config.comp_mode,scale_mode,port,handle)
        props_bl = block.props(config.comp_mode,baseline,port,handle)
        scf = props_sc.interval().bound/props_bl.interval().bound
        jenv.implies(modevar,jvar_ops, scf)

        db = jaunt_common.DB
        jvar_phys_gain = jenv.decl_phys_gain_var(block_name, \
                                                loc, \
                                                port,handle)
        jvar_phys_ops_lower = jenv.decl_phys_op_range_scvar(block_name, \
                                                            loc, \
                                                            port,handle,
                                                            lower=True)
        jvar_phys_ops_upper = jenv.decl_phys_op_range_scvar(block_name, \
                                                            loc, \
                                                            port,handle,
                                                            lower=False)

        jvar_unc = jenv.decl_phys_uncertainty(block_name, \
                                         loc, \
                                         port,handle)

        #config.scale_mode = config.scale_mode
        model = jenv.params.model
        pars = jaunt_common.get_physics_params(jenv, \
                                               circ, \
                                               block, \
                                               loc, \
                                               port, \
                                               handle=handle)
        uncertainty,gain = pars['uncertainty'],pars['gain']
        oprange_scale_lower = pars['oprange_lower']
        oprange_scale_upper = pars['oprange_upper']
        jenv.implies(modevar,jvar_phys_gain, gain)
        jenv.implies(modevar,jvar_phys_ops_lower, oprange_scale_lower)
        jenv.implies(modevar,jvar_phys_ops_upper, oprange_scale_upper)
        jenv.implies(modevar,jvar_unc, uncertainty)
        config.set_scale_mode(baseline)

def sc_decl_scale_model_variables(jenv,circ):
    for block_name,loc,config in circ.instances():
        block = circ.board.block(block_name)

        for port in block.inputs + block.outputs:
            for handle in list(block.handles(config.comp_mode,port)) + [None]:
                for scm in block.scale_modes(config.comp_mode):
                 if not block.whitelist(config.comp_mode, scm):
                     continue
                 sc_physics_model(jenv,scm,circ,block_name,loc,port,handle=handle)

        modevars = []
        for scale_mode in block.scale_modes(config.comp_mode):
            if not block.whitelist(config.comp_mode, scale_mode):
                continue
            modevar = jenv.get_mode_var(block_name,loc,scale_mode)
            modevars.append(modevar)

        jenv.exactly_one(modevars)



def sc_build_jaunt_env(prog,circ, \
                       model="ideal", \
                       max_freq=None, \
                       digital_error=0.05, \
                       analog_error=0.05):
    jenv = jenvlib.JauntInferEnv(model, \
                                 max_freq=max_freq, \
                                 digital_error=digital_error,
                                 analog_error=analog_error)
    # declare scaling factors
    jaunt_common.decl_scale_variables(jenv,circ)
    # build continuous model constraints
    sc_decl_scale_model_variables(jenv,circ)
    sc_generate_problem(jenv,prog,circ)

    for block_name,loc,config in circ.instances():
        block = circ.board.block(block_name)
        for port in block.outputs + block.inputs:
            v = jenv.get_scvar(block_name,loc,port)
            jenv.lt(jop.JConst(1e-12), jop.JVar(v), \
                    "ensure nonzero");
            jenv.gt(jop.JConst(1e12), jop.JVar(v), \
                    "ensure nonzero");

    return jenv

# traverse dynamics, also including coefficient variable
def sc_traverse_dynamics(jenv,circ,block,loc,out):
    visitor = exprvisitor.SCFPropExprVisitor(jenv,circ,block,loc,out)
    visitor.visit()

def sc_interval_constraint(jenv,circ,prob,block,loc,port,handle=None):
    jaunt_util.log_info("%s[%s].%s" % (block.name,loc,port))
    config = circ.config(block.name,loc)
    baseline = block.baseline(config.comp_mode)
    prop = block.props(config.comp_mode,baseline,port,handle=handle)
    if isinstance(prop, props.AnalogProperties):
        jaunt_common.analog_op_range_constraint(jenv,circ,block,loc,port,handle,
                                                '%s-%s-%s' % \
                                                (block.name,loc,port))
        jaunt_common.analog_bandwidth_constraint(jenv,circ,block,loc,port,handle,
                                                 '%s-%s-%s' % \
                                                 (block.name,loc,port))

    elif isinstance(prop, props.DigitalProperties):
        jaunt_common.digital_op_range_constraint(jenv,circ,block,loc,port,handle,
                                                '%s-%s-%s' % \
                                                 (block.name,loc,port))
        jaunt_common.digital_quantize_constraint(jenv,circ,block,loc,port,handle,
                                                 'quantize')
        jaunt_common.digital_bandwidth_constraint(jenv,prob,circ, \
                                                  block,loc,port,handle,
                                                  '%s-%s-%s' % \
                                                  (block.name,loc,port))
    else:
        raise Exception("unknown")

def sc_port_used(jenv,block_name,loc,port,handle=None):
    return jenv.in_use((block_name,loc,port,handle), \
                       tag=jenvlib.JauntVarType.SCALE_VAR)

def sc_generate_problem(jenv,prob,circ):
    for block_name,loc,config in circ.instances():
        block = circ.board.block(block_name)
        for out in block.outputs:
            # ensure we can propagate the dynamics
            #if block.name == 'integrator':
                #jenv.interactive()

            sc_traverse_dynamics(jenv,circ,block,loc,out)

        for port in block.outputs + block.inputs:
            if sc_port_used(jenv,block_name,loc,port):
                sc_interval_constraint(jenv,circ,prob,block,loc,port)

            for handle in block.handles(config.comp_mode,port):
                if sc_port_used(jenv,block_name,loc,port,handle=handle):
                    sc_interval_constraint(jenv,circ,prob,block,loc,port, \
                                           handle=handle)



    if not jenv.uses_tau() or not jenv.time_scaling:
        jenv.eq(jop.JVar(jenv.tau()), jop.JConst(1.0),'tau-fixed')
    else:
        jenv.lte(jop.JVar(jenv.tau()), jop.JConst(1e10),'tau-min')
        jenv.gte(jop.JVar(jenv.tau()), jop.JConst(1e-10),'tau-max')
        jaunt_common.max_sim_time_constraint(jenv,prob,circ)



def concretize_result(jenv,circ,nslns):
    smtenv = jsmt.build_smt_prob(circ,jenv)
    for result in jsmt.solve_smt_prob(smtenv,nslns=nslns):
        new_circ = circ.copy()
        for key,value in result.items():
            if isinstance(value,bool):
                continue

            jaunt_util.log_info("%s=%s" % (key,value))

        for block_name,loc,config in new_circ.instances():
            block = circ.board.block(block_name)
            scale_mode = None
            for scm in block.scale_modes(config.comp_mode):
                if not block.whitelist(config.comp_mode,scm):
                    continue

                mode = jenv.get_mode_var(block_name,loc,scm)
                if result[mode]:
                    assert(scale_mode is None)
                    scale_mode = scm
            assert(not scale_mode is None)
            config.set_scale_mode(scale_mode)
            print("%s[%s] = %s" % (block_name,loc,scale_mode))
            jaunt_util.log_info("%s[%s] = %s" % (block_name,loc,scale_mode))
        yield new_circ

def solve_convex_first(prob,circ,jenv):
    jopt = JauntObjectiveFunctionManager(jenv)
    jaunt_util.log_debug("===== %s =====" % jopt.method)
    for joptfun in jopt.inference_methods():
        jaunt_util.log_info("===> %s <===" % joptfun.name())
        jopt.method = joptfun.name()
        for idx,(gpprob,obj) in \
            enumerate(jgpkit.build_gpkit_problem(circ,jenv,jopt)):
            if gpprob is None:
                print("no solution")
                continue

            jaunt_util.log_debug("-> %s" % jopt.method)
            sln = jgpkit.solve_gpkit_problem(gpprob)
            if sln is None:
                jaunt_util.log_info("[[FAILURE - NO SLN]]")
                jenv.set_solved(False)
                jgpkit.debug_gpkit_problem(gpprob)
                return
            else:
                jaunt_util.log_info("[[SUCCESS - FOUND SLN]]")
                jenv.set_solved(True)


def infer_scale_config(prog,circ,nslns, \
                       model="ideal", \
                       max_freq=None, \
                       analog_error=0.05,
                       digital_error=0.05):
    assert(isinstance(circ,ConcCirc))
    jenv = sc_build_jaunt_env(prog,circ,
                              model=model, \
                              max_freq=max_freq, \
                              analog_error=analog_error, \
                              digital_error=digital_error)
    #solve_convex_first(prog,circ,jenv)
    for new_circ in concretize_result(jenv,circ,nslns):
        yield new_circ

