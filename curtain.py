#!/usr/bin/python
import threading
from relay import Relay
from mode import Mode

class Curtain(Mode):
    R1_GPIO_PIN = 13
    R2_GPIO_PIN = 6
    OPEN_CLOSE_TIME_S = 180
    def __init__(self, database):
        Mode.__init__(self, database, "curtain")
        self.__lock = threading.RLock()
        self.__r1 = Relay(self.R1_GPIO_PIN)
        self.__r2 = Relay(self.R2_GPIO_PIN)
        self.__timer = None
        self.stop()

    def __del__(self):
        self.stop()

    def close(self):
        if not self.isNoneMode():
            with self.__lock:
                if self.__timer is not None:
                    self.__timer.cancel()
                self.__r1.switchOn()
                self.__r2.switchOff()
                self.__timer = threading.Timer(self.OPEN_CLOSE_TIME_S, self.stop)

    def open(self):
        if not self.isNoneMode():
            with self.__lock:
                if self.__timer is not None:
                    self.__timer.cancel()
                self.__r1.switchOff()
                self.__r2.switchOn()
                self.__timer = threading.Timer(self.OPEN_CLOSE_TIME_S, self.stop)

    def isSwitchOn(self):
        with self.__lock:
            return self.__r1.isSwitchOn() or self.__r2.isSwitchOn()

    def isSwitchOff(self):
        with self.__lock:
            return self.__r1.isSwitchOff() and self.__r2.isSwitchOff()

    def isClosing(self):
        with self.__lock:
            return self.__r1.isSwitchOn() and self.__r2.isSwitchOff()

    def isOpening(self):
        with self.__lock:
            return self.__r1.isSwitchOff() and self.__r2.isSwitchOn()

    def stop(self):
        with self.__lock:
            if self.__timer is not None:
                self.__timer.cancel()
                self.__timer = None
            self.__r1.switchOff()
            self.__r2.switchOff()

if __name__ == '__main__':
    import time, sys, os
    sys.path.append(os.path.join(os.path.pardir, "RRaspPY"))
    sys.path.append("lib")
    import RPi.GPIO as GPIO
    GPIO.cleanup()
    GPIO.setmode(GPIO.BCM)
    class Database:
        def __init__(self):
            self.mode = dict()
            self.mode["curtain"] = Mode.READ_STATE
        def save(self, a, b, c):
            print "SAVE %s::%s = %s" % (a, b, c)
    try:
        curtain = Curtain(Database())
        curtain.open()
        #curtain.close()
        print "1 - %s: %s" % (curtain, ["stopped",["closing","opening"][curtain.isOpening()]][curtain.isSwitchOn()])
        time.sleep(curtain.OPEN_CLOSE_TIME_S + 30)
        print "2 - %s: %s" % (curtain, ["stopped",["closing","opening"][curtain.isOpening()]][curtain.isSwitchOn()])
    except KeyboardInterrupt:
        pass
    except Exception as error:
        print str(error)
    finally:
        if curtain.isSwitchOn():
            curtain.stop()
            print "3 - %s: %s" % (curtain, ["stopped",["closing","opening"][curtain.isOpening()]][curtain.isSwitchOn()])
        GPIO.cleanup()
