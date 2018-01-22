#!/usr/bin/python
import os, time, sys, types
sys.path.append(os.path.join(os.path.dirname(__file__), "lib"))
from helper import Debug

import ds18b20
from Adafruit_ADS1x15 import ADS1115 # sudo pip install adafruit-ads1x15
import RPi.GPIO as GPIO

# Raspberry 3 I/O Mapping

# BCM   Utilisation

# Information
#   2   SDA: ADS1115 (maybe needed + R10K to +5V) + LCD
#   3   SCL: ADS1115 (maybe needed + R10K to +5V) + LCD
#   4   1-Wire Temp (Jaune + R4.7K to +5V) (Noir=GND, rouge=5v)
#  --   Rotary CLK (Jaune)
#  --   Rotary DT (Marron)
#  22   Rotary SW (Blanc)
#  24   Rotary Event (Position has changed)
#  26   Water level (Jaune + R2.2K to GND) (Bleu=GND, noir+marron=5v)
#  12   Water move

# Commands
#   5   Relay IN? (Closing Curtain)
#   6   Relay IN? (Opening Curtain)
#  --   Relay IN? (Water Filling)
#  13   Relay IN? (Lights)
#  19   Relay IN? (Robot)
#  26   Relay IN? (Pump)
#  27   PWM GEN0  (Chlorine Injection)
#  17   PWM GEN2  (PH Injection)

# Add 47u on +5v

# all VDD are +5v

class Rotary:
    REG_VERSION = 0
    REG_FORMAT  = 1
    REG_POS_CUR = 5
    REG_POS_MIN = 6
    REG_POS_INI = 7
    REG_POS_MAX = 8
    REG_BOUNDED = 9
    REG_MSB_BMP = 0x80
    REG_REQUEST = 0x40
    def __init__(self, bounded, eventPin, rotaryCb, position=0, max=32767, min=-32768, bus=None):
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
        self.__callback = rotaryCb
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

class Information(Debug):
    ORP_CAN_PIN = 1
    PH_CAN_PIN = 2
    PSI_CAN_PIN = 3
    LIQUID_LEVEL_GPIO_PIN = 25
    LIQUID_MOVE_GPIO_PIN = 12
    def __init__(self, moveDetectCb, debounce_ms=200):
        Debug.__init__(self)
        self.__can = ADS1115(0x49)
        GPIO.setup(self.LIQUID_LEVEL_GPIO_PIN, GPIO.IN)
        GPIO.setup(self.LIQUID_MOVE_GPIO_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        self.__temp = ds18b20.Temperature("28-0417716a37ff")
        self.__moveDetectCb = moveDetectCb
        GPIO.add_event_detect(self.LIQUID_MOVE_GPIO_PIN, GPIO.BOTH, callback=self.__moveDetect, bouncetime=debounce_ms)

    def __moveDetect(self, pin):
        self.__moveDetectCb(pin, GPIO.input(pin))

    def __readAnalog(self, pin):
        value = None
        while value == None:
            try:
                value = self.__can.read_adc(pin)
            except:
                pass
        return (4096 * value) / 0x7FFF

    def getLiquidMoveState(self):
        return not GPIO.input(self.LIQUID_MOVE_GPIO_PIN)

    def getLiquidLevelState(self):
        return GPIO.input(self.LIQUID_LEVEL_GPIO_PIN)

    def getTemperature(self):
        return self.__temp.read()

    def getPHLevel(self, temperature=None):
        phMeasure = self.__readAnalog(self.PH_CAN_PIN)
        if temperature is None:
            return (3560 * phMeasure - 1889) / 1000.0
        return 7 - ((2500 - phMeasure) / (257.179 + 0.941468 * temperature))

    def getORPLevel(self):
        orpMeasure = self.__readAnalog(self.ORP_CAN_PIN)
        return int((2500 - orpMeasure) / 1.037)

    def getPressure(self):
        # linear: 0psi=0.5v, 30psi=4.5v => psi = (3 * Umv - 1500) / 400
        psiMeasure = self.__readAnalog(self.PSI_CAN_PIN)
        psi = (3 * psiMeasure - 1500) / 400
        # Conversion en PSI -> Bar
        return psi * 0.06894745

class Command(Debug):
    RELAY_GPIO_PIN = {"pump":26, "robot":19, "light":13, "fill":23, "open":5, "close":6}
    PH_GPIO_PIN = 17
    CL_GPIO_PIN = 27
    def __init__(self):
        Debug.__init__(self)
        # First switch off all
        for pin in self.RELAY_GPIO_PIN.values():
            GPIO.setup(pin, GPIO.OUT, initial=GPIO.LOW)
        # PWM: cl + ph
        GPIO.setup(self.PH_GPIO_PIN, GPIO.OUT, initial=GPIO.LOW)
        GPIO.setup(self.CL_GPIO_PIN, GPIO.OUT, initial=GPIO.LOW)
        self.__cl = self.__ph = None

    def __setattr__(self, item, value):
        if self.RELAY_GPIO_PIN.has_key(item.lower()):
            if type(value) != types.BooleanType:
                raise TypeError
            GPIO.output(self.RELAY_GPIO_PIN[item.lower()], [GPIO.LOW, GPIO.HIGH][value])
        else:
            object.__setattr__(self, item, value)

    def __getattr__(self, item):
        # Called only if item not already defined
        if self.RELAY_GPIO_PIN.has_key(item.lower()):
            return [False, True][GPIO.input(self.RELAY_GPIO_PIN[item.lower()]) == GPIO.HIGH]
        raise AttributeError

    def cl(self, percent, freqHz=100):
        if percent > 0 and percent <= 100:
            self.__cl = GPIO.PWM(self.CL_GPIO_PIN, freqHz)
            self.__cl.start(percent)
            return True
        if self.__cl != None:
            self.__cl.stop()
            self.__cl = None
        return False

    def ph(self, percent, freqHz=100):
        if percent > 0 and percent <= 100:
            self.__ph = GPIO.PWM(self.PH_GPIO_PIN, freqHz)
            self.__ph.start(percent)
            return True
        if self.__ph != None:
            self.__ph.stop()
            self.__ph = None
        return False

def WaterMoveDetection(pin, detected):
    print "Circulation d'eau en cours: %s" % ["NON", "OUI"][detected]

#def RotaryCb(pos, delta):
    #print delta

#def ButtonCb(pin, value):
    #print value

if __name__ == '__main__':
    try:
        GPIO.setmode(GPIO.BCM)
        #if False:
            #rotary = Rotary(False, 22, RotaryCb)
            ##rotary = Rotary(True, 22, RotaryCb, 0, 1000,-1000)
            #button = button.Button(24, 200, ButtonCb)
            #while True:
                #time.sleep(5)
            #assert False, ""
        cmd = Command()
        info = Information(WaterMoveDetection)
        while True:
            pressure = info.getPressure()
            print "Pressure: %.1fpsi / %.1fBar" % (pressure * 14.5038, pressure)
            print "Temperature: %.1fC" % info.getTemperature()
            print "Niveau du PH: %.1f" % info.getPHLevel()
            print "Niveau d'ORP: %dmV" % info.getORPLevel()
            print "Niveau d'eau trop bas: %s" % ["NON", "OUI"][not info.getLiquidLevelState()]
            bitmap = int(time.time() * 1000) & 0xFF
            print hex(bitmap)
            cmd.Pump = (bitmap & 0x01) == 0
            cmd.robot = (bitmap & 0x02) == 0
            cmd.LIGHT = (bitmap & 0x10) == 0
            cmd.fill = (bitmap & 0x20) == 0
            cmd.Open = (bitmap & 0x40) == 0
            cmd.cloSE = (bitmap & 0x80) == 0
            time.sleep(1.0)
    except KeyboardInterrupt:
        pass
    GPIO.cleanup()
