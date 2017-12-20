#!/usr/bin/env python
import types, time, datetime
import RPi.GPIO as GPIO
from helper import *

class Date(Debug):
    MONTH = ("january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december")
    DAY = ("sunday", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday")
    def __init__(self, year=1999, month=1, day=1, weekday=1):
        Debug.__init__(self)
        if year < 2000:
            today = datetime.datetime.today()
            year = today.year
            month = today.month
            day = today.day
            weekday = ((today.weekday() + 1) % 7) + 1
        self.year = self.__check(year, 2000, 2099, "Year")
        if type(month) in types.StringTypes and month.lower() in self.MONTH:
            self.month = self.MONTH.index(month.lower()) + 1
        else:
            self.month = self.__check(month, 1, 12, "Month")
        self.day = self.__check(day, 1, [30, 31][[day % 2, (day + 1) % 2][day > 7]], "Day")
        if type(weekday) in types.StringTypes and weekday.lower() in self.DAY:
            self.weekday = self.DAY.index(weekday.lower()) + 1
        else:
            self.weekday = self.__check(weekday, 1, 7, "Weekday")

    def __str__(self):
        return "%d %s %2d %s" % (self.year, self.MONTH[self.month - 1], self.day, self.DAY[self.weekday - 1])

    def __eq__(self, date):
        if self.weekday != date.weekday or self.day != date.day or self.month != date.month or self.year != date.year:
            return False
        return True

    def __check(self, value, min, max, kind):
        if value < min or value > max:
            raise ValueError, "%s value %d is out of bound [%d,%d]" % (kind, value, min, max)
        return value

class Time(Debug):
    def __init__(self, hour=-1, minute=0, seconde=0):
        Debug.__init__(self)
        if hour < 0:
            today = datetime.datetime.today()
            hour = today.hour
            minute = today.minute
            seconde = today.second
        self.hour = self.__check(hour, 0, 23, "Hour")
        self.minute = self.__check(minute, 0, 59, "Min")
        self.seconde = self.__check(seconde, 0, 59, "Sec")

    def __str__(self):
        return "%02d:%02d:%02d" % (self.hour, self.minute, self.seconde)

    def __eq__(self, time):
        if self.seconde != time.seconde or self.minute != time.minute or self.hour != time.hour:
            return False
        return True

    def __check(self, value, min, max, kind):
        if value < min or value > max:
            raise ValueError, "%s value %d is out of bound [%d,%d]" % (kind, value, min, max)
        return value

class DateTime(Debug):
    def __init__(self, year=1999, month=1, day=1, weekday=1, hour=0, minute=0, seconde=0):
        Debug.__init__(self)
        self.date = Date(year, month, day, weekday)
        self.time = Time([hour, -1][year < 2000], minute, seconde)

    def __str__(self):
        return str(self.date) + ' ' + str(self.time)

    def __eq__(self, datetime):
        if self.time.minute != datetime.time.minute or self.time.hour != datetime.time.hour or self.date != datetime.date:
            return False
        return True

class RTC(Debug):
    SEC_REG = 0x00
    MIN_REG = 0x02
    HOUR_REG = 0x04
    NUM_REG = 0x06
    MONTH_REG = 0x08
    DAY_REG = 0x0A
    YEAR_REG = 0x0C
    CTRL_REG = 0x0E
    TRICKLE = 0x10
    CLOCK_BURST_REG = 0x3E
    RAM_BURST_REG = 0x7E
    WR_REG = 0x80
    RD_REG = 0x81
    RAM_ADDR_BASE = 0x40
    def __init__(self, scl_pin, io_pin, rst_pin, mode=GPIO.BCM):
        Debug.__init__(self)
        self.__scl = scl_pin
        self.__io = io_pin
        self.__rst = rst_pin
        self.__ramSize = 31
        GPIO.setmode(mode)
        GPIO.setup(self.__scl, GPIO.OUT)
        GPIO.setup(self.__io, GPIO.IN)
        GPIO.setup(self.__rst, GPIO.OUT)
        GPIO.output(self.__scl, GPIO.LOW)
        GPIO.output(self.__rst, GPIO.LOW)

    def __enable(self):
        GPIO.output(self.__scl, GPIO.LOW)
        GPIO.output(self.__rst, GPIO.HIGH)
        time.sleep(0.000004)

    def __disable(self):
        GPIO.output(self.__rst, GPIO.LOW)
        time.sleep(0.000004)

    def __pulse(self):
        GPIO.output(self.__scl, GPIO.HIGH)
        time.sleep(0.000001)
        GPIO.output(self.__scl, GPIO.LOW)
        time.sleep(0.000001)

    def __write(self, value, option=0):
        GPIO.setup(self.__io, GPIO.OUT)
        value &= 0xFF
        if option == 1:
            value = ((value / 10) << 4) | (value % 10)
        elif option == 2:
            value = ((value / 10) << 4) | (value % 10) | 0x80
        self.TRACE(self.DEBUG, "WRITE(%d): 0x%02X\n", option, value)
        for bit in range(8):
            GPIO.output(self.__io, (value >> bit) & 1)
            time.sleep(0.0000002)
            self.TRACE(self.DEBUG, (value >> bit) & 1)
            self.__pulse()
        self.TRACE(self.DEBUG, "\n")

    def __read(self, option=0):
        GPIO.setup(self.__io, GPIO.IN)
        value = 0
        for bit in range(8):
            value |= (GPIO.input(self.__io) << bit)
            self.TRACE(self.DEBUG, GPIO.input(self.__io))
            self.__pulse()
        self.TRACE(self.DEBUG, "\n")
        if option == 1:
            value = 10 * ((value & 0x70) >> 4) + (value & 0x0F)
        elif option == 2:
            if value & 0x80:
                value = (value & 0x0F) + (12 * ((value & 0x20) >> 5))
            else:
                value = (value & 0x0F) + (10 * ((value & 0x30) >> 4))
        self.TRACE(self.DEBUG, "READ(%d): 0x%02X\n", option, value)
        return value

    def __writeRam(self, address, value):
        if address >= self.__ramSize or address < 0:
            raise ValueError, "RAM address value %X out of bound [0-%X]" % (address, self.__ramSize)
        self.__writeRegister(self.RAM_ADDR_BASE | (address << 1), value)

    def __readRam(self, address):
        if address >= self.__ramSize or address < 0:
            raise ValueError, "RAM address value %X out of bound [0-%X]" % (address, self.__ramSize)
        return self.__readRegister(self.RAM_ADDR_BASE | (address << 1))

    def __writeRamBulk(self, data):
        if len(data) < 1 or len(data) > self.__ramSize:
            raise ErrorValue,  "Length parameter %d out of bound [1,%d]" % (length, self.__ramSize)
        self.__enable()
        self.__write(self.RAM_BURST_REG | self.WR_REG)
        for value in data:
            self.__write(value)
        self.__disable()

    def __readRamBulk(self, length):
        if length < 1 or length > self.__ramSize:
            raise ErrorValue,  "Length parameter %d out of bound [1,%d]" % (length, self.__ramSize)
        self.__enable()
        self.__write(self.RAM_BURST_REG | self.RD_REG)
        data = list()
        for i in range(length):
            data.append(self.__read())
        self.__disable()
        return data

    def __writeRegister(self, reg,  value):
        self.__enable()
        self.__write(self.WR_REG | reg)
        self.__write(value)
        self.__disable()

    def __readRegister(self, reg):
        self.__enable()
        self.__write(self.RD_REG | reg)
        value = self.__read()
        self.__disable()
        return value

    def halt(self, enable=None):
        value = self.__readRegister(self.SEC_REG)
        self.TRACE(self.DEBUG, "Halt %s\n", ["OFF", "ON"][(value & 0x80) == 0x80])
        if not enable is None:
            self.__writeRegister(self.SEC_REG, (value & 0x7F) | [0x00, 0x80][enable])
        return (value & 0x80) == 0x80

    def writeProtect(self, enable=None):
        value = self.__readRegister(self.CTRL_REG)
        self.TRACE(self.DEBUG, "WrProtect %s\n", ["OFF", "ON"][(value & 0x80) == 0x80])
        if not enable is None:
            self.__writeRegister(self.CTRL_REG, [0x00, 0x80][enable])
        return (value & 0x80) == 0x80

    def setDateTime(self, dt, protect=False):
        self.TRACE(self.DEBUG, "Set %s\n", dt)
        msb = self.__readRegister(self.SEC_REG) & 0x80
        self.__enable()
        self.__write(self.WR_REG | self.CLOCK_BURST_REG)
        self.__write(dt.seconde, [1, 2][msb])
        self.__write(dt.minute, 1)
        self.__write(dt.hour, 1)
        self.__write(dt.date, 1)
        self.__write(dt.month, 1)
        self.__write(dt.day, 1)
        self.__write(dt.year - 2000, 1)
        self.__write([0x00, 0x80][protect])
        self.__disable()

    def getDateTime(self):
        self.__enable()
        self.__write(self.RD_REG | self.CLOCK_BURST_REG)
        second = self.__read(1)
        minute = self.__read(1)
        hour = self.__read(2)
        date = self.__read(1)
        self.debug_level = self.DEBUG
        month = self.__read(1)
        self.debug_level = self.NONE
        day = self.__read(1)
        year = 2000 + self.__read(1)
        control = self.__read(0)
        self.__disable()
        dt = DateTime(year, month, date, hour, minute, second, day)
        self.TRACE(self.DEBUG, "Get %s\n", dt)
        return dt

if __name__ == "__main__":
    rtc = RTC(23, 24, 25)
    rtc.debug_level = rtc.DEBUG
    if rtc.writeProtect(False):
        assert not rtc.writeProtect(), "Error: RTC still protected!"
    now = DateTime()
    if rtc.halt(False):
        assert not rtc.halt(), "Error: RTC still halted!"
        rtc.TAG(rtc.INFO, "SET1")
        rtc.setDateTime(now, True)
    rtc.debug_level = rtc.NONE
    rtc.TAG(rtc.INFO, "GET1")
    dt = rtc.getDateTime()
    print "\n%s\n" % dt
    if dt != now:
        rtc.writeProtect(False)
        rtc.TAG(rtc.INFO, "SET2")
        rtc.setDateTime(now, True)
        print "You set the date and time to:", now
    try:
        while True:
            rtc.TAG(rtc.INFO, "GET")
            print rtc.getDateTime()
            time.sleep(0.5)
    except KeyboardInterrupt:
        GPIO.cleanup()
