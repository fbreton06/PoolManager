#!/usr/bin/python
import sys, smbus

import RPi.GPIO as GPIO

class Encoder:
    REG_VERSION = 0
    REG_FORMAT  = 1
    REG_POS_CUR = 5
    REG_POS_MIN = 6
    REG_POS_INI = 7
    REG_POS_MAX = 8
    REG_BOUNDED = 9
    REG_MSB_BMP = 0x80
    REG_REQUEST = 0x40
    def __init__(self, bounded, eventPin, callback, position=0, max=32767, min=-32768, bus=None):
        GPIO.setup(eventPin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        if bus == None:
            self.__bus = smbus.SMBus(1)
        else:
            self.__bus = bus
        self.__address = 0x33
        nbBytes = self.__readRegister(self.REG_FORMAT)
        assert nbBytes == 2, "Unaligned version: %d instead of 2" % nbBytes
        self.__writeRegister(self.REG_BOUNDED, bounded != 0)
        if bounded:
            assert min >= -32768, "Unbound value min"
            assert max <= 32767, "Unbound value max"
            assert min < max, "Incoherency values min >= max"
            assert min <= position <= max, "Unbound value position"
            # Set upper bound at -32768 (minimum supported by the actual ATMEGA328p chip)
            self.__writeRegister(self.REG_POS_MIN, min)
            # Set lower bound at 32767 (maximum supported by the actual ATMEGA328p chip)
            self.__writeRegister(self.REG_POS_MAX, max)
        # Set lower bound at 32767 (maximum supported by the actual ATMEGA328p chip)
        self.__writeRegister(self.REG_POS_INI, position)
        self.__previous = position
        self.__callback = callback
        GPIO.add_event_detect(eventPin, GPIO.FALLING, callback=self.__event)

    def __del__(self):
        self.__bus.close()

    def __readRegister(self, regNum):
        self.__bus.write_byte(self.__address, regNum | self.REG_REQUEST)
        lsb = self.__bus.read_byte(self.__address)
        self.__bus.write_byte(self.__address, regNum | self.REG_REQUEST | self.REG_MSB_BMP)
        msb = self.__bus.read_byte(self.__address)
        return 256 * msb + lsb

    def __writeRegister(self, regNum, value):
        self.__bus.write_byte_data(self.__address, regNum, value & 0xFF)
        self.__bus.write_byte_data(self.__address, regNum | self.REG_MSB_BMP, (value / 256) & 0xFF)

    def __event(self, pin):
        try:
            position = self.__readRegister(self.REG_POS_CUR)
            if position > 0x7FFF: # Treat negative case
                position -= 0x10000
            delta = position - self.__previous
            if delta != 0:
                self.__previous = position
                self.__callback(position, delta)
        except:
            pass

def RotaryEncoderCb(pos, delta):
    print delta

if __name__ == '__main__':
    try:
        GPIO.cleanup()
        GPIO.setmode(GPIO.BCM)
        while True:
            encoder = Encoder(False, 22, RotaryEncoderCb)
            #encoder = Encoder(True, 22, RotaryEncoderCb, 0, 1000,-1000) # Bounded case
    except KeyboardInterrupt:
        pass
    GPIO.cleanup()
