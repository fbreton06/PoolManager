#!/usr/bin/python
import smbus, threading

class I2C:
    def __init__(self, nbClient):
        self.__count = nbClient
        self.__smbus = smbus.SMBus(1)
        self.__lock = threading.RLock()

    def getLock(self):
        return self.__lock

    def read_byte(self, address):
        with self.__lock:
            value = self.__smbus.read_byte(address)
        return value

    def write_byte(self, address, value):
        with self.__lock:
            self.__smbus.write_byte(address, value)

    def write_byte_data(self, address, value, data):
        with self.__lock:
            self.__smbus.write_byte_data(address, value, data)

    def close(self):
        self.__count -= 1
        if self.__count == 0:
            self.__smbus.close()
