#!/usr/bin/python
import sys
from mode import Mode
sys.path.append("lib")
import ds18b20

class Temperature(Mode):
    def __init__(self, device, database):
        Mode.__init__(self, database, "temperature")
        if self.isReadMode():
            self.__temp = ds18b20.Temperature(device)
        self.__current = 0.0
        self.__dayMax = -273.0
        self.__winter = 10.0

    def __read(self):
        return self.__temp.read()

    def getRange(self, values):
        dayMax = self.__dayMax
        self.__dayMax = -273.0
        if dayMax < self.__winter:
            return -1, dayMax
        for value in values:
            if dayMax < value:
                return values.index(value), dayMax
        return len(values), dayMax

    def read(self):
        return self.__current

    def update(self):
        if self.isReadMode():
            self.__current = self.__read()
            if self.__current > self.__dayMax:
                self.__dayMax = self.__current
                self.getDatabase().save("temperature", "max", self.__dayMax)

if __name__ == '__main__':
    import time, sys, os
    sys.path.append(os.path.join(os.path.pardir, "RRaspPY"))
    sys.path.append("lib")
    import RPi.GPIO as GPIO        
    GPIO.cleanup()
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(self.AUTO_START_GPIO_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    class Database:
        def __init__(self):
            self.mode = dict()
            self.mode["curtain"] = Mode.READ_STATE
        def save(self, a, b, c):
            print "SAVE %s::%s = %s" % (a, b, c)
    try:
        temperature = Temperature("28-0417716a37ff", Database())
        while True:
            temperature.update()
            print temperature.read()
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    except Exception as error:
        print str(error)
    finally:
        GPIO.cleanup()