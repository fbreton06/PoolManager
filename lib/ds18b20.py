#!/usr/bin/env python
import os, time, sys
from subprocess import Popen, PIPE, STDOUT

try:
    process = Popen("cat /etc/issue", stdout=PIPE, shell=True, stderr=STDOUT)
    result = process.communicate()
    isRaspberry = result[0].startswith("Rasp")
except:
    isRaspberry = False

if not isRaspberry:
    sys.path.append(os.path.join(os.path.pardir, os.path.pardir, "RRaspPY"))
    import host

class Temperature:
    def __init__(self, number=""):
        self.__remote = False
        if number:
            if os.path.isfile(number):
                self.__file = number # Simulation where number is the file used dor onewire stream emulation
            elif os.path.isfile(os.path.join(os.getcwd(), number)):
                self.__file = number # Same but in the current folder
            elif not isRaspberry:
                try: # Remote filesystem
                    self.__file = "/sys/bus/w1/devices/%s/w1_slave" % number
                    probe = host.Execute("open(\"%s\")" % self.__file)
                    host.Execute("close()", probe)
                    host.RemoveHandle(probe)
                    self.__remote = True
                except:
                    raise ValueError, "1-Wire Probe %s not detected in remote!" % number
            else:
                self.__file = "/sys/bus/w1/devices/%s/w1_slave" % number
                if not os.path.isfile(self.__file):
                    raise ValueError, "1-Wire Probe %s not detected!" % number
        else:
            # Try autodetection
            self.__file = ""
            for number in os.listdir('/sys/bus/w1/devices'):
                if number != 'w1_bus_master1':
                    self.__file = "/sys/bus/w1/devices/%s/w1_slave" % number
                    break
            if not os.path.isfile(self.__file):
                raise ValueError, "1-Wire Probe not auto-detected!"

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

if __name__ == "__main__":
    try:
        temp = Temperature("28-0417716a37ff")
        while True:
            print "Temperature: %.2fC" % temp.read()
            time.sleep(1.0)
    except KeyboardInterrupt:
        pass

