#!/usr/bin/env python
import os, time
from helper import *
import host

class Temperature(Debug):
    def __init__(self, number=""):
        Debug.__init__(self)
        self.__remote = False
        if number:
            if os.path.isfile(number):
                self.__file = number
            elif os.path.isfile(os.path.join(os.getcwd(), number + ".txt")):
                # Test current folder to support simulation case
                self.__file = number
            else:
                self.__file = "/sys/bus/w1/devices/%s/w1_slave" % number
                if not os.path.isfile(self.__file):
                    try: # Remote filesystem
                        probe = host.Execute("open(\"%s\")" % self.__file)
                        host.Execute("close()", probe)
                        host.RemoveHandle(probe)
                        self.__remote = True
                    except:
                        raise ValueError, "1-Wire Probe %s not detected!" % number
        else:
            self.__file = ""
            for number in os.listdir('/sys/bus/w1/devices'):
                if number != 'w1_bus_master1':
                    self.__file = "/sys/bus/w1/devices/%s/w1_slave" % number
                    break
            if not os.path.isfile(self.__file):
                raise ValueError, "1-Wire Probe not detected!"

    def __del__(self):
        self.close()

    def read(self):
        if self.__remote:
            probe = host.Execute("open(\"%s\")" % self.__file)
            result = host.Execute("read()", probe)
            host.Execute("close()", probe)
            host.RemoveHandle(probe)
        else:
            probe = open(self.__file)
            result = probe.read()
            probe.close()
        return float(result.split("\n")[1].split("=")[-1]) / 1000

    def close(self):
        if self.__remoteHandle != None:
            host.Execute("close(%s)", self.__remoteHandle)
            host.RemoveHandle(self.__remoteHandle)

if __name__ == "__main__":
    try:
        temp = Temperature("28-0417716a37ff")
        while True:
            print "Temperature: %.2fC" % temp.read()
            time.sleep(1.0)
    except KeyboardInterrupt:
        pass

