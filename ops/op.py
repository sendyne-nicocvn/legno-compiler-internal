import itertools
import math
import ops.interval as interval
import ops.bandwidth as bandwidth
from enum import Enum
import numpy as np
import random

def to_python(e):
    if e.op == OpType.VAR:
        varname = "%s_" % e.name
        return [varname],varname

    elif e.op == OpType.CONST:
        return [],"%.4e" % e.value

    elif e.op == OpType.ADD:
        vs1,a1 = to_python(e.arg1)
        vs2,a2 = to_python(e.arg2)
        v = list(set(vs1+vs2))
        return v,"(%s)+(%s)" % (a1,a2)


    elif e.op == OpType.POW:
        vs1,a1 = to_python(e.arg(0))
        vs2,a2 = to_python(e.arg(1))
        v = list(set(vs1+vs2))
        return v,"(%s)**(%s)" % (a1,a2)

    elif e.op == OpType.MULT:
        vs1,a1 = to_python(e.arg1)
        vs2,a2 = to_python(e.arg2)
        v = list(set(vs1+vs2))
        return v,"(%s)*(%s)" % (a1,a2)

    elif e.op == OpType.CLAMP:
        v,a = to_python(e.arg1)
        ival = e.interval
        a2 = "max(%f,%s)" % (ival.lower,a)
        a3 = "min(%f,%s)" % (ival.upper,a2)
        return v,a3

    elif e.op == OpType.SGN:
        v,a = to_python(e.arg(0))
        return v,"math.copysign(1,%s)" % a

    elif e.op == OpType.RANDFUN:
        v,a = to_python(e.arg(0))
        fmt = "np.interp([{expr}],np.linspace(-1,1,{n}),randlist({seed},{n}))[0]" \
              .format(
                  expr=a,
                  n=e.n,
                  seed=e.seed
              )
        return v,fmt

    elif e.op == OpType.RANDOM_VAR:
        v = e.variance
        return [],"np.random.uniform(%f,%f)" \
            % (-v,v)

    elif e.op == OpType.UNIFNOISE:
        nmax = e.bound
        nmin = -nmax
        return [],"np.random.uniform(-%f,%f)" % (nmin,nmax)


    elif e.op == OpType.SIN:
        v,a = to_python(e.arg(0))
        return v,"math.sin(%s.real)" % a

    elif e.op == OpType.COS:
        v,a = to_python(e.arg(0))
        return v,"math.cos(%s.real)" % a


    elif e.op == OpType.SQRT:
        v,a = to_python(e.arg(0))
        return v,"math.sqrt(%s)" % a

    elif e.op == OpType.ABS:
        v,a = to_python(e.arg(0))
        return v,"abs(%s)" % a

    elif e.op == OpType.CALL:
        expr = e.func.expr
        args = e.func.func_args
        vals = e.values
        assigns = dict(zip(args,vals))
        conc_expr = expr.substitute(assigns)
        return to_python(conc_expr)

    elif e.op == OpType.EMIT:
        return to_python(e.arg(0))

    else:
        raise Exception("unimpl: %s" % e)

class OpType(Enum):
    EQ= "="
    MULT= "*"
    INTEG= "int"
    ADD= "+"
    CONST= "const"
    VAR= "var"
    POW= "pow"
    EMIT= "emit"
    EXTVAR= "extvar"
    PAREN = "paren"

    FUNC = "func"
    CALL = "call"
    SGN = "sgn"
    ABS = "abs"
    COS = "cos"
    SIN = "sin"
    SQRT= "sqrt"
    LN= "ln"
    EXP= "exp"
    SQUARE= "pow2"
    RANDFUN = "randfun"
    UNIFNOISE = "uniformnz"
    CLAMP="clamp"
    RANDOM_VAR="rv"

class Op:

    def __init__(self,op,args):
        for arg in args:
            if not (isinstance(arg,Op)):
                raise Exception("not op: %s" % arg)
        self._args = args
        self._op = op
        self._is_associative = True \
                               if op in [OpType.MULT, OpType.ADD] \
                                  else False


    @property
    def op(self):
        return self._op

    @property
    def state_vars(self):
        stvars = {}
        for substvars in self._args():
            for k,v in substvars.items():
                assert(not k in stvars)
                stvars[k] =v
        return stvars

    def handles(self):
        handles = []
        for arg in self._args:
            for handle in arg.handles():
                assert(not handle in handles)
                handles.append(handle)

        return handles

    def toplevel(self):
        return None

    def arg(self,idx):
        return self._args[idx]

    @property
    def args(self):
        return self._args

    def nodes(self):
        child_nodes = sum(map(lambda a: a.nodes(), self._args))
        return 1 + child_nodes

    def depth(self):
        if len(self._args) == 0:
            return 0

        child_depth = max(map(lambda a: a.depth(), self._args))
        return 1 + child_depth


    def __repr__(self):
        argstr = " ".join(map(lambda arg: str(arg),self._args))
        return "(%s %s)" % (self._op.value,argstr)

    def __eq__(self,other):
        assert(isinstance(other,Op))
        return str(self) == str(other)

    def __hash__(self):
        return hash(str(self))

    def bwvars(self):
        return self.vars()

    def vars(self):
        vars = []
        for arg in self._args:
            vars += arg.vars()

        return list(set(vars))

    def to_json(self):
      args = list(map(lambda arg: arg.to_json(), \
                      self._args))
      return {
        'op': self.op.value,
        'args': args
      }

    @staticmethod
    def from_json(obj):
        op = OpType(obj['op'])
        if op == OpType.VAR:
            return Var.from_json(obj)
        elif op == OpType.CONST:
            return Const.from_json(obj)
        elif op == OpType.FUNC:
            return Func.from_json(obj)
        elif op == OpType.MULT:
            return Mult.from_json(obj)
        elif op == OpType.POW:
            return Pow.from_json(obj)
        elif op == OpType.SGN:
            return Sgn.from_json(obj)
        elif op == OpType.ABS:
            return Abs.from_json(obj)
        elif op == OpType.SQRT:
            return Sqrt.from_json(obj)
        elif op == OpType.SIN:
            return Sin.from_json(obj)
        elif op == OpType.COS:
            return Cos.from_json(obj)
        elif op == OpType.ADD:
            return Add.from_json(obj)
        elif op == OpType.RANDFUN:
            return RandFun.from_json(obj)


        else:
            raise Exception("unimpl: %s" % obj)

    def match_op(self,expr):
        if expr.op == self._op:
            return True,False,[zip(self._args,expr.args)]

        else:
            return False,False,None


    def substitute(self,bindings={}):
        raise Exception("substitute not implemented: %s" % self)

    def compute(self,bindings={}):
        raise Exception("compute not implemented: %s" % self)

    # infer bandwidth from interval information
    def infer_interval(self,interval,bound_intervals):
        raise NotImplementedError("unknown infer-interval <%s>" % (str(self)))


    # infer bandwidth from interval information
    def compute_interval(self,intervals):
        raise NotImplementedError("unknown compute-interval <%s>" % (str(self)))

    # infer bandwidth from interval information
    def infer_bandwidth(self,intervals,bandwidths={}):
        raise NotImplementedError("unknown infer-bandwidth <%s>" % (str(self)))


    def match(self,expr):
        def is_consistent(assignments):
            bnds = {}
            for v,e in assignments:
                if not v in bnds:
                    bnds[v] = e
                else:
                    print("%s -> %s :-> %s" % (v,bnds[v],e))
                    raise NotImplementedError

            return True

        can_match,eq_op,bindings = self.match_op(expr)
        if can_match:
            for binding in bindings:
                assigns = []
                submatches = []
                for v,e in binding:
                    if v.op == OpType.VAR:
                        assigns.append((v.name,e))
                    else:
                        submatches2 = []
                        for is_subeq, subassigns in v.match(e):
                            submatches3 = list(map(lambda subassign:
                                     (is_subeq,subassign), subassigns))
                            submatches2.append(submatches3)


                        submatches.append(submatches2)


                if not is_consistent(assigns):
                    continue

                for choices in itertools.product(*submatches):
                    combo = []
                    for choice in choices:
                        combo += choice

                    is_eq_match = eq_op and \
                                  all(map(lambda tup: tup[0], combo))
                    assigns2 = list(map(lambda tup: tup[1], combo))
                    if not is_consistent(assigns+assigns2):
                        continue

                    yield is_eq_match,assigns+assigns2
        else:
            return

class Op2(Op):

    def __init__(self,op,args):
        Op.__init__(self,op,args)
        assert(len(args) == 2)

    @property
    def arg1(self):
        return self._args[0]

    @property
    def arg2(self):
        return self._args[1]

    def compute(self,bindings):
        arg1 = self._args[0].compute(bindings)
        arg2 = self._args[1].compute(bindings)
        return self.compute_op2(arg1,arg2)

    def compute_op2(self,arg1,arg2):
        raise Exception("compute_op2 not implemented: %s" % self)


class Integ(Op2):

    def __init__(self,deriv,init_cond,handle):
        assert(handle.startswith(":"))

        Op.__init__(self,OpType.INTEG,[deriv,init_cond])
        self._handle = handle
        pass

    def substitute(self,bindings):
        inp = self.arg(0).substitute(bindings)
        ic = self.arg(1).substitute(bindings)
        return Integ(inp,ic,self._handle)

    @property
    def handle(self):
        return self._handle

    @property
    def ic_handle(self):
        return self._handle+"[0]"

    @property
    def deriv_handle(self):
        return self._handle+"\'"

    @property
    def init_cond(self):
        return self.arg2

    def coefficient(self):
        return self.deriv.coefficient()

    def handles(self):
        ch = Op.handles(self)
        assert(not self.handle in ch and \
               not self.handle is None)
        ch.append(self.handle)
        ch.append(self.ic_handle)
        ch.append(self.deriv_handle)
        return ch

    def toplevel(self):
        return self.handle

    # infer bandwidth from interval information
    def infer_interval(self,ival,bound_intervals):
        ideriv = self.deriv.compute_interval(bound_intervals)
        icond = self.init_cond.compute_interval(bound_intervals)
        istvar = interval.IntervalCollection(ival)
        icomb = icond.merge(ideriv, istvar.interval)
        icomb.bind(self.deriv_handle, ideriv.interval)
        icomb.bind(self.handle, ival)
        icomb.bind(self.ic_handle, icond.interval)
        return icomb

    def compute_interval(self,intervals):
        assert(not self.handle is None)
        assert(not self.deriv_handle is None)
        istvar = intervals[self._handle]
        ideriv = self.deriv.compute_interval(intervals)
        icond = self.init_cond.compute_interval(intervals)
        if not (istvar.contains(icond.interval)):
            #print("[WARN] stvar does not contain ic: stvar=%s, ic=%s, expr=%s" % \
            #                (istvar,icond,self))
            pass

        icomb = icond.merge(ideriv, istvar)
        icomb.bind(self.deriv_handle, ideriv.interval)
        icomb.bind(self.ic_handle, icond.interval)
        return icomb

    def state_vars(self):
        stvars = Op.state_vars(self)
        stvars[self._handle] = self
        return

    def infer_bandwidth(self,intervals,bandwidths={}):
        icoll = self.compute_interval(intervals)
        bw = bandwidth.Bandwidth.integ(icoll.interval, \
                                  icoll.get(self.deriv_handle))
        return bandwidth.BandwidthCollection(bw)

    def bwvars(self):
        return []


    @property
    def deriv(self):
        return self.arg1

class ExtVar(Op):

    def __init__(self,name,loc=None):
        Op.__init__(self,OpType.EXTVAR,[])
        self._name = name
        self._loc = loc

    def coefficient(self):
        return 1.0

    def sum_terms(self):
        return [self]

    def prod_terms(self):
        return [self]

    @property
    def loc(self):
        return self._loc

    @property
    def name(self):
        return self._name

    def compute_interval(self,bindings):
        return interval.IntervalCollection(bindings[self._name])


    def infer_bandwidth(self,intervals,bandwidths={}):
        return bandwidth.BandwidthCollection(bandwidths[self._name])

    def compute_bandwidth(self,bandwidths):
        assert(self._name in bandwidths)
        return bandwidth.BandwidthCollection(bandwidths[self._name])


    @property
    def name(self):
        return self._name

    def compute(self,bindings):
        return bindings[self._name]

    def __repr__(self):
        return "(%s %s)" % \
            (self._op.value,self._name)

    @staticmethod
    def from_json(obj):
        return ExtVar(obj['name'],obj['physical'])


    def to_json(self):
        obj = Op.to_json(self)
        obj['name'] = self._name
        obj['physical'] = self._physical
        return obj

class Var(Op):

    def __init__(self,name):
        Op.__init__(self,OpType.VAR,[])
        self._name = name

    def coefficient(self):
        return 1.0

    def sum_terms(self):
        return [self]

    def prod_terms(self):
        return [self]

    def to_json(self):
        obj = Op.to_json(self)
        obj['name'] = self._name
        return obj


    def __repr__(self):
        return "(%s %s)" % \
            (self._op.value,self._name)

    @staticmethod
    def from_json(obj):
        return Var(obj['name'])

    @property
    def name(self):
        return self._name

    def infer_interval(self,this_interval,bound_intervals):
        assert(this_interval.contains(bound_intervals[self.name]))
        return interval.IntervalCollection(bound_intervals[self.name])

    def compute_interval(self,intervals):
        if not (self.name in intervals):
            return interval.IntervalCollection(interval.IUnknown())
        else:
            return interval.IntervalCollection(intervals[self.name])

    def infer_bandwidth(self,intervals,bandwidths={}):
        if not self.name in bandwidths:
            print(bandwidths)
            raise Exception("unbound  bandwidth <%s>" % self.name)

        return bandwidth.BandwidthCollection(bandwidths[self.name])


    def compute_bandwidth(self,bandwidths):
        if not (self.name in bandwidths):
            raise Exception("cannot find <%s> in bw-map: <%s>" %\
                            (self.name,bandwidths))

        return bandwidth.BandwidthCollection(bandwidths[self.name])

    def substitute(self,assigns):
        return assigns[self._name]

    def compute(self,bindings):
        if not self._name in bindings:
            for key in bindings:
                print(key)
            raise Exception("<%s> not bound" % self._name)

        return bindings[self._name]

    def match_op(self,expr):
        return True,True,[[(self,expr)]]


    def vars(self):
        return [self._name]

class Const(Op):

    def __init__(self,value,tag=None):
        Op.__init__(self,OpType.CONST,[])
        self._value = float(value)

    def to_json(self):
        obj = Op.to_json(self)
        obj['value'] = self._value
        return obj

    def substitute(self,bindings):
        return Const(self._value)

    @staticmethod
    def from_json(obj):
        return Const(obj['value'])


    def coefficient(self):
        return self.value

    def sum_terms(self):
        return [self]

    def prod_terms(self):
        return []

    def compute(self,bindings):
        return self._value

    def compute_interval(self,bindings):
        return interval.IntervalCollection(
            interval.IValue(self._value)
        )

    def infer_bandwidth(self,intervals,bandwidths={}):
        return self.compute_bandwidth(bandwidths)

    def compute_bandwidth(self,bandwidths):
        return bandwidth.BandwidthCollection(bandwidth.Bandwidth(0))

    @property
    def value(self):
        return self._value

    def match_op(self,expr):
        if expr.op == self.op and \
           expr.value == self.value:
            return True,True,[]

        else:
            return False,None,None

    def __repr__(self):
        return "(%s %s)" % \
            (self._op.value,self._value)





class Emit(Op):

    def __init__(self,node,loc=None):
        Op.__init__(self,OpType.EMIT,[node])
        self._loc = loc
        pass

    @property
    def loc(self):
        return self._loc

    def infer_bandwidth(self,intervals,bandwidths={}):
        return self.arg(0).infer_bandwidth(intervals,bandwidths)


    def compute_bandwidth(self,bandwidths):
        return self.arg(0).compute_bandwidth(bandwidths)

    def infer_interval(self,this_interval,bound_intervals):
        return self.arg(0).infer_interval(this_interval,bound_intervals)

    def compute_interval(self,intervals):
        return self.arg(0).compute_interval(intervals)


    def compute(self,bindings):
        return self.arg(0).compute(bindings)


class Mult(Op2):

    def __init__(self,arg1,arg2):
        Op2.__init__(self,OpType.MULT,[arg1,arg2])
        pass


    @staticmethod
    def from_json(obj):
        return Mult(Op.from_json(obj['args'][0]),
                    Op.from_json(obj['args'][1]))

    def coefficient(self):
        return self.arg1.coefficient()*self.arg2.coefficient()

    def prod_terms(self):
        return self.arg1.prod_terms()+self.arg2.prod_terms()

    def sum_terms(self):
        return [self]

    def substitute(self,assigns):
        return Mult(self.arg1.substitute(assigns),
                    self.arg2.substitute(assigns))


    def infer_interval(self,this_interval,bound_intervals):
        icoll = self.compute_interval(bound_intervals)
        assert(this_interval.contains(icoll.interval))
        return icoll

    def compute_interval(self,intervals):
        is1 = self.arg1.compute_interval(intervals)
        is2 = self.arg2.compute_interval(intervals)
        return is1.merge(is2,
                  is1.interval.mult(is2.interval))

    def infer_bandwidth(self,intervals,bandwidths={}):
        bw1 = self.arg1.infer_bandwidth(intervals,bandwidths)
        bw2 = self.arg2.infer_bandwidth(intervals,bandwidths)
        return bw1.merge(bw2,
                         bw1.bandwidth.mult(bw2.bandwidth))

    def compute_bandwidth(self,bandwidths):
        bw1 = self.arg1.compute_bandwidth(bandwidths)
        bw2 = self.arg2.compute_bandwidth(bandwidths)
        return bw1.merge(bw2,
                         bw1.bandwidth.mult(bw2.bandwidth))


    def match_op(self,expr):
        if expr.op == self._op:
            return True,False,[
                [(self.arg1,expr.arg1),(self.arg2,expr.arg2)],
                [(self.arg1,expr.arg2),(self.arg2,expr.arg1)]
            ]

        elif expr.op == OpType.SQUARE:
            return True,False,[
                [(self.arg1,expr.base),(self.arg2,expr.base)]
            ]

        else:
            return True,True,[
                [(self.arg1,expr),(self.arg2,Const(1))],
                [(self.arg1,Const(1)),(self.arg2,expr)]
            ]


    def compute_op2(self,arg1,arg2):
        return arg1*arg2


class Add(Op2):

    def __init__(self,arg1,arg2):
        Op.__init__(self,OpType.ADD,[arg1,arg2])
        pass

    @staticmethod
    def from_json(obj):
        return Add(Op.from_json(obj['args'][0]), \
                   Op.from_json(obj['args'][1]))


    def coefficient(self):
        return 1.0

    def prod_terms(self):
        return [self]

    def sum_terms(self):
        return self.arg1.sum_terms() + self.arg2.sum_terms()


    def substitute(self,args):
        return Add(
            self.arg(0).substitute(args),
            self.arg(1).substitute(args)
        )


    def compute_interval(self,bindings):
        is1 = self.arg1.compute_interval(bindings)
        is2 = self.arg2.compute_interval(bindings)
        return is1.merge(is2,
                  is1.interval.add(is2.interval))


    def infer_bandwidth(self,intervals,bandwidths):
        bw1 = self.arg1.infer_bandwidth(intervals,bandwidths)
        bw2 = self.arg2.infer_bandwidth(intervals,bandwidths)
        return bw1.merge(bw2,
                         bw1.bandwidth.add(bw2.bandwidth))


    def compute_bandwidth(self,bandwidths):
        bw1 = self.arg1.compute_bandwidth(bandwidths)
        bw2 = self.arg2.compute_bandwidth(bandwidths)
        return bw1.merge(bw2,
                         bw1.bandwidth.add(bw2.bandwidth))


    def match_op(self,expr,enable_eq=False):
        if expr.op == self._op:
            return True,False,[
                [(self.arg1,expr.arg1),(self.arg2,expr.arg2)],
                [(self.arg1,expr.arg2),(self.arg2,expr.arg1)]
            ]

        else:
            return True,True,[
                [(self.arg1,expr),(self.arg2,Const(0))],
                [(self.arg1,Const(0)),(self.arg2,expr)]
            ]

    def compute_op2(self,arg1,arg2):
        return arg1+arg2




class Call(Op):
    def __init__(self, params, expr):
        self._func = expr
        self._params = params
        self._expr = self._func.apply(self._params)
        Op.__init__(self,OpType.CALL,params+[self._expr])
        assert(expr.op == OpType.FUNC)

    def coefficient(self):
        raise Exception("bind call function to its own variable please")

    def compute(self,bindings):
        new_bindings = {}
        for func_arg,var in zip(self._func.func_args,self._params):
            expr = var.compute(bindings)
            new_bindings[func_arg] = expr

        value = self._func.compute(new_bindings)
        return value

    @property
    def func(self):
        return self._func

    @property
    def values(self):
        for v in self._params:
            yield v

    def concretize(self):
        return self._expr

    def infer_bandwidth(self,intervals,bandwidths):
        return self.concretize().infer_bandwidth(intervals,bandwidths)

    def compute_bandwidth(self,bws):
        return self.concretize().compute_bandwidth(bws)

    def compute_interval(self,ivals):
        return self.concretize().compute_interval(ivals)

    def to_json(self):
        obj = Op.to_json(self)
        pars = []
        for par in self._params:
            pars.append(par.to_json())
        obj['expr'] = self._expr.to_json()
        obj['values'] = pars
        return obj


    def __repr__(self):
        pars = " ".join(map(lambda p: str(p), self._params))
        return "call %s %s" % (pars,self._func)


class Func(Op):
    def __init__(self, params, expr):
        Op.__init__(self,OpType.FUNC,[])
        self._expr = expr
        self._vars = params

    def compute(self,bindings):
        for v in self._vars:
            assert(v in bindings)

        return self._expr.compute(bindings)

    @property
    def expr(self):
        return self._expr

    @property
    def func_args(self):
        return self._vars

    def to_json(self):
        obj = Op.to_json(self)
        obj['expr'] = self._expr.to_json()
        obj['vars'] = self._vars
        return obj

    @staticmethod
    def from_json(obj):
        expr = Op.from_json(obj['expr'])
        varnames = obj['vars']
        return Func(list(varnames),expr)

    def apply(self,values):
        assert(len(values) == len(self._vars))
        assigns = dict(zip(self._vars,values))
        return self._expr.substitute(assigns)

    def __repr__(self):
        pars = " ".join(map(lambda p: str(p), self._vars))
        return "lambd(%s).(%s)" % (pars,self._expr)

class Clamp(Op):

    def __init__(self,arg,ival):
        Op.__init__(self,OpType.CLAMP,[arg])
        self._interval = ival

    @property
    def arg1(self):
        return self.arg(0)

    @property
    def interval(self):
        return self._interval

    def compute(self,bindings):
        result = self.arg(0).compute(bindings)
        return self._interval.clamp(result)

    def __repr__(self):
        return "clamp(%s,%s)" % (self.arg(0), \
                              self._interval)

class RandomVar(Op):
    def __init__(self,variance):
        Op.__init__(self,OpType.RANDOM_VAR,[])
        self._variance = variance

    @property
    def variance(self):
        return self._variance

    def compute(self,bindings):
        raise Exception("random variable")

class Paren(Op):

    def __init__(self,arg):
        Op.__init__(self,OpType.PAREN,[arg])
        pass

    @staticmethod
    def from_json(obj):
        return Paren(Op.from_json(obj['args'][0]))

    def compute(self,bindings):
        return self.arg(0).compute(bindings)


    def substitute(self,args):
        return Paren(self.arg(0).substitute(args))

    def compute_interval(self,ivals):
        return self.arg(0).compute_interval(ivals)


    # bandwidth is infinite if number is ever negative
    def infer_bandwidth(self,ivals,bandwidths={}):
        return self.arg(0).infer_bandwidth(ivals,bandwidths)


class Abs(Op):

    def __init__(self,arg):
        Op.__init__(self,OpType.ABS,[arg])
        pass

    @staticmethod
    def from_json(obj):
        return Abs(Op.from_json(obj['args'][0]))

    def compute(self,bindings):
        return abs(self.arg(0).compute(bindings))


    def substitute(self,args):
        return Abs(self.arg(0).substitute(args))

    def compute_interval(self,ivals):
        ivalcoll = self.arg(0).compute_interval(ivals)
        ivalcoll.update(ivalcoll.interval.abs())
        return ivalcoll


    # bandwidth is infinite if number is ever negative
    def infer_bandwidth(self,ivals,bandwidths={}):
        bwcoll = self.arg(0).infer_bandwidth(ivals,bandwidths)
        # 2*sin(pi*a/2)*gamma(alpha+1)/(2*pi*eta)^{alpha+1}
        bwcoll.update(bandwidth.InfBandwidth())
        return bwcoll


class RandFun(Op):

    def __init__(self,arg,n=100,seed=None):
        Op.__init__(self,OpType.RANDFUN,[arg])
        self.n = n
        if seed is None:
            self.seed = random.randint(0,1000000)
        else:
            self.seed = seed

    @staticmethod
    def from_json(obj):
        rf = RandFun(Op.from_json(obj['args'][0]), \
                     obj['n'], \
                     obj['seed'])
        return rf

    def substitute(self,assigns):
        rf = RandFun(self.arg(0).substitute(assigns), \
                     self.n,self.seed)
        return rf

    def compute(self,bindings):
        raise NotImplementedError

    def infer_bandwidth(self,intervals,bandwidths):
        bwcoll = self.arg(0).infer_bandwidth(intervals,bandwidths)
        bwcoll.update(bandwidth.InfBandwidth())
        return bwcoll
 
    def compute_interval(self,ivals):
        ivalcoll = self.arg(0).compute_interval(ivals)
        new_ival = interval.Interval(-1,1)
        ivalcoll.update(new_ival)
        return ivalcoll


    def to_json(self):
        obj = Op.to_json(self)
        obj['n'] = self.n
        obj['seed'] = self.seed
        return obj

class Sgn(Op):

    def __init__(self,arg):
        Op.__init__(self,OpType.SGN,[arg])
        pass

    @staticmethod
    def from_json(obj):
        return Sgn(Op.from_json(obj['args'][0]))

    def substitute(self,assigns):
        return Sgn(self.arg(0).substitute(assigns))

    def compute(self,bindings):
        return math.copysign(1.0,self.arg(0).compute(bindings).real)


    def infer_bandwidth(self,intervals,bandwidths):
        bwcoll = self.arg(0).infer_bandwidth(intervals,bandwidths)
        bwcoll.update(bandwidth.InfBandwidth())
        return bwcoll
 
    def compute_interval(self,ivals):
        ivalcoll = self.arg(0).compute_interval(ivals)
        new_ival = ivalcoll.interval.sgn()
        ivalcoll.update(new_ival)
        return ivalcoll

class Ln(Op):

    def __init__(self,arg):
        Op.__init__(self,OpType.LN,[arg])
        pass


class Exp(Op):

    def __init__(self,arg):
        Op.__init__(self,OpType.EXP,[arg])
        pass


class Sin(Op):

    def __init__(self,arg1):
        Op.__init__(self,OpType.SIN,[arg1])
        pass

    def compute(self,bindings):
        return math.sin(self.arg(0).compute(bindings).real)


    def substitute(self,args):
        return Sin(self.arg(0).substitute(args))

    @staticmethod
    def from_json(obj):
        return Sin(Op.from_json(obj['args'][0]))

    def compute_interval(self,ivals):
        ivalcoll = self.arg(0).compute_interval(ivals)
        ivalcoll.update(interval.Interval.type_infer(-1,1))
        return ivalcoll

    def infer_bandwidth(self,intervals,bandwidths={}):
        argival = self.arg(0).compute_interval(intervals)
        rad_to_hz = 1.0/(2.0*math.pi)
        bw = argival.interval.scale(rad_to_hz)

        bwcoll = self.arg(0).compute_bandwidth(bandwidths)
        bwcoll.update(bandwidth.Bandwidth(bw.bound))
        return bwcoll

class Cos(Op):

    def __init__(self,arg1):
        Op.__init__(self,OpType.COS,[arg1])
        pass

    def compute(self,bindings):
        return math.cos(self.arg(0).compute(bindings).real)


    @staticmethod
    def from_json(obj):
        return Cos(Op.from_json(obj['args'][0]))


    def substitute(self,args):
        return Cos(self.arg(0).substitute(args))

    # bandwidth is infinite if number is ever negative
    def compute_bandwidth(self,bws):
        bwcoll = self.arg(0).compute_bandwidth(bws)
        # 2*sin(pi*a/2)*gamma(alpha+1)/(2*pi*eta)^{alpha+1}
        bwcoll.update(bandwidth.InfBandwidth())
        return bwcoll

    def compute_interval(self,ivals):
        ivalcoll = self.arg(0).compute_interval(ivals)
        ivalcoll.update(interval.Interval.type_infer(-1,1))
        return ivalcoll


    def infer_bandwidth(self,intervals,bandwidths={}):
        argival = self.arg(0).compute_interval(intervals)
        rad_to_hz = 1.0/(2.0*math.pi)
        bw = argival.interval.scale(rad_to_hz)

        bwcoll = self.arg(0).compute_bandwidth(bandwidths)
        bwcoll.update(bandwidth.Bandwidth(bw.bound))
        return bwcoll






class UniformNoise(Op):

    def __init__(self,bound,frequency=0.01,period=1.0,seed=5):
        Op.__init__(self,OpType.UNIFNOISE,[])
        self._bound = bound
        self._frequency = frequency
        self._period = period
        self._n = int(self._period/self._frequency)
        np.random.seed(seed)
        self._buf = list(map(lambda i: \
                             np.random.uniform(-self._bound,
                                               self._bound), \
                             range(0,self._n)))

        pass

    @property
    def bound(self):
        return self._bound

    def compute(self,bindings):
        # note: the closer to random noise it is, the harder
        # it is to use a solver
        t = bindings['t']
        i = int((float(t)/self._frequency)) % self._n
        value = self._buf[i]
        return value




class Pow(Op):

    def __init__(self,arg1,arg2):
        Op.__init__(self,OpType.POW,[arg1,arg2])
        pass

    @property
    def arg1(self):
        return self.arg(0)
    @property
    def arg2(self):
        return self.arg(1)

    @staticmethod
    def from_json(obj):
        return Pow(Op.from_json(obj['args'][0]), \
                   Op.from_json(obj['args'][1]))


    # bandwidth is infinite if number is ever negative
    def infer_bandwidth(self,ivals,bws):
        bwcoll = self.arg(0).infer_bandwidth(ivals,bws)
        # 2*sin(pi*a/2)*gamma(alpha+1)/(2*pi*eta)^{alpha+1}
        bwcoll.update(bandwidth.InfBandwidth())
        return bwcoll

    def compute_interval(self,ivals):
        bcoll = self.arg(0).compute_interval(ivals)
        ecoll = self.arg(1).compute_interval(ivals)
        new_ival = bcoll.interval.exponent(ecoll.interval)
        rcoll = bcoll.merge(ecoll, new_ival)
        return rcoll

    def substitute(self,args):
        return Pow(
            self.arg(0).substitute(args),
            self.arg(1).substitute(args)
        )


    def compute(self,bindings):
        return self.arg(0).compute(bindings)**self.arg(1).compute(bindings)



class Sqrt(Op):

    def __init__(self,arg):
        Op.__init__(self,OpType.SQRT,[arg])
        pass


    @staticmethod
    def from_json(obj):
        return Sqrt(Op.from_json(obj['args'][0]))


    def compute(self,bindings):
        return math.sqrt(self.arg(0).compute(bindings))

    # bandwidth is infinite if number is ever negative
    def infer_bandwidth(self,ivals,bws):
        bwcoll = self.arg(0).infer_bandwidth(ivals,bws)
        # 2*sin(pi*a/2)*gamma(alpha+1)/(2*pi*eta)^{alpha+1}
        bwcoll.update(bandwidth.InfBandwidth())
        return bwcoll

    def compute_interval(self,ivals):
        ivalcoll = self.arg(0).compute_interval(ivals)
        ivalcoll.update(ivalcoll.interval.sqrt())
        return ivalcoll

    def match_op(self,expr,enable_eq=False):
        if expr.op == self._op:
            return True,False,[[self.base,expr.base]]

        elif expr.op == OpType.POW:
            if expr.exponent.op == OpType.CONST and \
               expr.exponent.value == 0.5:
                return True,False,[[self.base,expr.base]]

        return False,False,None


    @property
    def exponent(self):
        return Const(0.5)

    def substitute(self,args):
        return Sqrt(self.arg(0).substitute(args))

class Square(Op):

    def __init__(self,arg):
        Op.__init__(self,OpType.SQUARE,[arg])
        pass

    def match_op(self,expr, enable_eq=False):
        if expr.op == self._op:
            return True,False,[[(self.base,expr.base)]]

        elif expr.op == OpType.POW:
            if expr.exponent.op == OpType.CONST and \
               expr.exponent.value == 2.0:
                return True,False,[[(self.base,expr.base)]]

            elif expr.exponent.op == OpType.MULT and \
                 expr.arg1 == expr.arg2 and \
                 expr.arg1.op == OpType.VAR:
                return True,False,[[(self.base,expr.arg1)]]

        return False,None,None



    @property
    def exponent(self):
        return Const(2)

def Div(a,b):
    return Mult(a,Pow(b,Const(-1)))

def mkadd(terms):
    if len(terms) == 0:
        return Const(0)
    elif len(terms) == 1:
        return terms[0]
    elif len(terms) == 2:
        return Add(terms[0],terms[1])
    else:
        curr = Add(terms[0],terms[1])
        for i in range(2,len(terms)):
            curr = Add(curr,terms[i])
        return curr
