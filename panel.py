#!/usr/bin/python
import threading, time

import RPi.GPIO as GPIO

from defines import *

from lcd1602 import LCD
from rotary import Encoder
from button import Button
from mode import Mode

class Panel(Mode):
    ENCODER_EVENT_GPIO_PIN = 22
    ENCODER_SWITCH_GPIO_PIN = 24
    LCD_LIGHT_TICK = 300 # 5mn    
    def __init__(self, debug, database, default, pump, redox, ph, i2c):
        Mode.__init__(self, database, "panel")
        self.__lock = threading.RLock()
        self.__debug = debug
        self.__default = default
        self.__redox = redox
        self.__ph = ph
        self.__pump = pump
        if not self.isNoneMode():
            self.__encoder = Encoder(False, self.ENCODER_EVENT_GPIO_PIN, self.__encoderMove, bus=i2c)
            self.__button = Button(self.ENCODER_SWITCH_GPIO_PIN, 1000, self.__validButton, GPIO.RISING)
            self.__lcd = LCD(0x27, bus=i2c)
            self.__lcdMenu = "default"
            self.__delay = self.LCD_LIGHT_TICK / REFRESH_TICK
        self.__lcdLightTimer = 0
        self.__calib = None

    def __del__(self):
        with self.__lock:
            if self.__calib is not None:
                self.__calib.cancel()

    def __phCalibrationDone(self):
        with self.__lock:
            self.__calib = None
            self.__debug.TRACE(self.__debug.DEBUG, "PH calibration time elapsed\n")
            self.__ph.offset = self.__lcdValue - self.__ph.read()
            self.__lcdDisplay("ph_done")

    def __orpCalibrationDone(self):
        with self.__lock:
            self.__calib = None
            self.__debug.TRACE(self.__debug.DEBUG, "ORP calibration time elapsed\n")
            self.__redox.offset = self.__lcdValue - self.__redox.read()
            self.__lcdDisplay("orp_done")

    def __lcdDisplay(self, menu=None):
        self.__debug.TRACE(self.__debug.DEBUG, "Menu change: %s -> %s\n", self.__lcdMenu, menu)
        if menu is not None:
            self.__lcdMenu = menu
        self.__lcd.clear()
        if self.__lcdMenu == "default":
            self.__lcd.write(0, 0, "PH=%.1f" % self.__ph.read())
            self.__lcd.write(0, 7, "ORP=%dmV" % self.__redox.read())
            self.__lcd.write(1, 0, time.strftime("%H:%M"))
        elif self.__lcdMenu == "default_sub":
            self.__lcd.write(0, 0, "PH=%.1f" % self.__ph.read())
            self.__lcd.write(0, 7, "ORP=%dmV" % self.__redox.read())
            kind = self.__default.getKindFromIndex(self.__lcdValue)
            if kind:
                self.__lcd.write(1, 0, "Default=%s" % self.__default.getMessage(kind))
            else:
                self.__lcd.write(1, 0, "Back")
                self.__lcdValue = -1
        elif self.__lcdMenu == "ph":
            self.__lcd.write(0, 0, "PH Calibration")
            self.__lcd.write(1, 0, "Enter")
        elif self.__lcdMenu == "ph_sub":
            self.__lcd.write(0, 0, "PH Calibration")
            self.__lcd.write(1, 0, "Wanted %.1f" % self.__lcdValue)
        elif self.__lcdMenu == "ph_calib":
            self.__lcd.write(0, 0, "PH Calibration")
            self.__lcd.write(1, 0, "Please wait...")
        elif self.__lcdMenu == "ph_done":
            self.__lcd.write(0, 0, "PH Calibration")
            self.__lcd.write(1, 0, "Done")
        elif self.__lcdMenu == "orp":
            self.__lcd.write(0, 0, "ORP Calibration")
            self.__lcd.write(1, 0, "Enter")
        elif self.__lcdMenu == "orp_sub":
            self.__lcd.write(0, 0, "ORP Calibration")
            self.__lcd.write(1, 0, "Wanted %dmV" % self.__lcdValue)
        elif self.__lcdMenu == "orp_calib":
            self.__lcd.write(0, 0, "ORP Calibration")
            self.__lcd.write(1, 0, "Please wait...")
        elif self.__lcdMenu == "orp_done":
            self.__lcd.write(0, 0, "ORP Calibration")
            self.__lcd.write(1, 0, "Done")
        elif self.__lcdMenu == "pump":
            self.__lcd.write(0, 0, "Pump state: %s" % self.__pump)
            self.__lcd.write(1, 0, "Enter")
        elif self.__lcdMenu == "pump_sub":
            self.__lcd.write(0, 0, "Pump state: %s" % self.__pump.MODES[self.__lcdValue])
            self.__lcd.write(1, 0, "Back")

    def __validButton(self, pin, state):
        self.__debug.TRACE(self.__debug.DEBUG, "Encoder switch event: %s\n", state)
        if state == True:
            self.__lcdLightTimer = self.__delay
            if not self.__lcd.light():
                self.__lcd.light(True)
                self.__lcdDisplay("default")
            else:
                # Menu
                if self.__lcdMenu == "default":
                    self.__lcdValue = -1
                    if len(self.__default) > 0:
                        self.__lcdValue = 0
                        self.__lcdDisplay("default_sub")
                elif self.__lcdMenu == "ph":
                    self.__lcdValue = 7.0
                    self.__lcdDisplay("ph_sub")
                elif self.__lcdMenu == "orp":
                    self.__lcdValue = 650
                    if self.manager.option.orp:
                        self.__lcdDisplay("orp_sub")
                elif self.__lcdMenu == "pump":
                    self.__lcdValue = self.__pump.getMode()
                    self.__lcdDisplay("pump_sub")
                # SubMenu
                elif self.__lcdMenu == "default_sub":
                    if self.__lcdValue >= 0:
                        self.__default.remove(self.__default.getKindFromIndex(self.__lcdValue))
                    self.__lcdDisplay("default")
                elif self.__lcdMenu == "ph_sub":
                    with self.__lock:
                        self.__calib = threading.Timer(60.0, self.__phCalibrationDone)
                        self.__calib.start()
                    self.__lcdDisplay("ph_calib")
                elif self.__lcdMenu == "orp_sub":
                    with self.__lock:
                        self.__calib = threading.Timer(60.0, self.__orpCalibrationDone)
                        self.__calib.start()
                    self.__lcdDisplay("orp_calib")
                elif self.__lcdMenu == "pump_sub":
                    self.__pump.setMode(self.__lcdValue)
                    self.__lcdDisplay("pump")
                # SubMenuCalibration
                elif self.__lcdMenu == "ph_calib":
                    with self.__lock:
                        if self.__calib is not None:
                            self.__calib.cancel()
                    self.__lcdDisplay("ph")
                elif self.__lcdMenu == "ph_done":
                    self.__lcdDisplay("ph")
                elif self.__lcdMenu == "orp_calib":
                    with self.__lock:
                        if self.__calib is not None:
                            self.__calib.cancel()
                    self.__lcdDisplay("orp")
                elif self.__lcdMenu == "orp_done":
                    self.__lcdDisplay("orp")

    def __encoderMove(self, position, delta):
        self.__debug.TRACE(self.__debug.DEBUG, "Encoder move event: %d(%d)\n", position, delta)
        self.__lcdLightTimer = self.LCD_LIGHT_TICK
        if not self.__lcd.light():
            self.__lcd.light(True)
            self.__lcdDisplay("default")
        else:
            # Menu
            if self.__lcdMenu == "default":
                if delta > 0:
                    self.__lcdDisplay("ph")
                else:
                    self.__lcdDisplay("pump")
            elif self.__lcdMenu == "ph":
                if delta > 0:
                    self.__lcdDisplay("orp")
                else:
                    self.__lcdDisplay("default")
            elif self.__lcdMenu == "orp":
                if delta > 0:
                    self.__lcdDisplay("pump")
                else:
                    self.__lcdDisplay("ph")
            elif self.__lcdMenu == "pump":
                if delta > 0:
                    self.__lcdDisplay("default")
                else:
                    self.__lcdDisplay("orp")
            # SubMenu
            elif self.__lcdMenu == "default_sub":
                self.__lcdValue = (self.__lcdValue + [-1, 1][delta > 0]) % len(self.__default)
                self.__lcdDisplay()
            elif self.__lcdMenu == "ph_sub":
                self.__lcdValue += (delta / 10.0)
                if self.__lcdValue > self.__ph.UPPER_BOUND:
                    self.__lcdValue = self.__ph.UPPER_BOUND
                elif self.__lcdValue < self.__ph.LOWER_BOUND:
                    self.__lcdValue = self.__ph.LOWER_BOUND
                self.__lcdDisplay()
            elif self.__lcdMenu == "orp_sub":
                if abs(delta) > 1:
                    delta *= 5
                self.__lcdValue += delta
                if self.__lcdValue > self.__redox.UPPER_BOUND:
                    self.__lcdValue = self.__redox.UPPER_BOUND
                elif self.__lcdValue < self.__redox.LOWER_BOUND:
                    self.__lcdValue = self.__redox.LOWER_BOUND
                self.__lcdDisplay()
            elif self.__lcdMenu == "pump_sub":
                self.__lcdValue = (self.__lcdValue + [-1, 1][delta > 0]) % 3 # Only Off/On/Auto
                self.__lcdDisplay()

    def update(self):
        if self.__lcdLightTimer > 0:
            self.__lcdLightTimer -= 1
            if self.__lcdLightTimer <= 0:
                self.__lcd.light(False)
            elif self.__lcdMenu == "default":
                self.__lcdDisplay()
