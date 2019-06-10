import ops.op as ops
from enum import Enum
import util.util as util

class BlockType(Enum):
    ADC = "adc"
    DAC = "dac"
    GENERAL = "general"
    COPIER = "copier"
    BUS = "bus"

class Block:

    def __init__(self,name,type=None,subset=None):
        self._name = name
        self._type = type
        # port info
        self._outputs = []
        self._inputs = []

        # mode specific properties
        self._signals = {}
        self._ops = {}
        self._copies = {}

        self._coeffs = {}
        self._props = {} # operating ranges and values

        # scale factors
        self._scale_models = {}
        self._scale_modes = {}

        #self.set_comp_modes(['*'])
        #self.set_scale_modes("*",['*'])
        self._comp_mode_subsets = {}
        self._scale_mode_subsets = {}
        self._comp_modes = []
        self._scale_modes = {}
        self._subset = None

    def subset(self,subs):
        self._subset = subs
        return self

    def _make_comp_dict(self,comp_mode,d):
        comp_mode_key = util.normalize_mode(comp_mode)
        if not comp_mode_key in d:
            d[comp_mode_key] = {}

        return d[comp_mode_key]

    def _make_scale_dict(self,comp_mode,scale_mode,d):
        comp_mode_key = util.normalize_mode(comp_mode)
        if not (comp_mode_key in self._comp_modes):
            raise Exception("%s not in <%s>" % \
                            (comp_mode_key,self._comp_modes))
        data = self._make_comp_dict(comp_mode_key,d)

        scale_mode_key = util.normalize_mode(scale_mode)
        if not scale_mode_key in data:
            data[scale_mode_key] = {}

        return data[scale_mode_key]

    def _get_comp_dict(self,comp_mode,d):
        comp_mode_key = util.normalize_mode(comp_mode)
        if not comp_mode_key in d:
            return None

        return d[comp_mode_key]

    def _get_scale_dict(self,comp_mode,scale_mode,d):
        scale_mode_key = util.normalize_mode(scale_mode)
        data = self._get_comp_dict(comp_mode,d)
        if data is None:
            return None
        if not scale_mode_key in data:
            return None

        return data[scale_mode_key]

    def coeff(self,comp_mode,scale_mode,out,handle=None):
        data = self._get_scale_dict(comp_mode,scale_mode, \
                                    self._coeffs)
        if data is None or \
           not out in data or \
           not handle in data[out]:
            return 1.0

        return data[out][handle]

    def set_coeff(self,comp_mode,scale_mode,port,value,handle=None):
        data = self._make_scale_dict(comp_mode,scale_mode, \
                                     self._coeffs)
        if not port in data:
            data[port] = {}

        data[port][handle] = value
        return self

    @property
    def type(self):
        return self._type

    def _map_ports(self,prop,ports):
        for port in ports:
            assert(not port in self._signals)
            self._signals[port] = prop

    def _wrap_coeff(self,coeff,expr):
        if coeff == 1.0:
            return expr
        else:
            return ops.Mult(ops.Const(coeff,tag='scf'),expr)

    def get_dynamics(self,comp_mode,output):
        copy_data = self._get_comp_dict(comp_mode,self._copies)
        op_data = self._get_comp_dict(comp_mode,self._ops)
        if output in copy_data:
            output = copy_data[output]

        expr = op_data[output]
        return expr

    def dynamics(self,comp_mode):
        for output in self._outputs:
            expr = self.get_dynamics(comp_mode,output)
            yield output,expr

    def all_dynamics(self):
        for comp_mode in self._ops:
            for output,expr in self._ops[comp_mode].items():
                yield comp_mode,output,expr

    def signals(self,port):
        return self._signals[port]

    def props(self,comp_mode,scale_mode,port,handle=None):
        data = self._get_scale_dict(comp_mode,scale_mode, \
                                    self._props)
        if data is None:
            for k1,v1 in self._props.items():
                for k2,v2 in v1.items():
                    print(k1,k2)
            raise Exception("mode <%s,%s> not in prop-dict" % \
                            (comp_mode,scale_mode))
        if not port in data:
            raise Exception("port not in prop-dict <%s>" % port)

        if not handle in data[port]:
            raise Exception("handle not in prop-dict <%s>" % handle)

        return data[port][handle]

    def handles(self,comp_mode,port):
        if self.is_input(port):
            return []
        return self.get_dynamics(comp_mode,port).handles()

    @property
    def name(self):
        return self._name

    @property
    def inputs(self):
        return self._inputs

    def by_signal(self,sel_signal,ports):
        def _fn():
            for port in ports:
                signal = self._signals[port]
                if sel_signal == signal:
                    yield port

        return list(_fn())

    def copies(self,comp_mode,port):
        data = self._get_comp_dict(comp_mode,self._copies)
        for this_port, copy_port in data.items():
            if this_port == port:
                yield copy_port

    @property
    def outputs(self):
        return self._outputs

    def add_inputs(self,prop,inps):
        assert(len(inps) > 0)
        for inp in inps:
            self._inputs.append(inp)

        self._map_ports(prop,inps)
        return self

    def add_outputs(self,prop,outs):
        assert(len(outs) > 0)
        self._outputs = outs
        self._map_ports(prop,outs)
        return self


    @property
    def comp_modes(self):
        return self._comp_modes

    def scale_modes(self,comp_mode):
        return self._scale_modes[comp_mode]

    def set_comp_modes(self,modes,subsets):
        comp_modes = list(map(lambda m: \
                                    util.normalize_mode(m), \
                                    modes))

        for mode in comp_modes:
            self._ops[mode] = {}
            self._signals[mode] = {}
            self._copies[mode] = {}
            self._props[mode] = {}
            self._coeffs[mode] = {}

        for mode in comp_modes:
            self._comp_mode_subsets[mode] = []
            for subs in subsets:
                self._comp_mode_subsets[mode].append(subs)

        for mode in comp_modes:
            self._comp_modes.append(mode)

        return self

    def set_scale_modes(self,comp_mode,scale_modes,subsets):
        comp_mode_key = util.normalize_mode(comp_mode)
        if not comp_mode_key in self._props:
            raise Exception("not in comps <%s> : <%s>" % \
                            (comp_mode_key,self._scale_modes))

        scale_modes = list(map(lambda m: \
                               util.normalize_mode(m),
                               scale_modes))
        for mode in scale_modes:
            assert(not comp_mode_key in self._scale_modes or\
                   not mode in self._scale_modes[comp_mode_key])
            self._props[comp_mode_key][mode] = {}
            self._coeffs[comp_mode_key][mode] = {}

        for mode in scale_modes:
            self._scale_mode_subsets[(comp_mode_key,mode)]= []
            for subs in subsets:
                self._scale_mode_subsets[(comp_mode_key,mode)].append(subs)

        for mode in scale_modes:
            if not comp_mode_key in self._scale_modes:
                self._scale_modes[comp_mode_key] = []
            self._scale_modes[comp_mode_key].append(mode)

        return self

    def set_copy(self,comp_mode,copy,orig):
        data = self._get_comp_dict(comp_mode,self._copies)
        assert(not copy in data)
        data[copy] = orig
        return self

    def set_op(self,comp_mode,out,expr,integrate=False):
        data = self._make_comp_dict(comp_mode,self._ops)
        data[out] = expr
        return self

    def scale_model(self,comp_mode):
        if not comp_mode in self._scale_models:
            raise Exception("block <%s> does not contain scale model for <%s>" % \
                            (self.name,comp_mode))
        return self._scale_models[comp_mode]

    def set_scale_model(self,comp_mode,model):
        self._scale_models[comp_mode] = model

    def set_props(self,comp_mode,scale_mode,ports,properties,handle=None):
        data = self._make_scale_dict(comp_mode,scale_mode,self._props)

        for port in ports:
            assert(port in self._inputs or port in self._outputs)
            if not port in data:
                data[port] = {}

            assert(not handle in data[port])
            data[port][handle] = properties

        return self



    def is_input(self,port):
        assert(port in self._inputs or port in self._outputs)
        return port in self._inputs

    def is_output(self,port):
        assert(port in self._inputs or port in self._outputs)
        return port in self._outputs

    def _check_comp_dict(self,data):
        for comp_mode in self._comp_modes:
            assert(comp_mode in data)
            yield comp_mode,data[comp_mode]

    def _check_scale_dict(self,data):
        for comp_mode,datum in self._check_comp_dict(data):
            for scale_mode in self._scale_modes[comp_mode]:
                assert(scale_mode in datum)
                yield comp_mode,scale_mode,datum[scale_mode]

    def check(self):
        for comp_mode,data in self._check_comp_dict(self._copies):
            continue

        for comp_mode,_ in self._check_comp_dict(self._ops):
            continue

        for comp_mode in self._comp_modes:
            for out in self._outputs:
                if out in self._copies[comp_mode]:
                    assert(self._copies[comp_mode][out] in self._outputs)
                else:
                    assert(out in self._ops[comp_mode])
                    expr = self._ops[comp_mode][out]
                    for inp in expr.vars():
                        assert(inp in self._inputs)


        for comp_mode,data in self._check_comp_dict(self._signals):
            continue

        for comp_mode,scale_mode,data in self._check_scale_dict(self._props):
            continue

        return self
