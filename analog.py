#!/usr/bin/python
from Adafruit_ADS1x15 import ADS1115 # sudo pip install adafruit-ads1x15

class Analog:
    GAIN_BOUNDmV = {0: 6144, 1: 4096, 2: 2048, 4: 1024, 8: 512, 16: 256}
    def __init__(self, address=0x48, i2cLock=None):
        self.__can = ADS1115(address)
        self.__i2cLock = i2cLock

    def __readAnalog(self, pin, gain):
        value = None
        while value is None:
            try:
                value = self.__can.read_adc(pin, gain)
            except:
                pass
        return value

    def read(self, pin, gain=1):
        if not self.GAIN_BOUNDmV.has_key(gain):
            raise ValueError, "Unexpected gain value: %d" % gain
        value = None
        if self.__i2cLock is not None:
            with self.__i2cLock:
                value = self.__readAnalog(pin, gain)
        else:
            value = self.__readAnalog(pin, gain)
        return (self.GAIN_BOUNDmV[gain] * value) / 32767.0
