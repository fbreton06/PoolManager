#!/usr/bin/python
import time, threading
from defines import *

import RPi.GPIO as GPIO

from relay import Relay
from mode import Mode

class Pump(Relay, Mode):
    PUMP_GPIO_PIN = 26
    LIQUID_MOVE_GPIO_PIN = 12
    LIQUID_MOVE_DEBOUNCE_TIME_S = 0.5
    GUARD_PERIOD = 60 / REFRESH_TICK  # 1mn
    def __init__(self, debug, database, default, robot, redox, ph, temperature, debounce_ms=10):
        Mode.__init__(self, database, "pump")
        self.__lock = threading.RLock()
        Relay.__init__(self, self.PUMP_GPIO_PIN)
        self.__debug = debug
        self.__default = default
        self.__robot = robot
        self.__redox = redox
        self.__ph = ph
        self.__temperature = temperature
        self.__guard = self.GUARD_PERIOD
        self.__previousMode = None
        self.__moveDebounce = None
        GPIO.setup(self.LIQUID_MOVE_GPIO_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.add_event_detect(self.LIQUID_MOVE_GPIO_PIN, GPIO.BOTH, callback=self.__moveGpioDetect, bouncetime=debounce_ms)
        self.autoPrograms = list()
        self.programs = list()
        self.fullAuto = True

    def __del__(self):
        self.__stopPump("Emergency: stop")

    def __getLiquidMoveState(self):
        return GPIO.input(self.LIQUID_MOVE_GPIO_PIN) == GPIO.LOW

    def __moveDebounced(self):
        with self.__lock:
            if self.__moveState is None or not self.__moveState:
                self.__stopPump("Emergency: Event waterFlow seems to be blocked! Check valves state!")
                self.__default.add(self.__default.CRITICAL, "WaterFlow", "Seems to be blocked! Check valves state!")
            else:
                self.__debug.TRACE(self.__debug.DETAIL, "Move detected\n")

    def __moveGpioDetect(self, pin):
        with self.__lock:
            if self.__moveDebounce is not None:
                if self.__moveState is None:
                    self.__moveState = self.__getLiquidMoveState()
                    self.__moveDebounce.start()
                elif self.__moveState != self.__getLiquidMoveState():
                    self.__moveDebounce.cancel()
                    self.__moveState = not self.__moveState
                    self.__moveDebounce = threading.Timer(self.LIQUID_MOVE_DEBOUNCE_TIME_S, self.__moveDebounced)
                    self.__moveDebounce.start()
                self.__debug.TRACE(self.__debug.DETAIL, "Water move event: %s\n", self.__moveState)

    def __startPump(self, reason=""):
        self.__debug.TRACE(self.__debug.DETAIL, "Pump is started: %s\n", reason)
        with self.__lock:
            self.__moveState = None
            self.__moveDebounce = threading.Timer(self.LIQUID_MOVE_DEBOUNCE_TIME_S, self.__moveDebounced)
            self.switchOn()
            time.sleep(2) # TODO 2 a voir a l'usage
            if not self.__getLiquidMoveState():
                self.__stopPump("Emergency: WaterFlow seems to be blocked! Check valves state!")
                self.__default.add(self.__default.CRITICAL, "WaterFlow", "Seems to be blocked! Check valves state!")
    
    def __stopPump(self, reason, delay_s=0):
        with self.__lock:
            if self.__moveDebounce is not None:
                self.__moveDebounce.cancel()
            self.__moveDebounce = None
        self.__debug.TRACE(self.__debug.DETAIL, "Robot is stopped: %s\n", reason)
        self.__robot.switchOff()
        self.__debug.TRACE(self.__debug.DETAIL, "PH injection is stopped: %s\n", reason)
        self.__ph.switchOff()
        self.__debug.TRACE(self.__debug.DETAIL, "Chlore injection is stopped: %s\n", reason)
        self.__redox.switchOff()
        if delay_s == 0:
            # Emergency stop! We must to prevent the pump to restart
            self.__previousMode = self.getMode()
            self.setMode(self.OFF_STATE)
            self.switchOff()
            self.getDatabase().backup()
        else:
            time.sleep(delay_s) # TODO 2 a voir a l'usage
            self.__debug.TRACE(self.__debug.DETAIL, "Pump is stopped: %s (delay=%ds)\n", reason, delay_s)
            self.switchOff()
        self.__guard = self.GUARD_PERIOD

    def __computSchedulingTime(self, startHour, startMn, duration):
        start = startHour * 60 + startMn
        stop = start + duration * 60
        stopHour = int(stop / 60)
        stopMn = int(stop - stopHour * 60)
        return "%02d:%02d\t%02d:%02d" % (startHour, startMn, stopHour, stopMn)

    def onceByDay(self):
        programs = list()
        if self.__temperature.isReadMode():
            value, dayMax = self.__temperature.getRange((12.0, 16.0, 20.0, 27.0, 29.0, 31.0))
            if value < 0:
                # ...-Winter[ : 2H
                self.__default.add(self.__default.INFORMATION, "Wintering", "Enter")
                programs.append("12:00\t14:00")
            elif value == 0:
                # [Winter-12[ : 4H
                programs.append("11:00\t15:00")
            elif value == 1:
                # [12-16[ : 6H
                programs.append("11:00\t14:00")
                programs.append("15:00\t18:00")
            elif value == 2:
                # [16-20[ : 8H
                programs.append("09:30\t:13:30")
                programs.append("14:30\t:18:30")
            elif value == 3:
                # [20-27[ : temp/2 (10H to 13.5H)
                duration = float(dayMax) / 2
                if duration <= 12.0:
                    programs.append(self.__computSchedulingTime(6, 0, duration / 3))
                    programs.append(self.__computSchedulingTime(11, 0, duration / 3))
                    programs.append(self.__computSchedulingTime(16, 0, duration / 3))
                else:
                    programs.append(self.__computSchedulingTime(3, 0, duration / 4))
                    programs.append(self.__computSchedulingTime(8, 0, duration / 4))
                    programs.append(self.__computSchedulingTime(13, 0, duration / 4))
                    programs.append(self.__computSchedulingTime(18, 0, duration / 4))
            elif value == 4:
                # [27-29[ : 16H
                programs.append("03:00\t07:00")
                programs.append("08:00\t12:00")
                programs.append("13:00\t17:00")
                programs.append("18:00\t22:00")
            elif value == 5:
                # [29-31[ : 19H
                programs.append("00:00\t12:00")
                programs.append("12:30\t23:30")
                programs.append("00:00\t12:00")
                programs.append("12:30\t23:30")
                programs.appen__previousModed("12:30\t23:30")
            else:
                # 23H
                programs.append("00:00\t12:00")
                programs.append("12:30\t23:30")
            self.__debug.TRACE(self.__debug.DETAIL, "Programmation at %.1fC\n\tStart\tStop\n\tHH:MN\tHH:MN\n", dayMax)
            for program in programs:
                self.__debug.TRACE(self.__debug.DETAIL, "\t%s\n", program)
        self.autoPrograms = programs

    def appendProgram(self, entry):
        self.programs.append(entry)
        # Check coherency
        prev = "00:00"
        pumps = list()
        for start, stop in [x.split() for x in self.programs]:
            if stop > start:
                if start > prev:
                    pumps.append("%s\t%s" % (start, stop))
                    prev = stop
                elif stop > prev:
                    start, prev = pumps[-1].split()
                    pumps[-1] = "%s\t%s" % (start, stop)
                    prev = stop
        self.programs = pumps

    def guardPeriodElapsed(self):
        return self.__guard == 0

    def update(self):
        if self.__previousMode is not None:
            if self.__default.critical == 0:
                self.setMode(self.__previousMode)
                self.__previousMode = None
        if self.__guard > 0:
            self.__guard -= 1
        if self.isOffMode():
            if self.isSwitchOn():
                self.__stopPump("Forced to OFF", 2)
        elif self.isOnMode():
            if self.isSwitchOff():
                self.__startPump("Forced to ON")
        elif self.isAutoMode():
            if self.fullAuto:
                pumps = self.autoPrograms
            else:
                pumps = self.programs
            pump = False
            if len(pumps) > 0:
                now = time.strftime("%H:%M")
                for start, stop in [x.split() for x in pumps]:
                    if start <= now < stop:
                        pump = True
            if self.isSwitchOn() ^ pump:
                if pump:
                    self.__startPump("Automatic mode")
                else:
                    self.__stopPump("Automatic mode", 2)
