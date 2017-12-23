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
#  16   Rotary CLK
#  20   Rotary DT
#  21   Rotary SW
#  26   Water level (Jaune + R2.2K to GND) (Bleu=GND, noir+marron=5v)
#  12   Water move

# Commands
#  24   Relay IN? (Closing Curtain)
#  23   Relay IN? (Opening Curtain)
#  19   Relay IN? (Water Filling)
#  13   Relay IN? (Lights)
#  06   Relay IN? (Robot)
#  05   Relay IN? (Pump)
#  17   PWM GEN0  (Chlorine Injection)
#  27   PWM GEN2  (PH Injection)

# Add 47u on +5v

# all VDD are +5v

class Information(Debug):
    ORP_CAN_PIN = 1
    PH_CAN_PIN = 2
    PSI_CAN_PIN = 3
    LIQUID_LEVEL_GPIO_PIN = 26
    LIQUID_MOVE_GPIO_PIN = 12
    def __init__(self, moveDetectCb, rotaryCb, buttonCb, debounce_ms=200):
        Debug.__init__(self)
        self.__can = ADS1115(0x49)
        GPIO.setup(self.LIQUID_LEVEL_GPIO_PIN, GPIO.IN)
        GPIO.setup(self.LIQUID_MOVE_GPIO_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        self.__temp = ds18b20.Temperature("28-0417716a37ff")
        self.__moveDetectCb = moveDetectCb
        GPIO.add_event_detect(self.LIQUID_MOVE_GPIO_PIN, GPIO.BOTH, callback=self.__callback, bouncetime=debounce_ms)
        self.rotary = rotary.Rotary(16, 20, 1000, accel=8, callback=rotaryCb)
        self.button = button.Button(21, debounce_ms, callback=buttonCb)

    def __callback(self, pin):
        self.__moveDetectCb(pin, GPIO.input(pin))

    def getLiquidMoveState(self):
        return not GPIO.input(self.LIQUID_MOVE_GPIO_PIN)

    def getLiquidLevelState(self):
        return GPIO.input(self.LIQUID_LEVEL_GPIO_PIN)

    def getTemperature(self):
        return self.__temp.read()

    def getPHLevel(self, temperature=None):
        phMeasure = (4.096 * self.__can.read_adc(self.PH_CAN_PIN)) / 0x7FFF
        if temperature is None:
            return 3.56 * phMeasure - 1.889
        return 7 - ((2.5 - phMeasure) / (0.257179 + 0.000941468 * temperature))

    def getORPLevel(self):
        orpMeasure = (4096 * self.__can.read_adc(self.ORP_CAN_PIN)) / 0x7FFF
        return int((2500 - orpMeasure) / 1.037)

    def getPressure(self):
        # linear: 0psi=0.5v, 30psi=4.5v => psi = (3 * Umv - 1500) / 400
        psiMeasure = (4096 * self.__can.read_adc(self.PSI_CAN_PIN)) / 0x7FFF
        psi = (3 * psiMeasure - 1500) / 400
        # Conversion en PSI -> Bar
        return psi * 0.06894745

class Command(Debug):
    RELAY_GPIO_PIN = {"pump":5, "robot":6, "light":13, "fill":19, "open":23, "close":24}
    def __init__(self):
        Debug.__init__(self)
        # First switch off all
        for pin in self.RELAY_GPIO_PIN.values():
            GPIO.setup(pin, GPIO.OUT, initial=GPIO.LOW)
        # PWM: cl + ph
        GPIO.setup(17, GPIO.OUT, initial=GPIO.LOW)
        GPIO.setup(27, GPIO.OUT, initial=GPIO.LOW)

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

    def cl(self, percent=0, freqHz=1.0):
        if percent > 0 and percent <= 100:
            self.__cl = GPIO.PWM(17, freqHz)
            self.__cl.start(percent)
        else:
            self.__cl.stop()

    def ph(self, percent=0, freqHz=1.0):
        if percent > 0 and percent <= 100:
            self.__ph = GPIO.PWM(27, freqHz)
            self.__ph.start(percent)
        else:
            self.__ph.stop()

def WaterMoveDetection(pin, detected):
    print "Circulation d'eau en cours: %s" % ["NON", "OUI"][detected]

if __name__ == '__main__':
    try:
        GPIO.setmode(GPIO.BCM)
        info = Information(WaterMoveDetection, None, None)
        cmd = Command()
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
            cmd.PH = (bitmap & 0x04) == 0
            cmd.Cl = (bitmap & 0x08) == 0
            cmd.LIGHT = (bitmap & 0x10) == 0
            cmd.fill = (bitmap & 0x20) == 0
            cmd.Open = (bitmap & 0x40) == 0
            cmd.cloSE = (bitmap & 0x80) == 0
            time.sleep(1.0)
    except KeyboardInterrupt:
        pass
    GPIO.cleanup()
