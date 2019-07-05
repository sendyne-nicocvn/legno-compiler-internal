if __name__ == "__main__":
  import sys
  import os
  sys.path.insert(0,os.path.abspath("../../../"))


from lang.prog import MathProg
from ops import op, opparse
from bmark.bmarks.common import *
from bmark.bmarks.other.bbsys import build_std_bb_sys
import math
import bmark.menvs as menvs

def emit(v):
  return op.Emit(op.Mult(op.Const(0.99999), v), loc="A0")


def model():
  prob = MathProg("robot")
  sin_fun = op.Func(['T'], op.Sin(op.Var('T')))
  cos_fun = op.Func(['T'], op.Cos(op.Var('T')))

  ampl = 0.5
  W,V = build_std_bb_sys(prob,ampl,0)
  params = {
    'DEG0' : 0,
    'X0': 0,
    'Y0': 0,
    'W': W,
    'V': V,
    'one':0.999999
  }
  DEG = parse_diffeq('{one}*{V}', 'DEG0', ':t', params)
  X = parse_diffeq('{one}*{V}*COS', 'X0',':u', params)
  Y = parse_diffeq('{one}*{V}*SIN', 'Y0',':v', params)
  prob.bind('DEG',DEG)
  prob.bind('X',X)
  prob.bind('Y',Y)
  prob.bind('SIN', op.Call([op.Var('DEG')], sin_fun))
  prob.bind('COS', op.Call([op.Var('DEG')], cos_fun))
  prob.bind('Rot', emit(op.Var('Y')))
  pos = 1.0
  xrng = 1.5
  yrng = 2.5
  degrng = 0.5
  prob.set_interval("X",-xrng,xrng)
  prob.set_interval("Y",0,yrng)
  prob.set_interval("DEG",-degrng,degrng)
  # W
  prob.set_max_sim_time(200)
  prob.compile()
  menv = menvs.get_math_env('t200')
  return menv,prob

def execute():
  menv,prob = model()
  plot_diffeq(menv,prob)


if __name__ == "__main__":
  execute()
