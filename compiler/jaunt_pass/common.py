import compiler.jaunt_pass.basic_opt as boptlib
import compiler.jaunt_pass.phys_opt as physoptlib
import ops.jop as jop
import ops.op as ops
from enum import Enum


#TODO: what is low range, high range and med range?
#TODO: setRange: integ.in, integ.out and mult have setRange functions.
#TODO: how do you set wc in the integrator? Is it through the setRange function?
class JauntObjectiveFunctionManager():

    @staticmethod
    def basic_methods():
        #return ['fast','slow','max']
        return [
            boptlib.SlowObjFunc,
            boptlib.FastObjFunc,
            boptlib.MaxSignalObjFunc,
            boptlib.MaxSignalAndSpeedObjFunc,
            boptlib.MaxSignalAndStabilityObjFunc,

        ]

    @staticmethod
    def physical_methods():
        #return ['lo-noise', 'lo-bias', 'lo-delay']
        return [boptlib.MaxSignalAtSpeedObjFunc, \
                physoptlib.LowNoiseObjFunc]

    def __init__(self,jenv):
        self.method = None
        self.jenv = jenv
        self._results = {}

    def result(self,objective):
        return self._results[objective]

    def add_result(self,objective,sln):
        assert(not objective in self._results)
        self._results[objective] = sln


    def objective(self,circuit,varmap):
        assert(not self.method is None)
        gen = None
        for obj in self.basic_methods() + self.physical_methods():
            if obj.name() == self.method:
                gen = obj.make(circuit,self,varmap)

        for obj in gen:
            yield obj

class JauntVarType(Enum):
  SCALE_VAR= "SCV"
  COEFF_VAR = "COV"
  OP_RANGE_VAR = "OPV"
  VAR = "VAR"

class JauntEnv:
  LUT_SCF_IN = "LUTSCFIN"
  LUT_SCF_OUT = "LUTSCFOUT"
  TAU = "tau"

  def __init__(self):
    # scaling factor name to port
    self._to_jaunt_var = {}
    self._from_jaunt_var ={}

    self._in_use = {}

    self._eqs = []
    self._ltes = []
    # metavar
    self._meta = {}
    self._metavar = 0
    self._failed = False
    self._use_tau = False
    self._solved = False

  def set_solved(self,solved_problem):
      self._solved = solved_problem

  def solved(self):
      return self._solved

  def use_tau(self):
      self._use_tau = True

  def uses_tau(self):
      return self._use_tau

  def fail(self):
      self._failed = True

  def failed(self):
      return self._failed

  def in_use(self,scvar):
      return (scvar) in self._in_use

  def variables(self):
      yield JauntEnv.TAU

      #for tauvar in self._from_tauvar.keys():
      #    yield tauvar

      for scvar in self._from_jaunt_var.keys():
          yield scvar

  def eqs(self):
      for lhs,rhs in self._eqs:
          yield (lhs,rhs)

  def ltes(self):
      for lhs,rhs in self._ltes:
          yield (lhs,rhs)


  def get_jaunt_var_info(self,scvar_var):
      if not scvar_var in self._from_jaunt_var:
          print(self._from_jaunt_var.keys())
          raise Exception("not scaling factor table in <%s>" % scvar_var)

      block_name,loc,port,handle,tag = self._from_jaunt_var[scvar_var]
      return block_name,loc,port,handle,tag


  def jaunt_vars(self):
      return self._from_jaunt_var.keys()

  def get_jaunt_var(self,block_name,loc,port,handle=None, \
                    tag=JauntVarType.VAR):
      scvar = self._to_jaunt_var[(block_name,loc,port,handle,tag)]
      self._in_use[scvar] = True
      return scvar


  def decl_jaunt_var(self,block_name,loc,port,handle=None, \
                     tag=JauntVarType.VAR):
      # create a scaling factor from the variable name
      var_name = "%s_%s_%s_%s_%s" % (tag,block_name,loc,port,handle)
      if var_name in self._from_jaunt_var:
          return var_name

      self._from_jaunt_var[var_name] = (block_name,loc,port,handle,tag)
      self._to_jaunt_var[(block_name,loc,port,handle,tag)] = var_name
      return var_name

  def get_scvar(self,block_name,loc,port,handle=None):
    return self.decl_jaunt_var(block_name,loc,port,handle, \
                               tag=JauntVarType.SCALE_VAR)

  def decl_scvar(self,block_name,loc,port,handle=None):
    return self.decl_jaunt_var(block_name,loc,port,handle, \
                               tag=JauntVarType.SCALE_VAR)
  def eq(self,v1,v2):
      # TODO: equality
      self._eqs.append((v1,v2))


  def lte(self,v1,v2):
      # TODO: equality
      self._ltes.append((v1,v2))


  def gte(self,v1,v2):
      # TODO: equality
      self.lte(v2,v1)

def is_zero(v):
    return abs(v) < 1e-14


def same_sign(v1,v2):
    if v1 < 0 and v2 < 0:
        return True
    elif v1 > 0 and v2 > 0:
        return True
    else:
        return False


def decl_scale_variables(jenv,circ):
    # define scaling factors
    for block_name,loc,config in circ.instances():
        block = circ.board.block(block_name)
        for output in block.outputs:
            jenv.decl_scvar(block_name,loc,output)
            for handle in block.handles(config.comp_mode,output):
                jenv.decl_scvar(block_name,loc,output,handle=handle)

            if block.name == "lut":
                jenv.decl_scvar(block_name,loc,output, \
                                handle=jenv.LUT_SCF_OUT)
                pass

        for inp in block.inputs:
            jenv.decl_scvar(block_name,loc,inp)
            if block.name == "lut":
                jenv.decl_scvar(block_name,loc,inp, \
                                handle=jenv.LUT_SCF_IN)
                pass

        for output in block.outputs:
            for orig in block.copies(config.comp_mode,output):
                copy_scf = jenv.get_scvar(block_name,loc,output)
                orig_scf = jenv.get_scvar(block_name,loc,orig)
                jenv.eq(jop.JVar(orig_scf),jop.JVar(copy_scf))

    # set scaling factors connected by a wire equal
    for sblk,sloc,sport,dblk,dloc,dport in circ.conns():
        s_scf = jenv.get_scvar(sblk,sloc,sport)
        d_scf = jenv.get_scvar(dblk,dloc,dport)
        jenv.eq(jop.JVar(s_scf),jop.JVar(d_scf))


def cstr_lower_bound(jenv,expr,math_lower,hw_lower):
    if is_zero(math_lower) and hw_lower <= 0:
        return
    elif is_zero(math_lower) and hw_lower > 0:
        return jenv.fail()
    elif is_zero(hw_lower) and math_lower >= 0:
        return
    elif is_zero(hw_lower) and math_lower < 0:
        return jenv.fail()

    assert(not is_zero(math_lower))
    assert(not is_zero(hw_lower))

    if same_sign(math_lower,hw_lower) and \
       math_lower > 0 and hw_lower > 0:
        jenv.gte(jop.JMult(expr,jop.JConst(math_lower)),
                 jop.JConst(hw_lower))

    elif same_sign(math_lower,hw_lower) and \
         math_lower < 0 and hw_lower < 0:
        jenv.lte(jop.JMult(expr,jop.JConst(-math_lower)),
                 jop.JConst(-hw_lower))

    elif not same_sign(math_lower,hw_lower) and \
         hw_lower < 0 and math_lower > 0:
        pass

    elif not same_sign(math_lower,hw_lower) and \
         hw_lower > 0 and math_lower < 0:
        print("[[fail]] dne A st: %s < A*%s" % (hw_lower,math_lower))
        jenv.fail()
    else:
        raise Exception("uncovered lb: %s %s" % (math_lower,hw_lower))


def cstr_upper_bound(jenv,expr,math_upper,hw_upper):
    if is_zero(math_upper) and hw_upper >= 0:
        return

    elif is_zero(math_upper) and hw_upper < 0:
        return

    elif is_zero(hw_upper) and math_upper <= 0:
        return

    elif is_zero(hw_upper) and math_upper > 0:
        return jenv.fail()

    assert(not is_zero(math_upper))
    assert(not is_zero(hw_upper))

    if same_sign(math_upper,hw_upper) and \
       math_upper > 0 and hw_upper > 0:
        jenv.lte(jop.JMult(expr,jop.JConst(math_upper)),
                 jop.JConst(hw_upper))

    elif same_sign(math_upper,hw_upper) and \
         math_upper < 0 and hw_upper < 0:
        jenv.lte(jop.JMult(expr,jop.JConst(-math_upper)),
                 jop.JConst(-hw_upper))

    elif not same_sign(math_upper,hw_upper) and \
         hw_upper > 0 and math_upper < 0:
        pass

    elif not same_sign(math_upper,hw_upper) and \
         hw_upper < 0 and math_upper > 0:
        print("[[fail]] dne A st: %s > A*%s" % (hw_upper,math_upper))
        jenv.fail()
    else:
        raise Exception("uncovered ub: %s %s" % (math_upper,hw_upper))


def cstr_in_interval(jenv,scale_expr,math_rng,hw_rng):
    cstr_upper_bound(jenv,scale_expr, \
                            math_rng.upper,hw_rng.upper)
    cstr_lower_bound(jenv,scale_expr, \
                            math_rng.lower,hw_rng.lower)


class ExprVisitor:

  def __init__(self,jenv,circ,block,loc,port):
    self.jenv = jenv
    self.circ = circ
    self.block = block
    self.loc = loc
    self.port = port

  def visit(self):
    raise NotImplementedError

  def get_coeff(self,handle=None):
    raise NotImplementedError

  def visit_expr(self,expr):
    if expr.op == ops.OpType.CONST:
      return self.visit_const(expr)

    elif expr.op == ops.OpType.VAR:
      return self.visit_var(expr)

    elif expr.op == ops.OpType.MULT:
      return self.visit_mult(expr)

    elif expr.op == ops.OpType.SGN:
      return self.visit_sgn(expr)

    elif expr.op == ops.OpType.ABS:
      return self.visit_abs(expr)

    elif expr.op == ops.OpType.SQRT:
      return self.visit_sqrt(expr)

    elif expr.op == ops.OpType.COS:
      return self.visit_cos(expr)

    elif expr.op == ops.OpType.SIN:
      return self.visit_sin(expr)

    elif expr.op == ops.OpType.INTEG:
      return self.visit_integ(expr)

    else:
        raise Exception("unhandled <%s>" % expr)


  def visit_const(self,c):
    raise NotImplementedError

  def visit_var(self,v):
    raise NotImplementedError

  def visit_mult(self,m):
    raise NotImplementedError

  def visit_sgn(self,s):
    raise NotImplementedError

class SCFPropExprVisitor(ExprVisitor):

  def __init__(self,jenv,circ,block,loc,port):
      ExprVisitor.__init__(self,jenv,circ,block,loc,port)

  def coeff(self,handle):
      block,loc = self.block,self.loc
      config = circ.config(block.name,loc)
      coeff = block.coeff(config.comp_mode,config.scale_mode)
      return jop.JConst(coeff)

  def visit_const(self,expr):
      return jop.JConst(1.0)

  def visit_var(self,expr):
      block,loc = self.block,self.loc
      scvar = self.jenv.get_scvar(block.name,loc,expr.name)
      return jop.JVar(scvar)

  def visit_mult(self,expr):
      expr1 = self.visit_expr(expr.arg1)
      expr2 = self.visit_expr(expr.arg2)
      return jop.JMult(expr1,expr2)

  def visit_sgn(self,expr):
      expr1 = self.visit_expr(expr.arg(0))
      return jop.JConst(1.0)

  def visit_abs(self,expr):
      expr = self.visit_expr(expr.arg(0))
      return expr

  def visit_sqrt(self,expr):
      expr = self.visit_expr(expr.arg(0))
      new_expr = jop.expo(expr,0.5)
      return new_expr

  def visit_cos(self,expr):
      expr = self.visit_expr(expr.arg(0))
      jenv.eq(expr, jop.JConst(1.0))
      return jop.JConst(1.0)

  def visit_sin(self,expr):
      return self.visit_cos(expr)

  def visit_integ(self,expr):
      jenv = self.jenv
      # config
      scexpr_ic = self.visit_expr(expr.init_cond)
      scexpr_deriv = self.visit_expr(expr.deriv)

      scvar_deriv = jop.JVar(jenv.get_scvar(block.name,loc,port, \
                                            handle=expr.deriv_handle))
      scvar_state = jop.JVar(jenv.get_scvar(block.name,loc,port, \
                                            handle=expr.handle))
      scvar_ic = scvar_state

      coeff_deriv = self.coeff(expr.deriv_handle)
      coeff_state = self.coeff(expr.handle)
      coeff_ic = self.coeff(expr.ic_handle)

      jenv.eq(jop.JMult(scexpr_ic,coeff_ic), \
              scvar_ic)
      jenv.eq(jop.JMult(scexpr_deriv, coeff_deriv), \
              scvar_deriv)

      scexpr_state = jop.JMult(jop.JVar(jenv.TAU, \
                                        exponent=-1), scvar_deriv)

      jenv.eq(jop.JMult(scexpr_state, coeff_state), \
              scvar_state)

      jenv.use_tau()
      return scvar_state

  def visit(self):
      block,loc = self.block,self.loc
      config = self.circ.config(block.name,loc)
      expr = block.get_dynamics(config.comp_mode,self.port)
      scfvar = jop.JVar(self.jenv.get_scvar(block.name,loc,self.port))
      scexpr = self.visit_expr(expr)
      coeffvar = self.coeff(None)
      self.jenv.eq(scfvar,jop.JMult(scexpr,coeffvar))

class SCFLUTPropExprVisitor(SCFPropExprVisitor):

  def __init__(self,jenv,circ,block,loc,port):
      SCFPropExprVisitor.__init__(self,jenv,circ,block,loc,port)

  def coeff_lut_in(self):
      name = jenv.get_scvar(block.name,loc,expr.name, \
                            handle=jenv.LUT_SCF_IN)
      return jop.JVar(name)

  def coeff_lut_out(self):
      name = jenv.get_scvar(block.name,loc,expr.name, \
                            handle=jenv.LUT_SCF_OUT)
      return jop.JVar(name)


  def visit_var(self,expr):
    scvar = jenv.get_scvar(block.name,loc,expr.name)
    prod = jop.JMult(jop.JVar(scvar),self.coeff_lut_in())
    delta = 1e-4
    cstr_in_interval(jenv,prod, \
                    interval.Interval.type_infer(1.0-delta, 1.0+delta),
                    interval.Interval.type_infer(1.0,1.0)
    )
    return jop.JConst(1.0)

  def visit(self):
    scfvar = jop.JVar(jenv.get_scvar(block.name,loc,out))
    coeffvar = jop.JVar(jenv.get_coeff_var(block.name,loc,out))
    config = circ.config(block.name,loc)
    expr = config.expr(out)
    scexpr = jcomlib.cstr_traverse_expr(jenv,circ,block,loc,out,expr)
    compvar = jop.JVar(jenv.get_scvar(block.name,loc,out, \
                                handle=jenv.LUT_SCF_OUT))
    jenv.eq(scfvar, jop.JMult(jop.JMult(self.coeff_lut_out(), \
                                        scexpr),coeffvar))
    return scfvar
