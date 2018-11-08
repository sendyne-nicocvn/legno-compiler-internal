from devices.arduino_due import ArduinoDue
from devices.sigilent_osc import Sigilent1020XEOscilloscope 
import devices.sigilent_osc as osclib

from lib.base_command import FlushCommand, ArduinoCommand
import time

class State:

    def __init__(self,osc_ip,osc_port,ard_native,validate=False):
        if not validate:
            self.arduino = ArduinoDue(native=ard_native)
            self.oscilloscope = Sigilent1020XEOscilloscope(
                osc_ip, osc_port)
        self.prog = [];

        ## State committed to chip
        self.use_osc = False;

        self._use_adc = {};
        self._use_dac = {}
        self.use_analog_chip = None;
        self.n_samples = None;
        self.reset();

        self.TIME_BETWEEN_SAMPLES = 3.0*1e-6
        self.dummy = validate

    def reset(self):
        self.use_analog_chip = False;
        self.n_samples = 0

        for adc_id in range(0,4):
            self._use_adc[adc_id] = False

        self._use_dac = {}
        for dac_id in range(0,2):
            self._use_dac[dac_id] = False

    def use_dac(self,dac_id):
        self._use_dac[dac_id] = True

    def use_adc(self,adc_id):
        self._use_adc[adc_id] = True

    def adcs_in_use(self):
        for adc_id,in_use in self._use_adc.items():
            if in_use:
                yield adc_id

    def dacs_in_use(self):
        for dac_id,in_use in self._use_dac.items():
            if in_use:
                yield dac_id



    def close(self):
        if not self.dummy:
            self.arduino.close()
            self.oscilloscope.close()

    def initialize(self):
        if self.dummy:
            return

        print("[[ setup oscilloscope ]]")
        self.oscilloscope.setup()
        print("[[ setup arduino ]]")
        self.arduino.open()
        flush_cmd = FlushCommand()
        while not flush_cmd.execute(self):
            continue

    def enqueue(self,stmt):
        if stmt.test():
            print("[enq] %s" % stmt)
            self.prog.append(stmt)
        else:
            print("[error] " + stmt.error_msg())

    def calibrate_chip(self):
        if not self.use_analog_chip:
            return

        for stmt in self.prog:
            if isinstance(stmt, cmd.AnalogChipCommand):
                calib_stmt = stmt.calibrate()
                if not calib_stmt is None:
                    yield calib_stmt

    def teardown_chip(self):
        if not self.use_analog_chip:
            return

        for stmt in self.prog:
            if isinstance(stmt, cmd.AnalogChipCommand):
                dis_stmt = stmt.disable()
                if not dis_stmt is None:
                    yield dis_stmt

    def configure_chip(self):
        if not self.use_analog_chip:
            return

        for stmt in self.prog:
            if isinstance(stmt, cmd.AnalogChipCommand):
                print("[config] %s" % stmt)
                config_stmt = stmt.configure()
                if not config_stmt is None:
                    yield config_stmt



