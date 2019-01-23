import serial
import time
import re
import tqdm
import np

class ArduinoDue:

    def __init__(self,native=True):
        self._baud_rate = 115200
        if not native:
            self._serial_port = '/dev/tty.usbmodem1411';
        else:
            self._serial_port = 'dev/ttyACM0'

        self._comm = None

    def close(self):
        if not self._comm is None:
            self._comm.close()

    def open(self):
        print("%s:%s" % (self._serial_port,self._baud_rate))
        self._comm= serial.Serial(self._serial_port, self._baud_rate)

        delta = 0.02
        for _ in tqdm(np.linspace(0,2.0,delta)):
            time.sleep(delta)

        self.flush()
        return True

    def readline(self):
        line_bytes = self._comm.readline()
        line_valid_bytes = bytearray(filter(lambda b: b<128, line_bytes))
        return line_valid_bytes.decode('utf-8')

    def reads_available(self):
        return self._comm.in_waiting > 0

    def try_readline(self):
        if self._comm.in_waiting > 0:
            line = self.readline()
        else:
            line = None

        return line

    def writeline(self,string):
        msg = "%s\r\n" % string
        self.write(msg)

    def write_newline(self):
        self.write("\r\n")

    def flush(self):
        self._comm.flushInput()
        self._comm.flushOutput()

    def write_bytes(self,byts):
        isinstance(byts,bytearray)
        nbytes = 0;
        for i in range(0,len(byts), 32):
            nbytes += self._comm.write(byts[i:i+32])
            time.sleep(0.01)
        print("wrote %d bytes" % nbytes)
        self._comm.flush()

    def write(self,msg):
        self.write_bytes(msg.encode())
