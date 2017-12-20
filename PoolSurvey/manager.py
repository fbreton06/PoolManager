#!/usr/bin/python
import os, time, sys, types, threading
from datetime import date
sys.path.append(os.path.join(os.path.dirname(__file__), os.pardir, "lib"))

from helper import Debug
from hardware import Information, Command
from database import Database

import RPi.GPIO as GPIO

try:
    from tmp import tmpClass as MyClass
except:
    class MyClass:
        def alert(self, message):
            pass

class Manager(MyClass, Debug, threading.Thread):
    class Fake: pass
    DEFAULT_CRITICAL = 1
    DEFAULT_IMPORTANT = 2
    DEFAULT_INFORMATION = 3
    FILLING_DEBOUNCE_TICK = 30
    DATABASE_SAVE_TICK = 360 # 1h
    LCD_LIGHT_TICK = 6 # 1mn
    REFRESH_TICK = 10 # in second
    OFF_STATE = 0
    ON_STATE = 1
    AUTO_STATE = 2
    SIMU = False
    def __init__(self):
        Debug.__init__(self, Debug.ERROR)
        threading.Thread.__init__(self)
        self.__event = threading.Event()
        GPIO.setmode(GPIO.BCM)
        self.info = Information(self.__waterMoveDetect, self.__rotaryMove, self.__validButton)
        self.info.debug_level = self.debug_level
        self.cmd = Command()
        self.cmd.debug_level = self.debug_level
        self.lcd = LCD(0x27)
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
        if menu != None:
            self.lcdMenu = menu
        self.lcd.clear()
        if self.lcdMenu == "default":
            self.lcd.write(0, 0, "PH=%.1f" % self.ph.current)
            self.lcd.write(0, 8, "ORP=%.1fmv" % self.orp.current)
        if self.lcdMenu == "default_sub":
            self.lcd.write(0, 0, "PH=%.1f" % self.ph.current)
            self.lcd.write(0, 8, "ORP=%.1fmv" % self.orp.current)
            if self.lcdValue < len(self.state.defaults):
                self.lcd.write(1, 0, "Default=%s" % self.state.defaults[self.lcdValue].split("_")[-1])
            else:
                self.lcd.write(1, 0, "Retour")
        elif self.lcdMenu == "ph":
            self.lcd.write(0, 0, "PH Calibration")
            self.lcd.write(1, 0, "Enter")
        elif self.lcdMenu == "ph_sub":
            self.lcd.write(0, 0, "PH Calibration")
            self.lcd.write(1, 0, "PH Etalon=%.1f" % self.lcdValue)
        elif self.lcdMenu == "orp":
            self.lcd.write(0, 0, "ORP Calibration")
            self.lcd.write(1, 0, "Enter")
        elif self.lcdMenu == "orp_sub":
            self.lcd.write(0, 0, "ORP Calibration")
            self.lcd.write(1, 0, "ORP Etalon=%.1f" % self.lcdValue)
# TODO 2 pouvoir forcer la pompe sur place...
#        elif self.lcdMenu == "Circulation":
#            self.lcd.write(0, 0, "Pompe principale")
#            self.lcd.write(1, 0, "Etat=%s" % ["Arret", "Marche"][self.state.pump])

# TODO 1 ajouter lcd + fonction etalonnage des sondes
# TODO 1 ajouter un bouton reset defaut? ou a faire sur place (LCD)

    def __validButton(self, pin, state):
        if state == 0:
            if not self.lcd.light():
                self.lcd.light(True)
                self.lcdLightTimer = self.LCD_LIGHT_TICK
                self.lcdDisplay("default")
            else:
                if self.lcdMenu == "default":
                    self.lcdValue = 0
                    self.lcdDisplay("default_sub")
                elif self.lcdMenu == "default_sub":
                    if self.lcdValue >= len(self.state.defaults):
                        self.lcdDisplay("default")
                    else:
                        self.state.defaults.remove(self.lcdValue)
                        if self.lcdValue >= len(self.state.defaults):
                            self.lcdValue -= 1
                        if self.lcdValue < 0:
                            self.lcdDisplay("default")
                        else:
                            self.lcdDisplay()
                elif self.lcdMenu == "ph":
                    self.lcdValue = 7.0
                    self.lcdDisplay("ph_sub")
                elif self.lcdMenu == "ph_sub":
                    pass # demmarage de la procedure (attend 1mn et mesure et enregistre l'offset (dans la class info) qui doit etre appliquer apres
                elif self.lcdMenu == "orp":
                    self.lcdValue = 650
                    self.lcdDisplay("orp_sub")
                elif self.lcdMenu == "orp_sub":
                    pass # demmarage de la procedure (attend 1mn et mesure et enregistre l'offset (dans la class info) qui doit etre appliquer apres
                elif self.lcdMenu == "pump":
                    self.lcdValue = self.mode.pump
                    self.lcdDisplay("pump_sub")
                elif self.lcdMenu == "pump_sub":
                    self.mode.pump = self.lcdValue
                    self.lcdDisplay("pump")

    def __rotaryMove(self, position):
        if not self.lcd.light():
            self.lcd.light(True)
            self.lcdLightTimer = self.LCD_LIGHT_TICK
            self.lcdDisplay("default")
        else:
            if self.lcdMenu == "default":
                if position > 0:
                    self.lcdDisplay("ph")
            elif self.lcdMenu == "default_sub":
                if self.lcdValue >= len(self.state.defaults):
                    self.lcdDisplay("default")
                else:
                    self.state.defaults.remove(self.lcdValue)
                    if self.lcdValue >= len(self.state.defaults):
                        self.lcdValue -= 1
                    if self.lcdValue < 0:
                        self.lcdDisplay("default")
                    else:
                        self.lcdDisplay()
            elif self.lcdMenu == "ph":
                if position > 0:
                    self.lcdDisplay("orp")
                else:
                    self.lcdDisplay("default")
            elif self.lcdMenu == "ph_sub":
                self.lcdValue += 1# use delta
            elif self.lcdMenu == "orp":
                if position > 0:
                    self.lcdDisplay("default")
                else:
                    self.lcdDisplay("ph")
            elif self.lcdMenu == "orp_sub":
                self.lcdValue += 1# use delta

    def __waterMoveDetect(self, pin, detected):
        if not detected and self.cmd.pump:
            time.sleep(2) # TODO 2 a voir a l'usage
            if not self.info.getLiquidMoveState():
                self.newDefault(self.DEFAULT_CRITICAL, "Circulation de l'eau impossible. Verifiez les vannes!")

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
            self.newDefault(self.DEFAULT_INFORMATION, "Hivernage!")
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
            backup = os.path.join(os.path.basename(__file__), os.pardir, "PoolSurvey_bak")
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
            self.pressure.current = self.info.getPressure()
            if self.pressure.current > self.pressure.critical:
                self.newDefault(self.DEFAULT_IMPORTANT, "Pression trop importante. Nettoyez les filtres en urgence!")
            elif self.pressure.current > self.pressure.max:
                self.newDefault(self.DEFAULT_INFORMATION, "Pression trop grande. Pensez a nettoyer les filtres!")
            # Pump auto-schedulling
            self.__computePumpScheduling(self.temp.max)
            self.temp.max = -50.0
        if self.updatePumpState():
            self.ph.current = self.info.getPHLevel(self.temp.current)
            self.orp.current = self.info.getORPLevel()
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

    def run(self):
        while not self.__event.is_set():
            self.TAG(self.DEBUG, "%ds Tick" % self.REFRESH_TICK)
            self.__refresh()
            self.TRACE(self.DEBUG, str(self))
            self.__event.wait(self.REFRESH_TICK)
        self.join()

    def start(self):
        self.fillingTickTimer = -1
        super(Manager, self).start()

    def stop(self):
        self.__event.set()

    def newDefault(self, level, message):
        today = date.today()
        default = "%s %s %s %d %s" % (date.strftime(today, "%d %B %Y"), date.strftime(today, "%A"), time.strftime("%H:%M"), level, message)
        self.state.defaults.append(default)
        if level == self.DEFAULT_CRITICAL:
            self.stopPump()

    def startPump(self):
        self.state.pump = self.cmd.pump = True
        time.sleep(2) # TODO 2 a voir a l'usage
        if not self.info.getLiquidMoveState():
            self.newDefault(self.DEFAULT_CRITICAL, "Circulation de l'eau impossible. Verifiez les vannes!")

    def stopPump(self, delay_s=0):
        self.state.robot = self.cmd.robot = False
        self.cmd.ph(0)
        self.state.ph = False
        self.cmd.cl(0)
        self.state.orp = False
        if delay_s:
            time.sleep(delay_s) # TODO 2 a voir a l'usage
        else:
            # Emergency stop!
            self.mode.pump = self.OFF_STATE
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
            self.stopPump(2)
        elif self.mode.pump == self.ON_STATE:
            self.startPump()
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
                    self.startPump()
                else:
                    self.stopPump(2)
        # Done by start/stop function: self.state.pump = self.cmd.pump
        return self.cmd.pump

    def updateRobotState(self):
        if self.mode.robot == self.OFF_STATE:
            self.cmd.robot = False
        elif self.mode.robot == self.ON_STATE:
            self.cmd.robot = True
        else:
            robot = False
            now = time.strftime("%H:%M")
            if self.program.robots:
                for start, stop in [x.split() for x in self.program.robots]:
                    if start <= now < stop:
                        robot = True
            self.cmd.robot = robot
        self.state.robot = self.cmd.robot

    def updatePHState(self):
        if self.mode.ph == self.OFF_STATE:
            self.cmd.ph(0)
            self.state.ph = False
        elif self.mode.ph == self.ON_STATE:
            self.cmd.ph(50)
            self.state.ph = True
        else:
            # TODO 1 les delay 360 cidessous devraient evoluer selon la variation effective du ph...
            # ou le PWM ...
            if self.ph.delay > 0:
                self.ph.delay -= 1
                if self.ph.delay <= 0 and self.state.ph:
                    self.ph.delay =  360 / self.REFRESH_TICK # Delay inter-injection
                    self.cmd.ph(0)
                    self.state.ph = False
            else:
                if self.ph.current > self.ph.idle:
                    self.cmd.ph(50)
                    self.state.ph = True
                    self.ph.delay =  360 / self.REFRESH_TICK # Delay injection
            if self.ph.current < self.ph.min:
                self.newDefault(self.DEFAULT_IMPORTANT, "Le niveau du PH est trop bas!")
                self.cmd.ph(0)
                self.state.ph = False
            elif self.ph.current > self.ph.max:
                self.newDefault(self.DEFAULT_IMPORTANT, "Le niveau du PH est trop haut!")

    def updateORPState(self):
        if self.mode.orp == self.OFF_STATE:
            self.cmd.cl(0)
            self.state.orp = False
        elif self.mode.orp == self.ON_STATE:
            self.cmd.cl(50)
            self.state.orp = True
        else:
            if self.orp.delay > 0:
                self.orp.delay -= 1
                if self.orp.delay <= 0 and self.state.orp:
                    self.orp.delay =  360 / self.REFRESH_TICK # Delay inter-injection
                    self.cmd.cl(0)
                    self.state.orp = False
            else:
                if self.orp.current < self.orp.idle:
                    self.cmd.cl(50)
                    self.state.orp = True
                    # TODO 1 les delay 360 cidessous devraient evoluer selon la variation effective de l'orp...
                    # ou le PWM ...
                    self.orp.delay =  360 / self.REFRESH_TICK # Delay injection
            if self.orp.current < self.orp.min:
                self.newDefault(self.DEFAULT_IMPORTANT, "Le niveau de l'ORP trop bas!")
            elif self.orp.current > self.orp.max:
                self.newDefault(self.DEFAULT_IMPORTANT, "Le niveau de l'ORP trop haut!")
                self.cmd.cl(0)
                self.state.orp = False

    def updateWaterFillingState(self):
        if self.mode.filling == self.OFF_STATE:
            self.cmd.fill = False
        elif self.mode.filling == self.ON_STATE:
            self.cmd.fill = True
        else:
            if self.fillingTickTimer > 0:
                self.fillingTickTimer -= 1
            if self.cmd.fill == self.info.getLiquidLevelState():
                if self.fillingTickTimer < 0:
                    now = time.strftime("%H:%M")
                    if now > "23:00" or now < "07:00":
                        self.fillingTickTimer = self.FILLING_DEBOUNCE_TICK
                        self.TRACE(self.DEBUG, "Start water level detection debounce mechanism for %ds",
                                   self.FILLING_DEBOUNCE_TICK * self.REFRESH_TICK)
                elif self.fillingTickTimer == 0:
                    self.TRACE(self.DEBUG, "Valid water level detection")
                    self.cmd.fill = not self.cmd.fill
            else: # Low water level detected
                if self.fillingTickTimer > 0:
                    self.fillingTickTimer = -1
                    self.TRACE(self.DEBUG, "Cancel water level detection debounce mechanism")
        self.state.filling = self.cmd.fill

    def light(self, value=None):
        if not value is None:
            self.cmd.light = bool(value)
            self.state.light = self.cmd.light
        return self.cmd.light

if __name__ == '__main__':
    try:
        manager = Manager()
        manager.start()
    except KeyboardInterrupt:
        manager.stop()

# TODO 2 mettre en parametre de server.py le path /media/pi/data
# TODO 2 ajouter la liste des numero de mobile dans la data base + setting web
