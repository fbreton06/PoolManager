#!/usr/bin/python
import time, threading
from relay import Relay
from mode import Mode

class Light(Relay, Mode):
    MAX__LIGHT_ON_DURATION_S = 3600 * 2 # 2H
    LIGHT_GPIO_PIN = 5
    def __init__(self, database):
        Mode.__init__(self, database, "light")
        Relay.__init__(self, self.LIGHT_GPIO_PIN)
        self.__lock = threading.RLock()
        self.__timer = None
        self.switchOff()

    def __del__(self):
        self.switchOff()

    def switchOn(self):
        if not self.isNoneMode():
            with self.__lock:
                now = time.strftime("%H:%M")
                if now > "21:00" or now < "06:00":
                    super(Light, self).switchOn()
                    self.__timer = threading.Timer(self.MAX__LIGHT_ON_DURATION_S, self.switchOff)
    
    def switchOff(self):
        with self.__lock:
            if self.__timer is not None:
                self.__timer.cancel()
                self.__timer = None
            super(Light, self).switchOff()

    if __name__ == '__main__':
        import sys, os
        sys.path.append(os.path.join(os.path.pardir, "RRaspPY"))
        sys.path.append("lib")
        import RPi.GPIO as GPIO        
        GPIO.cleanup()
        GPIO.setmode(GPIO.BCM)
        class Database:
            def __init__(self):
                self.mode = dict()
                self.mode["light"] = Mode.READ_STATE
            def save(self, a, b, c):
                print "SAVE %s::%s = %s" % (a, b, c)
        try:
            light = Light(Database())
            light.isSwitchOn()
            time.sleep(30)
            light.isSwitchOff()
        except KeyboardInterrupt:
            pass
        except Exception as error:
            print str(error)
        finally:
            GPIO.cleanup()