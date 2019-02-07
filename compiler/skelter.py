import ops.op as op
import numpy as np
import ops.interval as interval
import compiler.common.evaluator_symbolic as evaluator
from compiler.common import prop_noise, prop_bias, prop_delay

def compute_snr(nz_eval,circ,block_name,loc,port):
  config = circ.config(block_name,loc)

  config = circ.config(block_name,loc)
  scf = config.scf(port)
  signal = config.interval(port).scale(scf)
  noise_mean,noise_var = nz_eval.get(block_name,loc,port)

  snr = np.log10(signal.bound/(noise_var))
  print("signal: %s" % signal)
  print("noise: %s" % noise_var)
  print("snr: %s" % snr)
  return snr

def rank(circ):
  score = 0
  nz_eval = evaluator.propagated_noise_evaluator(circ)

  # mismatch in seconds
  for handle,block_name,loc in circ.board.handles():
      if circ.in_use(block_name,loc):
        config = circ.config(block_name,loc)
        for port,label,kind in config.labels():
          score += compute_snr(nz_eval,circ,block_name,loc,port)

  return score

def execute(circ):
  print("<< compute noise >>")
  prop_noise.compute(circ)
  print("<< compute bias >>")
  prop_bias.compute(circ)
  print("<< compute delay >>")
  prop_delay.compute(circ)
