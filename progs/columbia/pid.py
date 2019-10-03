from dslang.dsprog import DSProg
from dslang.dssim import DSSim
import progs.prog_util as prog_util

def dsname():
  return "pid"

def dsinfo():
  return DSInfo(dsname(), \
                "PI controller",
                "velocity",
                "m/s")

def dsprog(prob):
  params = {
    "initial": 0.0,
    "one":0.99999
  }

  ampl = 0.5
  freq = 0.1
  prog_util.build_oscillator(prob,ampl,freq,"PERTURB","SIG")
  PLANT = "CTRL+{one}*SIG"
  ERROR = "PLANT+{one}*(-SIG)"
  CONTROL = "0.8*(-ERR)+0.9*(-INTEG)"
  INTEGRAL = "ERR+0.2*(-INTEG)"

  #prob.decl_var("SIG",SIG,params)
  prob.decl_var("ERR",ERROR,params)
  prob.decl_var("CTRL",CONTROL,params)
  prob.decl_stvar("INTEG",INTEGRAL,"{initial}",params)
  prob.decl_stvar("PLANT",PLANT,"{initial}",params)

  prob.emit("{one}*PLANT","TrackedSig",params)
  #prob.emit("{one}*ERROR","TrackingError",params)
  for v in ['PLANT','CTRL','ERR','SIG','INTEG']:
    prob.interval(v,-1,1)

  print(prob)
  prob.check()

def dssim():
  exp = DSSim('t200')
  exp.set_sim_time(200)
  return exp
