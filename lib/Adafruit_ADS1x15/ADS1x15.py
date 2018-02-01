import sys, os
sys.path.append(os.path.join(os.path.dirname(__file__), os.path.pardir))
import host

host.ImportModule(".ADS1x15", "ADS1x15", "Adafruit_ADS1x15")

class ADS1115:
    def __init__(self, address):
        self.__can = host.Execute("ADS1x15.ADS1115(%d)" % address)

    def __del__(self):
        if self.__can != None:
            host.RemoveHandle(self.__can)

    def read_adc(self, inputPin):
        return host.Execute("read_adc(%d)" % inputPin, self.__can)

if __name__ == '__main__':
    can = ADS1115(0x49)
    for i in range(4):
        print "ADC value (pin %d) = %d" % (i, can.read_adc(i))
    del can
    #raw_input("Appuyer sur entree pour continuer")
