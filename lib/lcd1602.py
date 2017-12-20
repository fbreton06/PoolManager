#!/usr/bin/python
import time, sys, smbus
from helper import *

class LCD(Debug):
    def __init__(self, address, backlight=False):
        Debug.__init__(self)
        self.__address = address
        self.__smbus = smbus.SMBus(1)
        self.__backlight = backlight
        self.__send_command(0x33) # Must initialize to 8-line mode at first
        time.sleep(0.005)
        self.__send_command(0x32) # Then initialize to 4-line mode
        time.sleep(0.005)
        self.__send_command(0x28) # 2 Lines & 5*7 dots
        time.sleep(0.005)
        self.__send_command(0x0C) # Enable display without cursor
        time.sleep(0.005)
        self.__send_command(0x01) # Clear Screen
        self.__smbus.write_byte(self.__address, 0x08)

    def __del__(self):
        self.__smbus.close()

    def __write_word(self, address, data):
        if self.__backlight:
            self.__smbus.write_byte(address, data | 0x08)
        else:
            self.__smbus.write_byte(address, data & 0xF7)

    def __send_command(self, command):
        # Send bit7-4 firstly
        buf = command & 0xF0
        buf |= 0x04               # RS = 0, RW = 0, EN = 1
        self.__write_word(self.__address ,buf)
        time.sleep(0.002)
        buf &= 0xFB               # Make EN = 0
        self.__write_word(self.__address ,buf)
        # Send bit3-0 secondly
        buf = (command & 0x0F) << 4
        buf |= 0x04               # RS = 0, RW = 0, EN = 1
        self.__write_word(self.__address ,buf)
        time.sleep(0.002)
        buf &= 0xFB               # Make EN = 0
        self.__write_word(self.__address ,buf)

    def __send_data(self, data):
        # Send bit7-4 firstly
        buf = data & 0xF0
        buf |= 0x05               # RS = 1, RW = 0, EN = 1
        self.__write_word(self.__address ,buf)
        time.sleep(0.002)
        buf &= 0xFB               # Make EN = 0
        self.__write_word(self.__address ,buf)
        # Send bit3-0 secondly
        buf = (data & 0x0F) << 4
        buf |= 0x05               # RS = 1, RW = 0, EN = 1
        self.__write_word(self.__address ,buf)
        time.sleep(0.002)
        buf &= 0xFB               # Make EN = 0
        self.__write_word(self.__address ,buf)

    def clear(self):
        # Clear Screen
        self.__send_command(0x01)

    def light(self, backlight=None):
        if backlight != None:
            self.__backlight = bool(backlight)
            if self.__backlight:
                self.__smbus.write_byte(self.__address, 0x08)
            else:
                self.__smbus.write_byte(self.__address, 0x00)
        return self.__backlight

    def write(self, row, column, message):
        if column < 0: column = 0
        if column > 15: column = 15
        if row < 0: row = 0
        if row > 1: row = 1
        # Move cursor
        self.__send_command(0x80 + 0x40 * row + column)
        for ch in message:
            self.__send_data(ord(ch))

if __name__ == '__main__':
    lcd = LCD(0x27, True)
    for i in range(3):
        lcd.write(0, 4, 'Hello')
        lcd.write(1, 7, 'world!')
        time.sleep(1.0)
        lcd.clear()
        time.sleep(1.0)
    lcd.light(False)
    print 'done'

