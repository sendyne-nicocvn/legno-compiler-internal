import sys
from enum import Enum
import math
import numpy as np

import util.util as util

import ops.op as op
import ops.opparse as opparse
from ops.interval import Interval

def _evaluate(expr,vmap):
    vmap['math'] = math
    vmap['np'] = np
    vmap['randlist'] = util.randlist
    return np.real(eval(expr,vmap))

class DSProgDB:
    PROGRAMS = {}

    @staticmethod
    def register(name,dsprog,dssim):
        assert(not name in DSProgDB.PROGRAMS)
        DSProgDB.PROGRAMS[name] = (dsprog,dssim)

    @staticmethod
    def get_sim(name):
        DSProgDB.load()
        prog,sim = DSProgDB.PROGRAMS[name]
        return sim()

    @staticmethod
    def get_prog(name):
        DSProgDB.load()
        prog,sim = DSProgDB.PROGRAMS[name]
        prob = DSProg(name)
        return prog(prob)

    @staticmethod
    def execute(name):
        prog,sim = DSProgDB.get(name)
        plot_diffeq(sim(), \
                    prog())

    @staticmethod
    def load():
        if len(DSProgDB.PROGRAMS) == 0:
            import progs

    def name(self):
        return NotImplementedError

class DSProg:
    class ExprType(Enum):
        INTEG = "integ"
        EXTERN = "extern"
        FN = "fn"

    def __init__(self,name):
        self._name = name
        self._bindings = {}
        self._lambdas = {}
        self._intervals = {}
        self._variables = []
        self.max_time = 100.0

        self.__order = None
        self.__order_integs = None
        self.__types = None
        self.__handles = 0



    def _compute_order(self):
        self.__order = []
        self.__order_integs = []
        self.__types = {}
        fns = []
        for var in self._variables:
            if not (var in self._bindings):
                continue

            if self._bindings[var].op == op.OpType.INTEG:
                self.__types[var] = DSProg.ExprType.INTEG
                self.__order.append(var)
                self.__order_integs.append(var)
            elif self._bindings[var].op == op.OpType.EXTVAR:
                self.__types[var] = DSProg.ExprType.EXTERN
                self.__order.append(var)

            else:
                self.__types[var] = DSProg.ExprType.FN
                fns.append(var)

        while not util.values_in_list(fns,self.__order):
            progress = False
            for var in fns:
                variables = self._bindings[var].vars()
                if util.values_in_list(variables,self.__order):
                    self.__order.append(var)
                    progress = True
            assert(progress)


    def build_ode_prob(self):
        ics = {}
        fns = {}
        derivs = {}
        deriv_vars = []
        fn_vars = []
        for var in self.__order:
            typ = self.__types[var]
            if typ == DSProg.ExprType.INTEG:
                _,ics[var] = op.to_python(self._bindings[var].init_cond)
                _,derivs[var] = op.to_python(self._bindings[var].deriv)
                deriv_vars.append(var)
            else:
                _,fns[var] = op.to_python(self._bindings[var])
                fn_vars.append(var)
        return deriv_vars,ics,derivs, \
            fn_vars,fns


    def variables(self):
        return self._variables


    def _bind(self,var,expr):
        assert(not var in self._bindings)
        self._variables.append(var)
        self._bindings[var] = expr

    def decl_stvar(self,var,deriv,ic="0.0",params={}):
        deriv = opparse.parse(deriv.format(**params))
        ic = opparse.parse(ic.format(**params))
        handle = ":h%d" % self.__handles
        expr = op.Integ(deriv,ic,handle=handle)
        self.__handles += 1
        self._bind(var,expr)

    def decl_var(self,var,expr,params={}):
        expr_conc = expr.format(**params)
        return opparse.parse(expr_conc)


    def emit(self,varexpr,obsvar,params={},loc='A0'):
        expr_conc = varexpr.format(**params)
        obj = opparse.parse(expr_conc)
        self._bind(obsvar,op.Emit(obj,loc='A0'))

    def decl_lambda(self,var,expr,params={}):
        expr_conc = opparse.parse(expr.format(**params))
        self._lambdas[var] = expr_conc

    def bindings(self):
        for var,expr in self._bindings.items():
            yield var,expr

    def binding(self,v):
        if not v in self._bindings:
            return None
        return self._bindings[v]

    def get_interval(self,v):
        return self._intervals[v]

    def interval(self,v,min_v,max_v):
        assert(min_v <= max_v)
        if not v in self._variables:
            self._variables.append(v)
        self._intervals[v] = Interval.type_infer(min_v,max_v)

    def intervals(self):
        for v,ival in self._intervals.items():
            yield v,ival


    def check(self):
        for variable,expr in self._bindings.items():
            if not (variable in self._intervals):
                if expr is None:
                    raise Exception("cannot infer ival: <%s> has no expression" \
                                    % variable)

                icoll = expr.infer_interval(self._intervals)
                self._intervals[variable] = icoll.interval


        if not (util.keys_in_dict(self._bindings.keys(), self._intervals)):
            for k in self._bindings.keys():
                if not k in self._intervals:
                    print("  :no ival %s" % k)
                else:
                    print("  :ival %s" % k)
            raise Exception("can't compile %s: missing intervals" % self.name)


        self._compute_order()

    @property
    def name(self):
        return self._name

    def __repr__(self):
        s = "prog %s\n" % self._name
        for v,e in self._bindings.items():
            s += "  %s=%s\n" % (v,e)
        s += "\n"
        for v,i in self._intervals.items():
            s += "  iv %s=%s\n" % (v,i)


        return s

    def _execute(self,dssim):
        from scipy.integrate import ode
        stvars,ics,derivs,fnvars,fns = self.build_ode_prob()

        def dt_func(t,values):
            vs = dict(zip(map(lambda v: "%s_" % v, stvars), \
                        values))
            for fvar in fnvars:
                vs["%s_" % fvar] = _evaluate(fns[fvar],vs)

            next_vs = {}
            for stvar in stvars:
                next_vs[stvar] = _evaluate(derivs[stvar],vs)

            return list(map(lambda v: next_vs[v],stvars))

        time = dssim.sim_time
        n = 1000.0
        dt = time/n
        r = ode(dt_func).set_integrator('zvode',method='bdf')
        x0 = list(map(lambda v: _evaluate(ics[v],{}),stvars))
        r.set_initial_value(x0,t=0.0)
        T = []
        Y = []
        tqdm_segs = 500
        last_seg = 0
        while r.successful() and r.t < time:
            T.append(r.t)
            Y.append(r.y)
            r.integrate(r.t + dt)
            seg = int(tqdm_segs*float(r.t)/float(time))

        return T,Y


    def execute(self,dssim):
        T,Y = self._execute(dssim)
        stvars,ics,derivs,fnvars,fns = self.build_ode_prob()

        def fn_func(t,values):
            vs = dict(zip(map(lambda v: "%s_" % v, stvars), \
                            values))
            vals = {}
            for fvar in fnvars:
                vals[fvar] = _evaluate(fns[fvar],vs)
                vs["%s_" % fvar] = vals[fvar]
            for v in stvars:
                vals[v] = vs['%s_' % v]
            return vals

        Z =dict(map(lambda v: (v,[]), stvars+fnvars))
        for t,y in zip(T,Y):
            for var,value in fn_func(t,y).items():
                Z[var].append(value)


        return T,Z
