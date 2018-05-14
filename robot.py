#!/usr/bin/python
import time

from relay import Relay
from mode import Mode

class Robot(Relay, Mode):
    ROBOT_GPIO_PIN = 19
    def __init__(self, debug, database):
        Mode.__init__(self, database, "robot")
        Relay.__init__(self, self.ROBOT_GPIO_PIN)
        self.__debug = debug
        self.programs = list()

    def __del__(self):
        self.switchOff()

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

    def update(self):
        if self.isOffMode():
            if self.isSwitchOn():
                self.__debug.TRACE(self.__debug.DETAIL, "Robot is stopped: Forced to OFF\n")
                self.switchOff()
        elif self.isOnMode():
            if self.isSwitchOff():
                self.__debug.TRACE(self.__debug.DETAIL, "Robot is started: Forced to ON\n")
                self.switchOn()
        elif self.isAutoMode():
            robotState = False
            now = time.strftime("%H:%M")
            if self.programs:
                for start, stop in [x.split() for x in self.programs]:
                    if start <= now < stop:
                        robotState = True
            if self.isSwitchOff() ^ robotState:
                self.__debug.TRACE(self.__debug.DETAIL, "Robot is %s: Automatic mode\n", ["stopped", "started"][robotState])
                self.switchToggle()

if __name__ == '__main__':
    import time, sys, os
    sys.path.append(os.path.join(os.path.pardir, "RRaspPY"))
    sys.path.append("lib")
    import RPi.GPIO as GPIO        
    from relay import Relay
    from pump import Pump
    from debug import Debug
    debug = Debug(Debug.DEBUG)
    GPIO.cleanup()
    GPIO.setmode(GPIO.BCM)
    class Database:
        def __init__(self):
            self.mode = dict()
            self.mode["robot"] = Mode.READ_STATE
        def save(self, a, b, c):
            print "SAVE %s::%s = %s" % (a, b, c)
    try:
        robot = Robot(debug, Database())
        GPIO.setup(Pump.LIQUID_MOVE_GPIO_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        state = GPIO.input(Pump.LIQUID_MOVE_GPIO_PIN)
        relayPump = Relay(Pump.PUMP_GPIO_PIN)
        relayPump.switchOn()
        time.sleep(2.0)
        if state == GPIO.input(Pump.LIQUID_MOVE_GPIO_PIN):
            relayPump.switchOff()
            raise ValueError, "Water move not detected"
        time.sleep(10)
        robot.switchOn()
        #time.sleep(60)
        robot.switchOff()
        time.sleep(10)
        relayPump.switchOff()
    except KeyboardInterrupt:
        pass
    except Exception as error:
        print str(error)
    finally:
        if robot.isSwitchOn():
            robot.switchOff()
        if relayPump.isSwitchOn():
            relayPump.switchOff()
        GPIO.cleanup()