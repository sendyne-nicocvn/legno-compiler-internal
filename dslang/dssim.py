
class DSSim:

    def __init__(self,name):
        self._name = name
        self._sim_time = 1.0
        self._input_time = 1.0
        self._hwenv = "osc"
        self._inputs = {}

    def input(self,name):
        if not name in self._inputs:
            raise Exception("input not recognized: %s" % name)
        return self._inputs[name][0]

    def is_periodic(self,name):
        return self._inputs[name][1]

    def set_input(self,name,func,periodic=False):
        assert(isinstance(func,op.Op))
        self._inputs[name] = (func,periodic)

    @property
    def name(self):
        return self._name

    @property
    def input_time(self):
        return self._input_time

    @property
    def hardware_env(self):
        return self._hwenv


    @property
    def sim_time(self):
        return self._sim_time

    def set_input_time(self,t):
        assert(t > 0)
        self._input_time = t


    def set_hardware_env(self,hwenv):
        self._hwenv = hwenv


    def set_sim_time(self,t):
        assert(t > 0)
        self._sim_time = t


class DSInfo:

    def __init__(self,name,desc,meas,units):
        self.name = name
        self.description = desc
        self.observation = meas
        self.units = units
        self.nonlinear = False
