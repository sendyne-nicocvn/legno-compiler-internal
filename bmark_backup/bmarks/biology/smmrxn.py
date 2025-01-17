if __name__ == "__main__":
  import sys
  import os
  sys.path.insert(0,os.path.abspath("../../../"))

from lang.prog import MathProg
from ops import op, opparse
from bmark.bmarks.common import *
import math
import bmark.menvs as menvs


def model(big=False):
  prob = MathProg("smmrxn%s" % ("big" if big else ""))
  if big:
    params = {
      'E0': 6800,
      'S0': 4400,
      'ES0': 0.0,
      'kf': 0.0001,
      'kr': 0.01,
      'one': 0.9999
    }

  else:
    params = {
      'E0': 0.15,
      'S0': 0.11,
      'ES0': 0.0,
      'kf': 0.1,
      'kr': 0.9999,
      'one': 0.9999
    }
    # reparametrization
    params = {
      'E0': 0.8,
      'S0': 0.5,
      'ES0': 0.0,
      'kf': 0.999,
      'kr': 0.5,
      'one': 0.9999
    }


  ES = parse_diffeq("(({kf}*E)*S) + {kr}*(-ES)", "ES0", ":z", params)
  #E = parse_diffeq("(({kf}*(-E))*S) + {kr}*(ES)", "E0", ":y", params)
  #S = parse_diffeq("(({kf}*(-E))*S) + {kr}*(ES)", "S0", ":x", params)
  E = parse_fn("{E0} + {one}*(-ES)",params)
  S = parse_fn("{S0} + {one}*(-ES)",params)
  prob.bind("E",E)
  prob.bind("S",S)
  prob.bind("ES",ES)
  prob.set_interval("E",-params['E0'],params['E0'])
  prob.set_interval("S",-params['S0'],params['S0'])
  max_ES = min(params['E0'],params['S0'])
  prob.set_interval("ES",-max_ES,max_ES)
  prob.bind("COMPLEX", op.Emit(
    op.Mult(op.Const(params['one']),op.Var("ES")),
    loc="A0"
  ))
  #prob.bind("COMPLEX", op.Emit(op.Var("ES"),loc="A0"))
  prob.set_max_sim_time(20)
  prob.compile()
  menv = menvs.get_math_env('t20')
  return menv,prob

def execute(big):
  menv,prob = model(big)
  T,Y = run_diffeq(menv,prob)
  plot_diffeq(menv,prob)


if __name__ == "__main__":
  execute(True)
  execute(False)
