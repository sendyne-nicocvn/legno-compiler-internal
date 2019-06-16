import argparse
import sys
import os
import shutil
import util.config as CONFIG
import lab_bench.lib.chipcmd.data as chipcmd
import json
import itertools
import numpy as np
import scipy.optimize
import math
from chip.model import PortModel, ModelDB
from chip.hcdc.globals import HCDCSubset
import matplotlib.pyplot as plt

def to_sign(name):
  return chipcmd.SignType(name)

def sign_options():
  return list(chipcmd.SignType.options())

def to_range(name):
  return chipcmd.RangeType(name)

def group_dataset(data):
  meta = data['metadata']
  block = meta['block']
  chip,tile,slce,inst = meta['loc']['chip'],meta['loc']['tile'], \
                        meta['loc']['slice'],meta['loc']['index']

  grouped_dataset = {}
  for i,grpdata in enumerate(data['groups']['values']):
    grpfields = data['groups']['fields']
    group = dict(zip(grpfields,grpdata))
    key = str(grpdata)
    if not key in grouped_dataset:
      grouped_dataset[key] = {'group':group,
                              'target':[],
                              'in0':[],
                              'in1':[],
                              'bias':[],
                              'noise':[],
                              'params':{}}

    expected = dict(zip(data['expected']['fields'], \
                        data['expected']['values'][i]))
    observed = dict(zip(data['observed']['fields'], \
                        data['observed']['values'][i]))
    params = dict(zip(data['params']['fields'], \
                      data['params']['values'][i]))

    key0,key1 = None,None
    for it in filter(lambda k: 'in0' in k, expected.keys()):
      key0 = it
    for it in filter(lambda k: 'in1' in k, expected.keys()):
      key1 = it

    assert(len(grpdata) == len(grpfields))
    grouped_dataset[key]['target'].append(expected['output'])
    if not key0 is None:
      grouped_dataset[key]['in0'].append(expected[key0])
    if not key1 is None:
      grouped_dataset[key]['in1'].append(expected[key1])

    grouped_dataset[key]['bias'].append(observed['bias'])
    grouped_dataset[key]['noise'].append(observed['noise'])
    for k,v in params.items():
      if not k in grouped_dataset[key]['params']:
        grouped_dataset[key]['params'][k] = []
      grouped_dataset[key]['params'][k].append(v)

  loc = "(HDACv2,%d,%d,%d,%d)" % (chip,tile,slce,inst)
  return block,loc,grouped_dataset

def apply_model(xdata,a,b):
    x = xdata
    result = (a)*(x) + b
    return result

def infer_model(data,adc=False):
  n = len(data['bias'])
  bias = np.array(list(map(lambda i: data['bias'][i], range(n))))
  target= np.array(list(map(lambda i: data['target'][i], range(n))))
  noise = np.array(list(map(lambda i: data['noise'][i], range(n))))
  in0 = np.array(list(map(lambda i: data['in0'][i], range(n))))
  in1 = np.array(list(map(lambda i: data['in1'][i], range(n))))
  if adc:
    bias = np.array(list(map(lambda i: bias[i]/128.0, range(n))))
    target = np.array(list(map(lambda i: (target[i]-128.0)/128.0, range(n))))
    noise = np.array(list(map(lambda i: noise[i]/(128.0**2), range(n))))

  if n == 1:
    gain,bias,unc_std,nz_std = 1.0,bias[0],0.0,math.sqrt(noise[0])

  elif n > 1:
    meas = np.array(list(map(lambda i: bias[i]+target[i], range(n))))
    #plt.scatter(target,meas,s=1.0)
    if len(in0) + len(in1) > 0:
      error = meas-target
      assert(len(in0) == len(error))
      plt.scatter(in0,in1,s=6.0,c=error)
      plt.savefig("iorel.png")
      plt.clf()

    (gain,bias),corrs= scipy.optimize.curve_fit(apply_model, target, meas)
    pred = np.array(list(map(lambda i: apply_model(target[i],gain,bias), \
                             range(n))))
    errors = list(map(lambda i: (meas[i]-pred[i])**2.0, range(n)))
    plt.scatter(target,meas,label='data',c='black')
    plt.plot(target,pred,label='pred',c='red')
    plt.legend()
    plt.savefig("model.png")
    plt.clf()
    plt.scatter(target,errors)
    plt.savefig("errors.png")
    plt.clf()
    input("continue?")
    unc_var = sum(errors)/n
    unc_std = math.sqrt(unc_var)
    nz_var = sum(noise)/n
    nz_std = math.sqrt(nz_var)

  print("gain=%f bias=%f unc-std=%f noise-std=%f" % (gain,bias,unc_std,nz_std))
  return gain,bias,unc_std,nz_std

def build_adc_model(data):
  block,loc,grouped_dataset = group_dataset(data)

  for group_data in grouped_dataset.values():
    group = group_data['group']
    gain,bias,bias_unc,noise = infer_model(group_data,adc=True)
    comp_mode = "*"
    scale_mode = to_range(group['rng'])
    model = PortModel('tile_adc',loc,'out',
                        comp_mode=comp_mode,
                        scale_mode=scale_mode)

    model.bias = bias
    model.bias_uncertainty = bias_unc
    model.noise = noise
    model.gain = gain
    yield model

    model = PortModel('tile_adc',loc,'in',
                           comp_mode=comp_mode,
                           scale_mode=scale_mode)
    yield model

def build_fanout_model(data):
  comp_options = [sign_options(), \
                  sign_options(), \
                  sign_options()]

  block,loc,grouped_dataset = group_dataset(data)

  for group_data in grouped_dataset.values():
    group = group_data['group']
    gain,bias,bias_unc,noise = infer_model(group_data)

    scale_modes = [to_range(group["range-%s" % group['port']])]
    comp_modes = list(itertools.product(*comp_options))
    for comp_mode in comp_modes:
      for scale_mode in scale_modes:
        model = PortModel(block,loc,group['port'],
                            comp_mode=comp_mode,
                            scale_mode=scale_mode)
        model.bias = bias
        model.bias_uncertainty = bias_unc
        model.noise = noise
        model.gain = gain
        yield model

        model = PortModel(block,loc,"in",
                               comp_mode=comp_mode,
                               scale_mode=scale_mode)
        yield model


def build_integ_model(data):
  comp_options = list(chipcmd.SignType.options())

  block,loc,grouped_dataset = group_dataset(data)

  for group_data in grouped_dataset.values():
    group = group_data['group']
    scale_mode = (to_range(group["range-in0"]), \
                   to_range(group["range-out0"]))
    print("%s scale-mode=%s port=%s" % (loc, \
                                        str(scale_mode), \
                                        group['port']))
    gain,bias,bias_unc,noise = infer_model(group_data)
    for comp_mode in comp_options:
      # the initial condition
      if group["port"]== "in1":
        model = PortModel("integrator",loc,'out', \
                            handle=':z[0]', \
                            comp_mode=comp_mode,
                            scale_mode=scale_mode)
        model.bias = bias
        model.bias_uncertainty = bias_unc
        model.noise = noise
        model.gain = gain
        yield model

        model = PortModel('integrator',loc,'ic', \
                          comp_mode=comp_mode,
                          scale_mode=scale_mode)
        yield model

      if group["port"]== "out0":
        model = PortModel('integrator',loc,'out', \
                          comp_mode=comp_mode,
                          scale_mode=scale_mode)
        model.bias = bias
        model.bias_uncertainty = bias_unc
        model.noise = noise
        yield model

        model = PortModel('integrator',loc,'out', \
                          handle=":z",
                          comp_mode=comp_mode,
                          scale_mode=scale_mode)
        yield model

      # the input port
      elif group["port"] == "in0":
        model = PortModel('integrator',loc,'in', \
                          comp_mode=comp_mode,
                          scale_mode=scale_mode)
        model.bias = bias
        model.bias_uncertainty = bias_unc
        model.noise = noise
        yield model
        model = PortModel('integrator',loc,'out', \
                          handle=":z'",
                          comp_mode=comp_mode,
                          scale_mode=scale_mode)
        yield model

def build_dac_model(data):
  block,loc,grouped_dataset = group_dataset(data)

  for group_data in grouped_dataset.values():
    group = group_data['group']
    gain,bias,bias_unc,noise = infer_model(group_data)
    comp_mode = to_sign(group['inv'])
    scale_mode = to_range(group['rng'])
    # ignore source
    model = PortModel('tile_dac',loc,'out', \
                        comp_mode=comp_mode, \
                        scale_mode=scale_mode)
    model.bias = bias
    model.bias_uncertainty = bias_unc
    model.noise = noise
    model.gain = gain
    yield model

    model = PortModel('tile_dac',loc,'in', \
                      comp_mode=comp_mode,
                      scale_mode=scale_mode)
    yield model

def build_mult_model(data):
  block,loc,grouped_dataset = group_dataset(data)

  for group_data in grouped_dataset.values():
    group = group_data['group']
    if group['vga']:
      scale_mode = (to_range(group["range-in0"]), \
                    to_range(group["range-out0"]))
    else:
      scale_mode = (to_range(group["range-in0"]), \
                    to_range(group["range-in1"]), \
                    to_range(group["range-out0"]))

    print("scale-mode=%s" % str(scale_mode))
    gain,bias,bias_unc,noise = infer_model(group_data)
    comp_mode = "vga" if group['vga'] else "mul"
    model = PortModel("multiplier",loc,'out', \
                        comp_mode=comp_mode,
                        scale_mode=scale_mode)
    model.bias = bias
    model.bias_uncertainty = bias_unc
    model.noise = noise
    model.gain = gain
    yield model

    model = PortModel("multiplier",loc,'in0', \
                         comp_mode=comp_mode,
                         scale_mode=scale_mode)
    yield model
    model = PortModel("multiplier",loc,'in1', \
                         comp_mode=comp_mode,
                         scale_mode=scale_mode)
    yield model
    model = PortModel("multiplier",loc,'coeff', \
                         comp_mode=comp_mode,
                         scale_mode=scale_mode)
    yield model

def build_model(data):
  meta = data['metadata']
  print("=== BLOCK %s %s ===" % (meta['block'], \
                                 ".".join(
                                   map(lambda v: str(v), \
                                       meta['loc'].values()) \
                                 ))
  )
  if meta['block'] == 'adc':
    gen = build_adc_model(data)
  elif meta['block'] == 'fanout':
    gen = build_fanout_model(data)
  elif meta['block'] == 'integ':
    gen = build_integ_model(data)
  elif meta['block'] == 'dac':
    gen = build_dac_model(data)
  elif meta['block'] == 'mult':
    gen = build_mult_model(data)
  elif meta['block'] == 'lut':
    gen = map(lambda i : i, [])
  else:
    raise Exception("unhandled: %s" % meta["block"])


  db = ModelDB()
  for model in gen:
    db.put(model)

def populate_default_models(board):
  print("==== Populate Default Models ===")
  db = ModelDB()
  for blkname in ['tile_in','tile_out', \
                  'chip_in','chip_out', \
                  'ext_chip_in','ext_chip_out']:
    block = board.block(blkname)
    for inst in board.instances_of_block(blkname):
      for port in block.inputs + block.outputs:
        model = PortModel(blkname,inst,port, \
                          comp_mode='*', \
                          scale_mode='*')
        db.put(model)

parser = argparse.ArgumentParser(description="Model inference engine")
parser.add_argument('--subset',default='standard',
                    help='component subset to use for compilation')
parser.add_argument('--populate-defaults',action='store_true',
                    help='insert default models for connection blocks')

args = parser.parse_args()

shutil.rmtree(CONFIG.DATASET_DIR)

print("python3 grendel.py --dump-db")
retcode = os.system("python3 grendel.py --dump-db")
if retcode != 0:
  raise Exception("could not dump database: retcode=%d" % retcode)

for dirname, subdirlist, filelist in os.walk(CONFIG.DATASET_DIR):
  for fname in filelist:
    if fname.endswith('.json'):
      fpath = "%s/%s" % (dirname,fname)
      with open(fpath,'r') as fh:
        obj = json.loads(fh.read())
        build_model(obj)

if args.populate_defaults:
  from chip.hcdc.hcdcv2_4 import make_board
  subset = HCDCSubset(args.subset)
  hdacv2_board = make_board(subset)
  populate_default_models(hdacv2_board)
