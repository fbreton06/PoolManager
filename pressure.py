#!/usr/bin/python
from mode import Mode

class Pressure(Mode):
    PSI_CAN_PIN = 3
    def __init__(self, database, default, analog):
        Mode.__init__(self, database, "pressure")
        self.__default = default
        self.__analog = analog
        self.__current = 0.0
        self.__max = 1.3
        self.__dayMax = 0.0
        self.__critical = 1.5

    def __read(self, psiUnit=False):
        # linear: 0psi=0.5v, 30psi=4.5v => psi = (3 * Umv - 1500) / 400
        psiMeasure = self.__analog.read(self.PSI_CAN_PIN)
        psi = (3 * psiMeasure - 1500) / 400.0
        # Conversion en PSI -> Bar
        return [psi * 0.0689476, psi][psiUnit]

    def read(self):
        return self.__current

    def onceByDay(self):
        if self.__dayMax > self.__critical:
            self.__default.add(self.__default.IMPORTANT, "Pressure", "Too high! Clean filters urgently!")
        elif self.__dayMax > self.__max:
            self.__default.add(self.__default.INFORMATION, "Pressure", "Is high. Think to clean filters")
        self.__dayMax = 0

    def update(self):
        if self.isReadMode():
            self.__current = self.__read()
            if self.__current > self.__dayMax:
                self.__dayMax = self.__current

if __name__ == '__main__':
    import time, sys, os
    sys.path.append(os.path.join(os.path.pardir, "RRaspPY"))
    sys.path.append("lib")
    import RPi.GPIO as GPIO
    from default import Default
    from analog import Analog
    from relay import Relay
    from pump import Pump
    GPIO.cleanup()
    GPIO.setmode(GPIO.BCM)
    class Database:
        def __init__(self):
            self.mode = dict()
            self.mode["pressure"] = Mode.READ_STATE
        def save(self, a, b, c):
            print "SAVE %s::%s = %s" % (a, b, c)
    try:
        # Running: should > 0.5Bar (even if the filter is clean)
        pressure = Pressure(Database(), Default(), Analog(0x49))
        pressure.update()
        print "Stopped: %fbar" % pressure.read()
        GPIO.setup(Pump.LIQUID_MOVE_GPIO_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        state = GPIO.input(Pump.LIQUID_MOVE_GPIO_PIN)
        relayPump = Relay(Pump.PUMP_GPIO_PIN)
        relayPump.switchOn()
        time.sleep(2.0)
        if state == GPIO.input(Pump.LIQUID_MOVE_GPIO_PIN):
            relayPump.switchOff()
            raise ValueError, "Water move not detected"
        for i in range(12):
            pressure.update()
            print "Running: %fbar" % pressure.read()
            time.sleep(5)
        relayPump.switchOff()
        time.sleep(20)
        pressure.update()
        print "Stopped: %fbar" % pressure.read()
    except KeyboardInterrupt:
        pass
    except Exception as error:
        print str(error)
    finally:
        if relayPump.isSwitchOn():
            relayPump.switchOff()
        GPIO.cleanup()
