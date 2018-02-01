#!/usr/bin/python
import os, time, sys, types, threading
from datetime import date

if __name__ == "__main__":
    path = os.getcwd()
else:
    path = os.path.dirname(__file__)
sys.path.append(os.path.join(path, "lib"))

from helper import Debug
from hardware import Information, Command, Rotary
from database import Database
import button, smbus

from lcd1602 import LCD
import RPi.GPIO as GPIO

try:
    raise ErrorValue, "fake"
    from tmp import tmpClass as MyClass
except:
    class MyClass:
        def alert(self, message):
            pass

class I2C:
    def __init__(self, nbClient):
        self.__count = nbClient
        self.__smbus = smbus.SMBus(1)
        self.lock = threading.RLock()

    def read_byte(self, address):
        with self.lock:
            value = self.__smbus.read_byte(address)
        return value

    def write_byte(self, address, value):
        with self.lock:
            self.__smbus.write_byte(address, value)

    def write_byte_data(self, address, value, data):
        with self.lock:
            self.__smbus.write_byte_data(address, value, data)

    def close(self):
        self.__count -= 1
        if self.__count == 0:
            self.__smbus.close()

class Manager(MyClass, Debug, threading.Thread):
    class Fake: pass
    DEFAULT_CRITICAL = 1
    DEFAULT_IMPORTANT = 2
    DEFAULT_INFORMATION = 3
    DATABASE_SAVE_TICK = 360 # 1h
    LCD_LIGHT_TICK = 30 # 5mn
    REFRESH_TICK = 10 # in second
    OFF_STATE = 0
    ON_STATE = 1
    AUTO_STATE = 2
    SIMU = False
    PUMP_MODES = ("OFF", "ON", "AUTO")
    ROTARY_EVENT_GPIO_PIN = 22
    ROTARY_SWITCH_GPIO_PIN = 24
    PH_PWM_PERCENT = 10
    CL_PWM_PERCENT = 10
    def __init__(self):
        Debug.__init__(self, Debug.ERROR)
        threading.Thread.__init__(self)
        self.__event = threading.Event()
        GPIO.cleanup()
        GPIO.setmode(GPIO.BCM)
        self.cmd = Command()
        self.cmd.debug_level = self.debug_level
        self.info = Information(self.__waterMoveDetect)
        self.info.debug_level = self.debug_level
        self.__i2c = I2C(2)
        self.__rotary = Rotary(False, self.ROTARY_EVENT_GPIO_PIN, self.__rotaryMove, bus=self.__i2c)
        self.__button = button.Button(self.ROTARY_SWITCH_GPIO_PIN, 1000, self.__validButton, GPIO.RISING)        
        self.lcd = LCD(0x27, bus=self.__i2c)
        self.lcdLightTimer = 0
        self.database = Database()
        self.database.debug_level = self.debug_level
        for section in self.database.sections():
            assert not self.__dict__.has_key(section), "Member name \"%s\" conflict!" % section
            self.__dict__[section] = self.Fake()
            for key, value in self.database.items(section):
                self.__dict__[section].__dict__[key] = self.database.get(section, key)
        self.autoSaveTick = 0
        self.__today = date.today().day - 1
        self.lcdMenu = "default"
        self.TRACE(Debug.INFO, "Initialisation done (%s)\n", self.getVerbosity())

    def __del__(self):
        GPIO.cleanup()

    def __str__(self):
        return self.html("\n", "\n")

    def html(self, subeol="<br>", eol="<br>"):
        text = ""
        for section in self.database.sections():
            text += "%s[%s]%s" % (eol, section, eol)
            for key, value in self.database.items(section):
                text += "%s = %s%s" % (key, self.__dict__[section].__dict__[key], subeol)
        return text

    def lcdDisplay(self, menu=None):
        self.TRACE(Debug.DEBUG, "Menu change: %s -> %s\n", self.lcdMenu, menu)
        #print 
        if menu != None:
            self.lcdMenu = menu
        self.lcd.clear()
        if self.lcdMenu == "default":
            self.lcd.write(0, 0, "PH=%.1f" % self.ph.current)
            self.lcd.write(0, 7, "ORP=%dmV" % self.orp.current)
            self.lcd.write(1, 0, time.strftime("%H:%M"))
        elif self.lcdMenu == "default_sub":
            self.lcd.write(0, 0, "PH=%.1f" % self.ph.current)
            self.lcd.write(0, 7, "ORP=%dmV" % self.orp.current)
            if len(self.state.defaults) > 0:
                self.lcd.write(1, 0, "Default=%s" % self.state.defaults[self.lcdValue].split()[-1])
            else:
                self.lcd.write(1, 0, "Back")
        elif self.lcdMenu == "ph":
            self.lcd.write(0, 0, "PH Calibration")
            self.lcd.write(1, 0, "Enter")
        elif self.lcdMenu == "ph_sub":
            self.lcd.write(0, 0, "PH Calibration")
            self.lcd.write(1, 0, "Wanted %.1f" % self.lcdValue)
        elif self.lcdMenu == "ph_calib":
            self.lcd.write(0, 0, "PH Calibration")
            self.lcd.write(1, 0, "Please wait...")
        elif self.lcdMenu == "ph_done":
            self.lcd.write(0, 0, "PH Calibration")
            self.lcd.write(1, 0, "Done")
        elif self.lcdMenu == "orp":
            self.lcd.write(0, 0, "ORP Calibration")
            self.lcd.write(1, 0, "Enter")
        elif self.lcdMenu == "orp_sub":
            self.lcd.write(0, 0, "ORP Calibration")
            self.lcd.write(1, 0, "Wanted %dmV" % self.lcdValue)
        elif self.lcdMenu == "orp_calib":
            self.lcd.write(0, 0, "ORP Calibration")
            self.lcd.write(1, 0, "Please wait...")
        elif self.lcdMenu == "orp_done":
            self.lcd.write(0, 0, "ORP Calibration")
            self.lcd.write(1, 0, "Done")
        elif self.lcdMenu == "pump":
            self.lcd.write(0, 0, "Pump state: %s" % self.PUMP_MODES[self.mode.pump])
            self.lcd.write(1, 0, "Enter")
        elif self.lcdMenu == "pump_sub":
            self.lcd.write(0, 0, "Pump state: %s" % self.PUMP_MODES[self.lcdValue])
            self.lcd.write(1, 0, "Back")

    def __phCalibrationDone(self):
        self.TRACE(Debug.DEBUG, "PH calibration time elapsed\n")
        self.ph.offset = self.lcdValue - self.ph.current
        self.lcdDisplay("ph_done")

    def __orpCalibrationDone(self):
        self.TRACE(Debug.DEBUG, "ORP calibration time elapsed\n")
        self.orp.offset = self.lcdValue - self.orp.current
        self.lcdDisplay("orp_done")

    def __validButton(self, pin, state):
        self.TRACE(Debug.DEBUG, "Rotary switch event: %s\n", state)
        if state == True:
            self.lcdLightTimer = self.LCD_LIGHT_TICK
            if not self.lcd.light():
                self.lcd.light(True)
                self.lcdDisplay("default")
            else:
                # Menu
                if self.lcdMenu == "default":
                    self.lcdValue = 0
                    self.lcdDisplay("default_sub")
                elif self.lcdMenu == "ph":
                    self.lcdValue = 7.0
                    self.lcdDisplay("ph_sub")
                elif self.lcdMenu == "orp":
                    self.lcdValue = 650
                    self.lcdDisplay("orp_sub")
                elif self.lcdMenu == "pump":
                    self.lcdValue = self.mode.pump
                    self.lcdDisplay("pump_sub")
                # SubMenu
                elif self.lcdMenu == "default_sub":
                    self.state.defaults.pop(self.lcdValue)
                    self.lcdDisplay("default")
                elif self.lcdMenu == "ph_sub":
                    self.__calib = threading.Timer(60.0, self.__phCalibrationDone)
                    self.__calib.start()
                    self.lcdDisplay("ph_calib")
                elif self.lcdMenu == "orp_sub":
                    self.__calib = threading.Timer(60.0, self.__orpCalibrationDone)
                    self.__calib.start()
                    self.lcdDisplay("orp_calib")
                elif self.lcdMenu == "pump_sub":
                    self.mode.pump = self.lcdValue
                    self.lcdDisplay("pump")
                # SubMenuCalibration
                elif self.lcdMenu == "ph_calib":
                    self.__calib.cancel()
                    self.lcdDisplay("ph")
                elif self.lcdMenu == "ph_done":
                    self.lcdDisplay("ph")
                elif self.lcdMenu == "orp_calib":
                    self.__calib.cancel()
                    self.lcdDisplay("orp")
                elif self.lcdMenu == "orp_done":
                    self.lcdDisplay("orp")

    def __rotaryMove(self, position, delta):
        self.TRACE(Debug.DEBUG, "Rotary change event: %d(%d)\n", position, delta)
        self.lcdLightTimer = self.LCD_LIGHT_TICK
        if not self.lcd.light():
            self.lcd.light(True)
            self.lcdDisplay("default")
        else:
            # Menu
            if self.lcdMenu == "default":
                if delta > 0:
                    self.lcdDisplay("ph")
                else:
                    self.lcdDisplay("pump")
            elif self.lcdMenu == "ph":
                if delta > 0:
                    self.lcdDisplay("orp")
                else:
                    self.lcdDisplay("default")
            elif self.lcdMenu == "orp":
                if delta > 0:
                    self.lcdDisplay("pump")
                else:
                    self.lcdDisplay("ph")
            elif self.lcdMenu == "pump":
                if delta > 0:
                    self.lcdDisplay("default")
                else:
                    self.lcdDisplay("orp")
            # SubMenu
            elif self.lcdMenu == "default_sub":
                self.lcdValue = (self.lcdValue + [-1, 1][delta > 0]) % len(self.state.defaults)
                self.lcdDisplay()
            elif self.lcdMenu == "ph_sub":
                self.lcdValue += (delta / 10.0)
                if self.lcdValue > self.ph.ubound:
                    self.lcdValue = self.ph.ubound
                elif self.lcdValue < self.ph.lbound:
                    self.lcdValue = self.ph.lbound
                self.lcdDisplay()
            elif self.lcdMenu == "orp_sub":
                if abs(delta) > 1:
                    delta *= 5
                self.lcdValue += delta
                if self.lcdValue > self.orp.ubound:
                    self.lcdValue = self.orp.ubound
                elif self.lcdValue < self.orp.lbound:
                    self.lcdValue = self.orp.lbound
                self.lcdDisplay()
            elif self.lcdMenu == "pump_sub":
                self.lcdValue = (self.lcdValue + [-1, 1][delta > 0]) % len(self.PUMP_MODES)
                self.lcdDisplay()

    def __waterMoveDetect(self, pin, detected):
        self.TRACE(Debug.DETAIL, "Water move event: %s\n", detected)
        if not detected and self.cmd.pump:
            self.newDefault(self.DEFAULT_CRITICAL, "Water seems to be blocked! Check valves state!")

    def __computSchedulingTime(self, startHour, startMn, duration):
        start = startHour * 60 + startMn
        stop = start + duration * 60
        stopHour = int(stop / 60)
        stopMn = int(stop - stopHour * 60)
        return "%02d:%02d\t%02d:%02d" % (startHour, startMn, stopHour, stopMn)

    def __computePumpScheduling(self, temperature):
        self.program.auto = list()
        if temperature < self.temp.winter:
            # ...-Winter[ : 2H
            self.newDefault(self.DEFAULT_INFORMATION, "Wintering!")
            self.program.auto.append("12:00\t14:00")
        elif temperature < 12.0:
            # [Winter-12[ : 4H
            self.program.auto.append("11:00\t15:00")
        elif temperature < 16.0:
            # [12-16[ : 6H
            self.program.auto.append("11:00\t14:00")
            self.program.auto.append("15:00\t18:00")
        elif temperature < 20.0:
            # [16-20[ : 8H
            self.program.auto.append("09:30\t:13:30")
            self.program.auto.append("14:30\t:18:30")
        elif temperature < 27.0:
            # [20-27[ : temp/2 (10H to 13.5H)
            duration = float(temperature) / 2
            if duration <= 12.0:
                self.program.auto.append(self.__computSchedulingTime(6, 0, duration / 3))
                self.program.auto.append(self.__computSchedulingTime(11, 0, duration / 3))
                self.program.auto.append(self.__computSchedulingTime(16, 0, duration / 3))
            else:
                self.program.auto.append(self.__computSchedulingTime(3, 0, duration / 4))
                self.program.auto.append(self.__computSchedulingTime(8, 0, duration / 4))
                self.program.auto.append(self.__computSchedulingTime(13, 0, duration / 4))
                self.program.auto.append(self.__computSchedulingTime(18, 0, duration / 4))
        elif temperature < 29.0:
            # [27-29[ : 16H
            self.program.auto.append("03:00\t07:00")
            self.program.auto.append("08:00\t12:00")
            self.program.auto.append("13:00\t17:00")
            self.program.auto.append("18:00\t22:00")
        elif temperature < 31.0:
            # [29-31[ : 19H
            self.program.auto.append("00:00\t12:00")
            self.program.auto.append("12:30\t23:30")
            self.program.auto.append("00:00\t12:00")
            self.program.auto.append("12:30\t23:30")
            self.program.auto.append("12:30\t23:30")
        else:
            # 23H
            self.program.auto.append("00:00\t12:00")
            self.program.auto.append("12:30\t23:30")

    def __backup(self, tickLimit):
        if self.autoSaveTick == tickLimit:
            for section in self.database.sections():
                for key, value in self.database.items(section):
                    self.database.set(section, key, self.__dict__[section].__dict__[key])
            self.database.backup()
            self.autoSaveTick = 0
            # All seems to be OK, we can remove the previous version
            backup = os.path.join(path, os.pardir, "PoolSurvey.bak")
            if os.path.exists(backup):
                os.system("rm -frd %s" % backup)
        self.autoSaveTick += 1

    def __refresh(self):
        self.temp.current = self.info.getTemperature()
        if self.temp.current > self.temp.max:
            self.temp.max = self.temp.current
        # Once by day
        if self.__today != date.today().day:
            self.__today = date.today().day
            # Pressure checking
            with self.__i2c.lock:
                self.pressure.current = self.info.getPressure()
            if self.pressure.current > self.pressure.critical:
                self.newDefault(self.DEFAULT_IMPORTANT, "Pressure too high. Clean filters urgently!")
            elif self.pressure.current > self.pressure.max:
                self.newDefault(self.DEFAULT_INFORMATION, "Pressure is high. Think to clean filters")
            # Pump auto-schedulling
            self.__computePumpScheduling(self.temp.max)
            self.temp.max = -50.0
        if self.updatePumpState():
            with self.__i2c.lock:
                self.ph.current = self.ph.offset + self.info.getPHLevel(self.temp.current)
                self.orp.current = self.orp.offset + self.info.getORPLevel()
            self.updateRobotState()
            self.updatePHState()
            self.updateORPState()
        self.updateWaterFillingState()
        # Saved each hour
        self.__backup(self.DATABASE_SAVE_TICK)
        if self.lcdLightTimer > 0:
            self.lcdLightTimer -= 1
            if self.lcdLightTimer <= 0:
                self.lcd.light(False)
            elif self.lcdMenu == "default":
                self.lcdDisplay()

    def run(self):
        while not self.__event.is_set():
            self.TAG(self.DEBUG, "%ds Tick" % self.REFRESH_TICK)
            self.__refresh()
            self.TRACE(self.DEBUG, str(self))
            self.__event.wait(self.REFRESH_TICK)
        self.TRACE(Debug.DETAIL, "Manager thread is stopped\n")

    def start(self):
        super(Manager, self).start()
        self.TRACE(Debug.DETAIL, "Manager thread is started\n")

    def stop(self):
        self.__event.set()

    def newDefault(self, level, message):
        self.TRACE(Debug.DETAIL, "Add default \"%s\" in the defaults list\n", message)
        today = date.today()
        default = "%s %s %s %d %s" % (date.strftime(today, "%d %B %Y"), date.strftime(today, "%A"), time.strftime("%H:%M"), level, message)
        self.state.defaults.append(default)
        if level == self.DEFAULT_CRITICAL and self.state.pump:
            self.stopPump("Emergency: %s" % message)

    def startPump(self, reason=""):
        self.TRACE(Debug.DETAIL, "Pump is started: %s\n", reason)
        self.state.pump = self.cmd.pump = True
        time.sleep(2) # TODO 2 a voir a l'usage
        if not self.info.getLiquidMoveState():
            self.newDefault(self.DEFAULT_CRITICAL, "Water seems to be blocked! Check valves state!")

    def stopPump(self, reason, delay_s=0):
        self.state.robot = self.cmd.robot = False
        self.TRACE(Debug.DETAIL, "PH injection is stopped: %s\n", reason)
        self.state.ph = self.cmd.ph(0)
        self.TRACE(Debug.DETAIL, "Chlore injection is stopped: %s\n", reason)
        self.state.orp = self.cmd.cl(0)
        if delay_s == 0:
            # Emergency stop! We must to prevent the pump to restart
            self.mode.pump = self.OFF_STATE
        else:
            time.sleep(delay_s) # TODO 2 a voir a l'usage
        self.TRACE(Debug.DETAIL, "Pump is stopped: %s (delay=%ds)\n", reason, delay_s)
        self.state.pump = self.cmd.pump = False

    def appendProgram(self, kind, entry):
        self.program.__dict__[kind].append(entry)
        # Check coherency
        prev = "00:00"
        pumps = list()
        for start, stop in [x.split() for x in self.program.__dict__[kind]]:
            if stop > start:
                if start > prev:
                    pumps.append("%s\t%s" % (start, stop))
                    prev = stop
                elif stop > prev:
                    start, prev = pumps[-1].split()
                    pumps[-1] = "%s\t%s" % (start, stop)
                    prev = stop
        self.program.__dict__[kind] = pumps

    def updatePumpState(self):
        if self.mode.pump == self.OFF_STATE:
            if self.state.pump:
                self.stopPump("Forced to OFF", 2)
        elif self.mode.pump == self.ON_STATE:
            if not self.state.pump:
                self.startPump("Forced to ON")
        else:
            if self.mode.program:
                pumps = self.program.auto
            else:
                pumps = self.program.pumps
            pump = False
            if len(pumps) > 0:
                now = time.strftime("%H:%M")
                for start, stop in [x.split() for x in pumps]:
                    if start <= now < stop:
                        pump = True
            if not self.cmd.pump ^ pump:
                if pump:
                    self.startPump("Automatic mode")
                else:
                    self.stopPump("Automatic mode", 2)
        return self.cmd.pump

    def updateRobotState(self):
        if self.mode.robot == self.OFF_STATE:
            if self.state.robot:
                self.TRACE(Debug.DETAIL, "Robot is stopped: Forced to OFF\n")
                self.cmd.robot = False
        elif self.mode.robot == self.ON_STATE:
            if not self.state.robot:
                self.TRACE(Debug.DETAIL, "Robot is started: Forced to ON\n")
                self.cmd.robot = True
        else:
            robot = False
            now = time.strftime("%H:%M")
            if self.program.robots:
                for start, stop in [x.split() for x in self.program.robots]:
                    if start <= now < stop:
                        robot = True
            if not self.cmd.robot ^ robot:
                self.TRACE(Debug.DETAIL, "Robot is %s: Automatic mode\n" % ["stopped", "started"][robot])
                self.cmd.robot = robot
        self.state.robot = self.cmd.robot

    def updatePHState(self):
        if self.mode.ph == self.OFF_STATE:
            if self.state.ph:
                self.TRACE(Debug.DETAIL, "PH injection is stopped: Forced to OFF\n")
                self.state.ph = self.cmd.ph(0)
        elif self.mode.ph == self.ON_STATE:
            if not self.state.ph:
                self.TRACE(Debug.DETAIL, "PH injection is started: Forced to ON (speed=%d%)\n", self.PH_PWM_PERCENT)
                self.state.ph = self.cmd.ph(self.PH_PWM_PERCENT) # TODO 2 regler une vitesse pas trop rapide
        else:
            # TODO 1 les delay 360 cidessous devraient evoluer selon la variation effective du ph...
            # ou le PWM ...
            if self.ph.delay > 0:
                self.ph.delay -= 1
                if self.ph.delay <= 0 and self.state.ph:
                    self.TRACE(Debug.DETAIL, "PH injection is stopped: Automatic mode\n")
                    self.ph.delay =  360 / self.REFRESH_TICK # Delay inter-injection
                    self.state.ph = self.cmd.ph(0)
            else:
                if self.ph.current > self.ph.idle:
                    self.TRACE(Debug.DETAIL, "PH injection is started: Automatic mode (speed=%d%)\n", self.PH_PWM_PERCENT)
                    self.state.ph = self.cmd.ph(self.PH_PWM_PERCENT)
                    self.ph.delay =  360 / self.REFRESH_TICK # Delay injection
            if self.ph.current < self.ph.min:
                self.newDefault(self.DEFAULT_IMPORTANT, "PH level too low!")
                self.TRACE(Debug.DETAIL, "PH injection is stopped: PH level too low\n")
                self.state.ph = self.cmd.ph(0)
            elif self.ph.current > self.ph.max:
                self.newDefault(self.DEFAULT_IMPORTANT, "PH level too high!")

    def updateORPState(self):
        if self.mode.orp == self.OFF_STATE:
            if self.state.orp:
                self.TRACE(Debug.DETAIL, "Chlore injection is stopped: Forced to OFF\n")
                self.state.orp = self.cmd.cl(0)
        elif self.mode.orp == self.ON_STATE:
            if not self.state.orp:
                self.TRACE(Debug.DETAIL, "Chlore injection is started: Forced to ON (speed=%d%)\n", self.CL_PWM_PERCENT)
                self.state.orp = self.cmd.cl(self.CL_PWM_PERCENT) # TODO 2 regler une vitesse pas trop rapide
        else:
            if self.orp.delay > 0:
                self.orp.delay -= 1
                if self.orp.delay <= 0 and self.state.orp:
                    self.orp.delay =  360 / self.REFRESH_TICK # Delay inter-injection
                    self.TRACE(Debug.DETAIL, "Chlore injection is stopped: Automatic mode\n")
                    self.state.orp = self.cmd.cl(0)
            else:
                if self.orp.current < self.orp.idle:
                    self.TRACE(Debug.DETAIL, "Chlore injection is started: Automatic mode (speed=%d%)\n", self.CL_PWM_PERCENT)
                    self.state.orp = self.cmd.cl(self.CL_PWM_PERCENT)
                    # TODO 1 les delay 360 cidessous devraient evoluer selon la variation effective de l'orp...
                    # ou le PWM ...
                    self.orp.delay =  360 / self.REFRESH_TICK # Delay injection
            if self.orp.current < self.orp.min:
                self.newDefault(self.DEFAULT_IMPORTANT, "ORP level too low!")
            elif self.orp.current > self.orp.max:
                self.newDefault(self.DEFAULT_IMPORTANT, "ORP level too high!")
                self.TRACE(Debug.DETAIL, "Chlore injection is stopped: ORP level too high\n")
                self.state.orp = self.cmd.cl(0)

    def updateWaterFillingState(self):
        if self.mode.filling == self.OFF_STATE:
            if self.state.filling:
                self.TRACE(Debug.DETAIL, "Filling pool is stopped: Forced to OFF\n")
                self.cmd.fill = False
        elif self.mode.filling == self.ON_STATE:
            if not self.state.filling:
                self.TRACE(Debug.DETAIL, "Filling pool is started: Forced to ON\n")
                self.cmd.fill = True
        else:
            now = time.strftime("%H:%M")
            if now > "21:00" or now < "07:00": # Start only when no one is in the pool
                if self.cmd.fill == self.info.getLiquidLevelState():
                    self.TRACE(self.DETAIL, "Filling pool is %: Water level detection", ["started", "stopped"][self.cmd.fill])
                    self.cmd.fill = not self.cmd.fill
        self.state.filling = self.cmd.fill

    def light(self, value=None):
        if not value is None:
            self.cmd.light = bool(value)
            self.state.light = self.cmd.light
            self.TRACE(Debug.DETAIL, "Lights: %s\n", ["ON", "OFF"][self.state.light])
        return self.cmd.light

if __name__ == '__main__':
    try:
        manager = Manager()
        manager.start()
    except KeyboardInterrupt:
        manager.stop()

# TODO 2 mettre en parametre de server.py le path /media/pi/data
