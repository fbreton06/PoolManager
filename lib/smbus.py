import host
import time

host.ImportModule("smbus")

class SMBus:
    def __init__(self, busType):
        self.__bus = host.Execute("smbus.SMBus(%d)" % busType)

    def __del__(self):
        if self.__bus != None:
            host.RemoveHandle(self.__bus)

    def read_byte(self, address):
        return host.Execute("read_byte(%d)" % address, self.__bus)

    def write_byte(self, address, value):
        host.Execute("write_byte(%d, %d)" % (address, value), self.__bus)

    def write_byte_data(self, address, value, data):
        host.Execute("write_byte_data(%d, %d, %d)" % (address, value, data), self.__bus)

    def close(self):
        host.Execute("close()", self.__bus)
        host.RemoveHandle(self.__bus)
        self.__bus = None

if __name__ == '__main__':
    bus = SMBus(1)
    print "LCD Light OFF for 2s"
    bus.write_byte(0x27, 0)
    time.sleep(2)
    print "LCD Light ON for 2s"
    bus.write_byte(0x27, 8)
    time.sleep(2)
    print "LCD Light OFF"
    bus.write_byte(0x27, 0)
    bus.close()
    print "Done"
    #raw_input("Appuyer sur entree pour continuer")
