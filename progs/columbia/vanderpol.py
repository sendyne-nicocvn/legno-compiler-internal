
def dsname():
  return "vanderpol"

def dsprog(prog):
  params = {
    'mu': 0.2,
    'Y0': 0.0,
    'X0': -0.5,
    'one':0.9999
  }
  dY = "(Y*{mu}*(1.0+(-X)*X) + {one}*(-X))"
  dX = "{one}*Y"
  prog.decl_stvar("Y",dY,"{Y0}",params)
  prog.decl_stvar("X",dX,"{X0}",params)
  prog.emit("{one}*X","OSC",params)
  prog.interval("X",-2.5,2.5)
  prog.interval("Y",-2.5,2.5)
  prog.check()
  return prog

def dssim():
  exp = DSSim('t50')
  exp.set_sim_time(50)
  return exp