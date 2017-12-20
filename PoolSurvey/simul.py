#!/usr/bin/python
class ADS1115:
    def read_adc(self, pin):
        return 0x3FFF

class GPIOClass(dict):
    IN = 0
    OUT = 1
    PUD_UP = 1
    BOTH = 2
    BOARD = 0
    BCM = 1
    LOW = False
    HIGH = True
    def setmode(self, mode):
        pass
    def cleanup(self):
        pass
    def setup(self, pin, direction, pull_up_down=None, initial=LOW):
        if not self.has_key(pin):
            self[pin] = [initial, direction]
    def add_event_detect(self, pin, edge, callback=None, bouncetime=None):
        if not self.has_key(pin):
            raise ValueError, "No setup call: \"add_event_detect\" pin %d" % pin
        ##self[pin].append(callback)
    def input(self, pin):
        if not self.has_key(pin):
            raise ValueError, "No setup call: \"input\" pin %d" % pin
        return self[pin][0]
    def output(self, pin, value):
        if not self.has_key(pin):
            raise ValueError, "No setup call: \"output\" pin %d" % pin
        if self[pin][1] != self.OUT:
            print pin, self.IN, self.OUT
            print self
            raise ValueError, "\"output\" used on input pin %d" % pin
        self[pin][0] = [self.LOW, self.HIGH][bool(value)]
GPIO=GPIOClass()

class TemperatureClass:
    def read(self):
        return 24.5
class ds18b20Class:
    def Temperature(self, sn):
        return TemperatureClass()
ds18b20=ds18b20Class()