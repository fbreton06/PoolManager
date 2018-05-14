#!/usr/bin/python
import time, threading

import RPi.GPIO as GPIO

from relay import Relay
from mode import Mode

class Waterlevel(Relay, Mode):
    FILLING_GPIO_PIN = 23
    LIQUID_LEVEL_GPIO_PIN = 25
    LIQUID_LEVEL_DEBOUNCE_TIME_S = 300 # 5mn
    def __init__(self, debug, database, debounce_ms=10):
        Mode.__init__(self, database, "waterlevel")
        self.__lock = threading.RLock()
        Relay.__init__(self, self.FILLING_GPIO_PIN)
        self.__debug = debug
        if self.isReadMode():
            self.__levelDebounce = None
            GPIO.setup(self.LIQUID_LEVEL_GPIO_PIN, GPIO.IN)
            GPIO.add_event_detect(self.LIQUID_LEVEL_GPIO_PIN, GPIO.BOTH, callback=self.__levelGpioDetect, bouncetime=debounce_ms)
            self.__liquidLevelState = GPIO.input(self.LIQUID_LEVEL_GPIO_PIN) == GPIO.HIGH

    def __del__(self):
        with self.__lock:
            if self.__levelDebounce is not None:
                self.__levelDebounce.cancel()

    def __getWaterLevelState(self):
        return GPIO.input(pin) == GPIO.HIGH

    def __levelDebounced(self):
        with self.__lock:
            if self.__getWaterLevelState():
                self.__debug.TRACE(self.__debug.DETAIL, "Filling pool is stopped")
                self.switchOff()
                self.__levelDebounce = None

    def __levelGpioDetect(self, pin):
        with self.__lock:
            if self.__levelDebounce is not None:
                if not self.__getWaterLevelState():
                    self.__levelDebounce.cancel()
                    self.__levelDebounce = threading.Timer(self.LIQUID_LEVEL_DEBOUNCE_TIME_S, self.__levelDebounced)
                    self.__levelDebounce.start()
                    self.__debug.TRACE(self.__debug.DETAIL, "Water level event: too low\n")
                else:
                    self.__debug.TRACE(self.__debug.DETAIL, "Water level event: good\n")

    def update(self):
        if self.isOffMode():
            if self.isSwitchOn():
                self.__debug.TRACE(self.__debug.DETAIL, "Filling pool is stopped: Forced to OFF\n")
                self.switchOff()
        elif self.isOnMode():
            if self.isSwitchOff():
                self.__debug.TRACE(self.__debug.DETAIL, "Filling pool is started: Forced to ON\n")
                self.switchOn()
        elif self.isAutoMode():
            now = time.strftime("%H:%M")
            if now > "23:00" or now < "07:00": # Start only when no one should be in the pool
                if not self.__getWaterLevelState():
                    self.__debug.TRACE(self.__debug.DETAIL, "Filling pool is started")
                    self.__levelDebounce = threading.Timer(self.LIQUID_LEVEL_DEBOUNCE_TIME_S, self.__levelDebounced)
                    self.__levelDebounce.start()
                    self.switchOn()

if __name__ == '__main__':
    import time, sys, os
    sys.path.append(os.path.join(os.path.pardir, "RRaspPY"))
    sys.path.append("lib")
    import RPi.GPIO as GPIO        
    from debug import Debug
    debug = Debug(Debug.DEBUG)
    GPIO.cleanup()
    GPIO.setmode(GPIO.BCM)
    class Database:
        def __init__(self):
            self.mode = dict()
            self.mode["waterlevel"] = Mode.AUTO_STATE
        def save(self, a, b, c):
            print "SAVE %s::%s = %s" % (a, b, c)
    try:
        waterlevel = Waterlevel(debug, Database())
        while True:
            waterlevel.update()
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    except Exception as error:
        print str(error)
    finally:
        GPIO.cleanup()