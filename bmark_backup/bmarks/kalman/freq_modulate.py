
if __name__ == "__main__":
  import sys
  import os
  sys.path.insert(0,os.path.abspath("../../../"))

from bmark.bmarks.common import *
from lang.prog import MathProg
from ops import op, opparse
import bmark.menvs as menvs
from bmark.bmarks.other.closed_form import *

def model():
  params = {
    'meas_noise':0.3,
    'proc_noise':0.2,
    'W0':0.0,
    'V0':0.0,
    'X0':0.0,
    'Pinit':1.0,
    'one':0.9999
  }
  prob = MathProg("KFreqModulate")

  params['Q'] = params['meas_noise']
  params['Rinv'] = 1.0/params['proc_noise']
  params['nRinv'] = -params['Rinv']

  build_cos(prob,"1.0",1.0,"Z")

  E = parse_fn("{one}*Z+{one}*(-X)",params)
  dW = parse_diffeq("{Rinv}*P13*E", \
                    "W0", \
                    ':w', \
                    params)
  dV = parse_diffeq("X*(-W) + {Rinv}*P23*E", \
                    "V0", \
                    ":v", \
                    params)
  dX = parse_diffeq("V + {Rinv}*(P33)*E",\
                    "X0", \
                    ":x", \
                    params)

  #square_fun = op.Func(['V'], op.Mult(op.Var('V'),\
  #                                  op.Var('V')))

  dP11 = parse_diffeq("{Q}+{nRinv}*(P13*P13)",
                    "Pinit",
                    ":p11",
                    params)


  dP12 = parse_diffeq("P11*(-X)+P13*(-W)+{Q}+{nRinv}*(P13*P23)",
                   "Pinit",
                    ":p12",
                    params)


  dP13 = parse_diffeq("P12 +{Q}+ {nRinv}*(P13*P33)",
                    "Pinit",
                    ":p13",
                    params)

  dP22 = parse_diffeq("2.0*P12*(-X)+2.0*P23*(-W)+{Q} + {nRinv}*(P23*P23)",
                    "Pinit",
                    ":p22",
                    params)

  dP23 = parse_diffeq("P13*(-X) + P33*(-W)+ P22 +{Q} + {nRinv}*(P23*P33)",
                    "Pinit",
                    ":p23",
                    params)

  dP33 = parse_diffeq("2.0*P23 +{Q}+ {nRinv}*(P33*P33)",
                    "Pinit",
                    ":p33",
                    params)

  prob.bind("E",E)
  prob.bind("X",dX)
  prob.bind("V",dV)
  prob.bind("W",dW)
  prob.bind("P11",dP11)
  prob.bind("P12",dP12)
  prob.bind("P13",dP13)
  prob.bind("P22",dP22)
  prob.bind("P23",dP23)
  prob.bind("P33",dP33)

  for cov in ['11','12','13','22','23','33']:
    prob.set_interval("P%s" % cov,-1.2,1.2)

  prob.set_interval("X",-1.0,1.0)
  prob.set_interval("V",-1.0,1.0)
  prob.set_interval("W",-1.0,1.0)

  measure_var(prob,"W","FREQSQ")
  prob.set_max_sim_time(200)
  prob.compile()
  menv = menvs.get_math_env('t200')
  return menv,prob


def execute():
  menv,prob = model()
  plot_diffeq(menv,prob)


if __name__ == "__main__":
  execute()


