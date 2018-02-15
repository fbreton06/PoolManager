#!/usr/bin/python
import os, time, sys, types, threading
sys.path.append("lib")
from datetime import date

from helper import Debug

verbosity = Debug.ERROR
#verbosity = Debug.DEBUG
#verbosity = Debug.DUMP

from helper import Debug
from hardware import Information, Command, Rotary
from database import Database
import button, smbus

from lcd1602 import LCD
import RPi.GPIO as GPIO

try:
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

class Default(Debug, dict):
    CRITICAL = 0
    IMPORTANT = 1
    INFORMATION = 2
    LEVELS = ("CRITICAL", "IMPORTANT", "INFORMATION")
    def __init__(self, emergencyCb):
        Debug.__init__(self)
        self.debug_level = verbosity
        self.__critical = 0
        self.__emergencyCb = emergencyCb
        self.__oldState = None
        self.lock = threading.RLock()

    def add(self, severity, kind, message):
        assert kind != "", "Unsupport empty  kind"
        with self.lock:
            self.TRACE(Debug.DETAIL, "Add default %s%s [%s]\n", kind, message, self.LEVELS[severity])
            today = date.today()
            timeStamp = "%s %s %s" % (date.strftime(today, "%d %B %Y"), date.strftime(today, "%A"), time.strftime("%H:%M"))
            if self.has_key(kind):
                if severity == self.CRITICAL and self[kind][0] != self.CRITICAL:
                    self.__critical += 1
                # Update it
                self[kind] = (severity, timeStamp, message)
            else:
                if severity == self.CRITICAL:
                    self.__critical += 1
                # Create new one
                self[kind] = (severity, timeStamp, message)
            if self[kind][0] == self.CRITICAL:
                self.__oldState = self.__emergencyCb(kind, message)

    def remove(self, kind):
        oldState = None
        with self.lock:
            if self.has_key(kind):
                if self[kind][0] == self.CRITICAL and self.__critical > 0:
                    self.__critical -= 1
                if self.__critical == 0:
                    oldState = self.__oldState
        return oldState

    def getKindFromIndex(self, index):
        kind = ""
        with self.lock:
            if index >= 0 and index < len(self):
                kind = self.keys()[index]
        return kind

    def getMessage(self, kind_or_index):
        message = "Message %s not found!" % kind
        with self.lock:
            if self.has_key(kind):
                message = self[kind][-1]
        return message

class Manager(MyClass, Debug):
    class Fake: pass
    ONCE_BY_HOUR_TICK = 360 # 1h
    LCD_LIGHT_TICK = 30 # 5mn
    REFRESH_TICK = 10 # in second
    OFF_STATE = 0
    ON_STATE = 1
    AUTO_STATE = 2
    PUMP_MODES = ("OFF", "ON", "AUTO")
    ROTARY_EVENT_GPIO_PIN = 22
    ROTARY_SWITCH_GPIO_PIN = 24
    PH_PWM_PERCENT = 10
    CL_PWM_PERCENT = 10
    def __init__(self, refPath, dataPath, dbFilename):
        Debug.__init__(self, verbosity)
        self.refPath = refPath
        GPIO.cleanup()
        GPIO.setmode(GPIO.BCM)
        self.cmd = Command()
        self.cmd.debug_level = verbosity
        self.info = Information(self.__waterMoveDetect)
        self.info.debug_level = verbosity
        self.__i2c = I2C(2)
        self.__rotary = Rotary(False, self.ROTARY_EVENT_GPIO_PIN, self.__rotaryMove, bus=self.__i2c)
        self.__button = button.Button(self.ROTARY_SWITCH_GPIO_PIN, 1000, self.__validButton, GPIO.RISING)        
        self.lcd = LCD(0x27, bus=self.__i2c)
        self.lcdLightTimer = 0
        self.database = Database(dataPath, dbFilename)
        self.database.debug_level = verbosity
        for section in self.database.sections():
            assert not self.__dict__.has_key(section), "Member name \"%s\" conflict!" % section
            self.__dict__[section] = self.Fake()
            for key, value in self.database.items(section):
                self.__dict__[section].__dict__[key] = self.database.get(section, key)
        self.autoSaveTick = 0
        self.__today = date.today().day - 1
        self.default = Default(self.__emergency)
        self.lcdMenu = "default"
        self.TRACE(Debug.DEBUG, "Initialisation done (Verbosity level: %s)\n", self.getVerbosity())

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
            kind = self.default.getKindFromIndex(self.lcdValue)
            if kind:
                self.lcd.write(1, 0, "Default=%s" % self.default.getMessage(kind))
            else:
                self.lcd.write(1, 0, "Back")
                self.lcdValue = -1
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
                    self.lcdValue = -1
                    if len(self.default) > 0:
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
                    if self.lcdValue >= 0:
                        oldState = self.default.remove(self.default.getKindFromIndex(self.lcdValue))
                        if oldState != None:
                            if oldState:
                                self.mode.pump = self.AUTO_STATE
                                self.startPump("Go back from emergency state")
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
                self.lcdValue = (self.lcdValue + [-1, 1][delta > 0]) % len(self.default)
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
            self.default.add(self.default.CRITICAL, "WaterFlow", "Seems to be blocked! Check valves state!")

    def __computSchedulingTime(self, startHour, startMn, duration):
        start = startHour * 60 + startMn
        stop = start + duration * 60
        stopHour = int(stop / 60)
        stopMn = int(stop - stopHour * 60)
        return "%02d:%02d\t%02d:%02d" % (startHour, startMn, stopHour, stopMn)

    def __computePumpScheduling(self, temperature):
        programs = list()
        if temperature < self.temp.winter:
            # ...-Winter[ : 2H
            self.default.add(self.default.INFORMATION, "Wintering", "Enter")
            programs.append("12:00\t14:00")
        elif temperature < 12.0:
            # [Winter-12[ : 4H
            programs.append("11:00\t15:00")
        elif temperature < 16.0:
            # [12-16[ : 6H
            programs.append("11:00\t14:00")
            programs.append("15:00\t18:00")
        elif temperature < 20.0:
            # [16-20[ : 8H
            programs.append("09:30\t:13:30")
            programs.append("14:30\t:18:30")
        elif temperature < 27.0:
            # [20-27[ : temp/2 (10H to 13.5H)
            duration = float(temperature) / 2
            if duration <= 12.0:
                programs.append(self.__computSchedulingTime(6, 0, duration / 3))
                programs.append(self.__computSchedulingTime(11, 0, duration / 3))
                programs.append(self.__computSchedulingTime(16, 0, duration / 3))
            else:
                programs.append(self.__computSchedulingTime(3, 0, duration / 4))
                programs.append(self.__computSchedulingTime(8, 0, duration / 4))
                programs.append(self.__computSchedulingTime(13, 0, duration / 4))
                programs.append(self.__computSchedulingTime(18, 0, duration / 4))
        elif temperature < 29.0:
            # [27-29[ : 16H
            programs.append("03:00\t07:00")
            programs.append("08:00\t12:00")
            programs.append("13:00\t17:00")
            programs.append("18:00\t22:00")
        elif temperature < 31.0:
            # [29-31[ : 19H
            programs.append("00:00\t12:00")
            programs.append("12:30\t23:30")
            programs.append("00:00\t12:00")
            programs.append("12:30\t23:30")
            programs.append("12:30\t23:30")
        else:
            # 23H
            programs.append("00:00\t12:00")
            programs.append("12:30\t23:30")
        self.TRACE(Debug.DETAIL, "Programmation at %.1fC\n\tStart\tStop\n\tHH:MN\tHH:MN\n", temperature)
        for program in programs:
            self.TRACE(Debug.DETAIL, "\t%s\n", program)
        return programs

    def __emergency(self, kind, message):
        oldState = self.state.pump
        if oldState:
            self.stopPump("Emergency: %s%s" % (kind, message))
        return oldState

    def __databaseSave(self):
        for section in self.database.sections():
            for key, value in self.database.items(section):
                self.database.set(section, key, self.__dict__[section].__dict__[key])
        self.database.backup()

    def __onceByHour(self, tickLimit):
        if self.autoSaveTick == tickLimit:
            self.autoSaveTick = 0
            self.__databaseSave()
            # All seems to be OK, we can remove the previous version
            backup = os.path.join(self.refPath, "PoolSurvey_bak")
            if os.path.exists(backup):
                os.system("rm -frd %s" % backup)
        self.autoSaveTick += 1

    def run(self):
        self.TRACE(Debug.DEBUG, "Manager is started\n")        
        self.__running = True
        while self.__running:
            self.TAG(self.DETAIL, "%ds Tick" % self.REFRESH_TICK)
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
                    self.default.add(self.default.IMPORTANT, "Pressure", "Too high! Clean filters urgently!")
                elif self.pressure.current > self.pressure.max:
                    self.default.add(self.default.INFORMATION, "Pressure", "Is high. Think to clean filters")
                # Pump auto-schedulling
                self.program.auto = self.__computePumpScheduling(self.temp.max)
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
            self.__onceByHour(self.ONCE_BY_HOUR_TICK)
            if self.lcdLightTimer > 0:
                self.lcdLightTimer -= 1
                if self.lcdLightTimer <= 0:
                    self.lcd.light(False)
                elif self.lcdMenu == "default":
                    self.lcdDisplay()
            time.sleep(self.REFRESH_TICK)
            raise ValueError, "Faked crash"
        self.TRACE(Debug.DEBUG, "Manager is stopped\n")
        
    def stop(self):
        self.__running = False

    def startPump(self, reason=""):
        self.TRACE(Debug.DETAIL, "Pump is started: %s\n", reason)
        self.state.pump = self.cmd.pump = True
        time.sleep(2) # TODO 2 a voir a l'usage
        if not self.info.getLiquidMoveState():
            self.default.add(self.default.CRITICAL, "WaterFlow", "Seems to be blocked! Check valves state!")

    def stopPump(self, reason, delay_s=0):
        self.TRACE(Debug.DETAIL, "Robot is stopped: %s\n", reason)
        self.state.robot = self.cmd.robot = False
        self.TRACE(Debug.DETAIL, "PH injection is stopped: %s\n", reason)
        self.state.ph = self.cmd.ph(0)
        self.TRACE(Debug.DETAIL, "Chlore injection is stopped: %s\n", reason)
        self.state.orp = self.cmd.cl(0)
        if delay_s == 0:
            self.__databaseSave()
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
            if self.cmd.pump ^ pump:
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
                self.TRACE(Debug.DETAIL, "PH injection is started: Forced to ON (speed=%d)\n", self.PH_PWM_PERCENT)
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
                    self.TRACE(Debug.DETAIL, "PH injection is started: Automatic mode (speed=%d)\n", self.PH_PWM_PERCENT)
                    self.state.ph = self.cmd.ph(self.PH_PWM_PERCENT)
                    self.ph.delay =  360 / self.REFRESH_TICK # Delay injection
            if self.ph.current < self.ph.min:
                self.default.add(self.default.IMPORTANT, "PH", "Level too low!")
                self.TRACE(Debug.DETAIL, "PH injection is stopped: PH level too low\n")
                self.state.ph = self.cmd.ph(0)
            elif self.ph.current > self.ph.max:
                self.default.add(self.default.IMPORTANT, "PH","Level too high!")

    def updateORPState(self):
        if self.mode.orp == self.OFF_STATE:
            if self.state.orp:
                self.TRACE(Debug.DETAIL, "Chlore injection is stopped: Forced to OFF\n")
                self.state.orp = self.cmd.cl(0)
        elif self.mode.orp == self.ON_STATE:
            if not self.state.orp:
                self.TRACE(Debug.DETAIL, "Chlore injection is started: Forced to ON (speed=%d)\n", self.CL_PWM_PERCENT)
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
                    self.TRACE(Debug.DETAIL, "Chlore injection is started: Automatic mode (speed=%d)\n", self.CL_PWM_PERCENT)
                    self.state.orp = self.cmd.cl(self.CL_PWM_PERCENT)
                    # TODO 1 les delay 360 cidessous devraient evoluer selon la variation effective de l'orp...
                    # ou le PWM ...
                    self.orp.delay =  360 / self.REFRESH_TICK # Delay injection
            if self.orp.current < self.orp.min:
                self.default.add(self.default.IMPORTANT, "ORP", "Level too low!")
            elif self.orp.current > self.orp.max:
                self.default.add(self.default.IMPORTANT, "ORP", "Level too high!")
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
                    self.cmd.fill = not self.cmd.fill
                    self.TRACE(self.DETAIL, "Filling pool is %: Water level detection", ["stopped", "started"][self.cmd.fill])
        self.state.filling = self.cmd.fill

    def light(self, value=None):
        if not value is None:
            self.cmd.light = bool(value)
            self.state.light = self.cmd.light
            self.TRACE(Debug.DETAIL, "Lights: %s\n", ["ON", "OFF"][self.state.light])
        return self.cmd.light

if __name__ == '__main__':
    try:
        manager = Manager(os.getcwd(), os.getcwd(), "db.ini")
        manager.run()
    except KeyboardInterrupt:
        manager.stop()
