#!/usr/bin/python
import threading

class Statistic(list):
    def __init__(self, debug, pump, robot, redox, ph, temperature, pressure, waterlevel):
        self.__lock = threading.RLock()
        self.__debug = debug
        self.__pump = pump
        self.__robot = robot
        self.__redox = redox
        self.__ph = ph
        self.__temperature = temperature
        self.__pressure = pressure
        self.__waterlevel = waterlevel

    def __str__(self):
        text = ""
        with self.__lock:
            for index in range(len(self)):
                text += "Day %d:\n" % (index + 1 - len(self))
                for key, values in self[index].items():
                    text += "\t%s:\n\t[" % key
                    for value in values:
                        text += "%s," % value
                    text += "[%s,]\n"
        return text

    def __del__(self):
        self.__debug.TRACE(self.__debug.DETAIL, "Statistics:\n%s", self)

    def onceByDay(self):
        with self.__lock:
            self.append(dict())
            if self.__pressure.isReadMode():
                self[-1]["pressure::value"] = list()
            if self.__ph.isReadMode():
                self[-1]["ph::value"] = list()
            if self.__redox.isReadMode():
                self[-1]["redox::value"] = list()
            if self.__temperature.isReadMode():
                self[-1]["temperature::value"] = list()
            if self.__pump.isNormalMode():
                self[-1]["pump::state"] = list()
            if self.__ph.isNormalMode():
                self[-1]["ph::state"] = list()
            if self.__redox.isNormalMode():
                self[-1]["redox::state"] = list()
            if len(self) > 7:
                self.pop(0)

    def save(self, filename="statistics.txt"):
        handle = open(filename, "wt+")
        handle.write("Statistics:\n%s" % self)
        handle.close()

    def update(self):
        with self.__lock:
            if self.__pressure.isReadMode():
                self[-1]["pressure::value"].append(self.__pressure.read())
            if self.__ph.isReadMode():
                self[-1]["ph::value"].append(self.__ph.read())
            if self.__redox.isReadMode():
                self[-1]["redox::value"].append(self.__redox.read())
            if self.__temperature.isReadMode():
                self[-1]["temperature::value"].append(self.__temperature.read())
            if self.__pump.isNormalMode():
                self[-1]["pump::state"].append(self.__pump.isSwitchOn())
            if self.__ph.isNormalMode():
                self[-1]["ph::state"].append(self.__ph.isSwitchOn())
            if self.__redox.isNormalMode():
                self[-1]["redox::state"].append(self.__redox.isSwitchOn())
