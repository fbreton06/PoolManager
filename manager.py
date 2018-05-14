#!/usr/bin/python

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
#  27   PWM GEN0  (Redox Injection)
#  17   PWM GEN2  (PH Injection)

# Add 47u on +5v

# all VDD are +5v

import os, time, sys, types
from datetime import date
from defines import *

sys.path.append(os.path.join(os.path.pardir, "RRaspPY"))
sys.path.append("lib")
import RPi.GPIO as GPIO

from i2c import I2C
from analog import Analog
from default import Default
from database import Database
from waterlevel import Waterlevel
from light import Light
from curtain import Curtain
from pressure import Pressure
from temperature import Temperature
from redox import Redox
from ph import PH
from robot import Robot
from pump import Pump
from panel import Panel
from statistic import Statistic

from debug import Debug
debug = Debug(Debug.DEBUG) # ERROR DEBUG DUMP

class Manager:
    AUTO_START_GPIO_PIN = 16
    ONCE_BY_HOUR_TICK = 360 # 1h
    def __init__(self, refPath, dataPath, dbFilename):
        GPIO.cleanup()
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.AUTO_START_GPIO_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        self.__i2c = I2C(2)
        self.__analog = Analog(sel.__i2c.getLock(), 0x49)
        self.default = Default()
        self.database = Database(dataPath, dbFilename)
        self.waterlevel = Waterlevel(debug, self.database)
        self.light = Light(self.database)
        self.curtain = Curtain(self.database)
        self.pressure = Pressure(self.database, self.default, self.__analog)
        self.temperature = Temperature("28-0417716a37ff", self.database)
        self.redox = Redox(debug, self.database, self.default, self.__analog)
        self.ph = PH(debug, self.database, self.default, self.__analog, self.temperature)
        self.robot = Robot(debug, self.database)
        self.pump = Pump(debug, self.database, self.default, self.robot, self.redox, self.ph, self.temperature)
        self.panel = Panel(debug, self.database, self.default, self.pump, self.redox, self.ph, self.__i2c)
        self.statistic = Statistic(debug, self.pump, self.robot, self.redox, self.ph, self.temperature, self.pressure, self.waterlevel)
        self.refPath = refPath
        self.__autoSaveTick = 0
        self.__today = date.today().day - 1
        debug.TRACE(debug.DEBUG, "Initialisation done (Verbosity level: %s)\n", debug)

    def __del__(self):
        GPIO.cleanup()

    def __onceByHour(self):
        if self.__autoSaveTick == self.ONCE_BY_HOUR_TICK:
            self.database.backup()
            self.__autoSaveTick = 0
            # All seems to be OK, we can remove the previous version
            backup = os.path.join(self.refPath, "PoolSurvey_bak")
            if os.path.exists(backup):
                os.system("rm -frd %s" % backup)
        self.__autoSaveTick += 1

    def __onceByDay(self):
        if self.__today != date.today().day:
            self.__today = date.today().day
            self.pressure.onceByDay()
            self.pump.onceByDay()
            self.statistic.onceByDay()

    def isAutoStart(self):
        return GPIO.input(self.AUTO_START_GPIO_PIN) == GPIO.LOW

    def start(self):
        debug.TRACE(debug.DEBUG, "Manager is started\n")
        self.__running = True
        while self.__running:
            debug.TAG(debug.DETAIL, "%ds Tick" % REFRESH_TICK)
            self.temperature.update()
            self.__onceByDay()
            self.pump.update()
            if self.pump.guardPeriodElapsed():
                self.robot.update()
                self.ph.update()
                self.redox.update()
                self.waterlevel.update()
                self.pressure.update()
                self.panel.update()
            self.statistic.update()
            self.__onceByHour()
            time.sleep(REFRESH_TICK)
        debug.TRACE(debug.DEBUG, "Manager is stopped\n")
        self.pump.switchOff()
        self.statistic.save()

    def stop(self):
        self.__running = False

if __name__ == '__main__':
    try:
        manager = Manager(os.getcwd(), os.getcwd(), "db.ini")
        manager.start()
    finally:
        manager.stop()
