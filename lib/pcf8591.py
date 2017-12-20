#!/usr/bin/env python
import smbus
from helper import *

class CAN(Debug):
    def __init__(self,  address,  busType=1):
        Debug.__init__(self)
        self.__bus = smbus.SMBus(busType)
        self.__address = address

    def read(self, entry):
        if entry < 0 or entry > 3:
            raise ErrorValue, "Bad entry value: %d" % entry
        try:
            self.__bus.write_byte(self.__address, 0x40 + entry)
            # Dummy read to start conversion
            self.__bus.read_byte(self.__address)
        except Exception, error:
            print "Device address: 0x%2X" % self.__address
            raise error
        return self.__bus.read_byte(self.__address)

    def write(self, value):
        if value < 0 or value > 255:
            raise ErrorValue, "Bad byte value: %d" % value
        try:
            self.__bus.write_byte_data(self.__address, 0x40, value)
        except Exception, error:
            print "Device address: 0x%2X" % self.__address
            raise error

if __name__ == "__main__":
    try:
        value = 0
        can = CAN(0x48)
        while True:
            for i in range(4):
                print 'AIN%d = %d' % (i, can.read(i))
            can.write(value % 256)
            value += 1
    except KeyboardInterrupt:
        pass

