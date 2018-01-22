#!/usr/bin/env python
import os, time
from helper import *

class Temperature(Debug):
    def __init__(self, number=""):
        Debug.__init__(self)
        self.__number = number
        if not self.__number:
            for number in os.listdir('/sys/bus/w1/devices'):
                if number != 'w1_bus_master1':
                    self.__number = number
        if not os.path.isfile("/sys/bus/w1/devices/%s/w1_slave" % self.__number):
            raise ValueError, "1-Wire Probe not detected!"

    def read(self):
        probe = open("/sys/bus/w1/devices/%s/w1_slave" % self.__number)
        result = probe.read()
        probe.close()
        return float(result.split("\n")[1].split("=")[-1]) / 1000

if __name__ == "__main__":
    try:
        temp = Temperature("28-0417716a37ff")
        while True:
            print "Temperature: %.2fC" % temp.read()
            time.sleep(1.0)
    except KeyboardInterrupt:
        pass

