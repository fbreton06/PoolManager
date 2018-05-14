#!/usr/bin/python
import threading
from defines import *

from mode import Mode
from relay import Relay

class PH(Mode, Relay):
    PH_CAN_PIN = 2
    PH_GPIO_PIN = 20
    LOWER_BOUND = 0.0
    UPPER_BOUND = 14.0
    MIN_LEVEL = 7.0
    MAX_LEVEL = 8.0
    INCREMENT = 1.0
    PAUSE = 15.0
    FILTER = 0.03
    def __init__(self, debug, database, default, analog, temperature):
        Mode.__init__(self, database, "ph")
        self.__lock = threading.RLock()
        Relay.__init__(self, self.PH_GPIO_PIN)
        self.__debug = debug
        self.__default = default
        self.__analog = analog
        self.__temperature = temperature
        self.__injectionTimer = None
        self.__current = 0.0
        self.__waitTick = 0
        self.__injection = 37.5             # 250ml
        self.__wait = 600 / REFRESH_TICK    # 10mn de stabilisation
        self.offset = 0.0
        self.idle = 7.2

    def __del__(self):
        with self.__lock:
            if self.__injectionTimer is not None:
                self.__injectionTimer.cancel()
        self.switchOff()

    def __startInjection(self):
        with self.__lock:
            self.switchOn()
            self.__injectionTimer = threading.Timer([self.INCREMENT, self.__duration][self.__duration < self.INCREMENT], self.__endOfInjection)
            self.__injectionTimer.start()

    def __endOfInjection(self):
        with self.__lock:
            self.switchOff()
            if self.__duration < self.INCREMENT:
                self.__duration = 0
            else:
                self.__duration -= self.INCREMENT
            if self.__duration:
                self.__injectionTimer = threading.Timer(self.PAUSE, self.__startInjection)
                self.__injectionTimer.start()
            else:
                self.__debug.TRACE(self.__debug.DETAIL, "PH injection is stopped\n")
                self.__waitTick = self.__wait
                self.__count = 0
                self.__injectionTimer = None

    def __regulation(self):
        if self.__waitGuard > 0:
            self.__waitGuard -= 1
        delta = self.__current - self.idle
        if self.__waitTick > 0:
            self.__waitTick -= 1
            if abs(self.__previous - self.__current) > self.FILTER:
                self.__count = 0
            else:
                self.__count += 1
            self.__previous = self.__current
            if self.__waitTick == 0:
                ratio = 1 + abs(delta / self.__delta)
                if self.__count >= (self.__wait * 0.2):
                    # Stable
                    self.__injection *= ratio
                    self.getDatabase().save("ph", "injection", self.__injection)
                    self.__debug.TRACE(self.__debug.WARNING, "PH injection need to be increased: %.1fs\n", self.__injection)
                else:
                    # Not yet stable
                    self.__wait *= ratio
                    self.getDatabase().save("ph", "wait", self.__wait)
                    self.__debug.TRACE(self.__debug.WARNING, "Wait after PH injection need to be increased: %.1fs\n", self.__wait)
                self.__waitGuard = self.__wait
        if delta > 0:
            if self.__injectionTimer is None and self.__waitTick == 0 and self.__waitGuard == 0:
                if delta >= 0.6:
                    duration = self.__injection
                elif delta >= 0.4:
                    duration = self.__injection * 0.75
                elif delta >= 0.2:
                    duration = self.__injection * 0.5
                else:
                    duration = self.__injection * 0.2
                self.__debug.TRACE(self.__debug.DETAIL, "PH injection is started: %.1fs\n", duration)
                self.__delta = delta
                self.__duration = duration
                self.__startInjection()
        else:
            if self.__injectionTimer is not None:
                self.__injectionTimer.cancel()
                self.__injectionTimer = None
                self.switchOff()
                self.__injection /= 2
                if self.__injection < 2:
                    self.__injection = 2.0
                self.__debug.TRACE(self.__debug.WARNING, "PH injection is really too big: %.1fs\n", self.__injection)
                self.__waitGuard = self.__wait
            elif self.__waitTick > 0:
                if self.__count >= (self.__wait * 0.2):
                    # Stable
                    self.__wait *= 0.9
                    self.getDatabase().save("ph", "wait", self.__wait)
                    self.__debug.TRACE(self.__debug.WARNING, "Wait after PH injection could be decreased: %.1fs\n", self.__wait)
                else:
                    # Not yet stable
                    self.__injection *= 0.9
                    self.getDatabase().save("ph", "injection", self.__injection)
                    self.__debug.TRACE(self.__debug.WARNING, "PH injection could be decreased: %.1fs\n", self.__injection)
                self.__waitTick = 0
                self.__waitGuard = self.__wait

    def __getPHLevel(self):
        # Range: 2.1V to 2.9V: 2.5V +/- 400mV
        phMeasure = self.__analog.read(self.PH_CAN_PIN)
        if self.__temperature.isNoneMode():
            return (3.56 * phMeasure - 1889) / 1000.0
        return 7 - ((2500 - phMeasure) / (257.179 + 0.941468 * self.__temperature.read()))

    def read(self):
        return self.__current

    def update(self):
        with self.__lock:
            self.__current = self.offset + self.__getPHLevel()
            if self.isOffMode():
                if self.isSwitchOn():
                    self.__debug.TRACE(self.__debug.DETAIL, "PH injection is stopped: Forced to OFF\n")
                    self.switchOff()
            elif self.isOnMode():
                if self.isSwitchOff():
                    self.__debug.TRACE(self.__debug.DETAIL, "PH injection is started: Forced to ON (speed=%d)\n", self.PH_PWM_PERCENT)
                    self.switchOn()
            elif self.isAutoMode():
                self.__regulation()
                if self.__current < self.MIN_LEVEL:
                    self.__default.add(self.__default.IMPORTANT, "PH", "Level too low!")
                    self.__debug.TRACE(self.__debug.DETAIL, "PH injection is stopped: PH level too low\n")
                    self.switchOff()
                elif self.__current > self.MAX_LEVEL:
                    self.__default.add(self.__default.IMPORTANT, "PH","Level too high!")

if __name__ == '__main__':
    import time, sys, os
    sys.path.append(os.path.join(os.path.pardir, "RRaspPY"))
    sys.path.append("lib")
    import RPi.GPIO as GPIO        
    from default import Default
    from analog import Analog
    from temperature import Temperature
    from relay import Relay
    from pump import Pump
    from debug import Debug
    debug = Debug(Debug.DEBUG)
    GPIO.cleanup()
    GPIO.setmode(GPIO.BCM)
    class Database:
        def __init__(self):
            self.mode = dict()
            self.mode["ph"] = Mode.READ_STATE # AUTO_STATE READ_STATE
            self.mode["temperature"] = Mode.NONE_STATE # READ_STATE NONE_STATE
        def save(self, a, b, c):
            print "SAVE %s::%s = %s" % (a, b, c)
    try:
        database = Database()
        ph = PH(debug, database, Default(), Analog(0x49), Temperature("28-0417716a37ff", database))
        GPIO.setup(Pump.LIQUID_MOVE_GPIO_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        state = GPIO.input(Pump.LIQUID_MOVE_GPIO_PIN)
        relayPump = Relay(Pump.PUMP_GPIO_PIN)
        relayPump.switchOn()
        time.sleep(2.0)
        if state == GPIO.input(Pump.LIQUID_MOVE_GPIO_PIN):
            relayPump.switchOff()
            raise ValueError, "Water move not detected"
        for i in range(12):
            ph.update()
            print ph.read()
            time.sleep(5)
    except KeyboardInterrupt:
        pass
    except Exception as error:
        print str(error)
    finally:
        if relayPump.isSwitchOn():
            relayPump.switchOff()
        GPIO.cleanup()
