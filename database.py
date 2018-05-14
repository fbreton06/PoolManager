#!/usr/bin/python
import os, threading, types
from ConfigParser import ConfigParser

class Database(dict):
    DEFAULT = {"mode":{"pump":1,"robot":2,"ph":3,"redox":3,"light":4,"curtain":4,"waterlevel":4,"pressure":3,"temperature":3,"panel":4},
               "ph":{"offset":0.0,"idle":7.2,"injection":0,"wait":0,"reduction":0.2},
               "redox":{"offset":0,"idle":650,"injection":0,"wait":0,"gain":25},
               "temperature":{"winter":10.0,"max":-273.0},
               "pressure":{"max":1.3,"critical":1.5}}
    def __init__(self, dataPath, dbFilename):
        self.__lock = threading.RLock()
        if not os.path.isdir(dataPath):
            raise ValueError, "Undefined path: %s" % dataPath
        self.filename = dbFilename
        self.path = dataPath
        self.__filename = os.path.join(dataPath, dbFilename)
        self.__saved = os.path.join(dataPath, "saved")
        if not os.path.exists(self.__filename) and not os.path.exists(self.__filename + ".new"):
            if os.path.isfile(self.__saved):
                os.remove(self.__saved)
            # Need to be created
            for key, value in self.DEFAULT.items():
                self[key] = dict()
                for subKey, subValue in value.items():
                    self[key][subKey] = subValue
            self.backup()
        else:
            self.restore()

    def __str__(self):
        return self.html("\n", "\n")

    def __getattr__(self, item):
        # Called only if item not already defined
        try:
            return self[item]
        except:
            raise AttributeError

    def __check(self, section, key, value=None):
        # Check that couple of section/key exists
        if not self.has_key(section):
            raise ValueError, "Unexpected section: \"%s\"" % section
        if not self[section].has_key(key):
            raise ValueError, "Unexpected key in section: \"%s::%s\"" % (section, key)
        if not value is None:
            # Check value type
            if type(value) != type(self.DEFAULT[section][key]):
                raise ValueError, "Unexpected value %s of \"%s::%s\": %s" % (type(value), section, key, type(self.DEFAULT[section][key]))

    def __save(self, section, key, value):
        if type(self.DEFAULT[section][key]) in types.StringTypes:
            self[section][key] = str(value)
        else:
            self[section][key] = type(self.DEFAULT[section][key])(value)

    def html(self, subeol="<br>", eol="<br>"):
        text = ""
        for key, value in self.items():
            text += "%s[%s]%s" % (eol, key, eol)
            for subKey, subValue in value.items():
                text += "%s = %s%s" % (subKey, subValue, subeol)
        return text

    def save(self, section, key, value):
        self.__check(section, key, value)
        self.__lock.acquire()
        self.__save(section, key, value)
        self.__lock.release()

    def restore(self):
        self.__lock.acquire()
        if os.path.isfile(self.__saved):
            if os.path.isfile(self.__filename + ".new"):
                if os.path.isfile(self.__filename):
                    os.remove(self.__filename)
                os.rename(self.__filename + ".new", self.__filename)
        else:
            if os.path.isfile(self.__filename + ".new"):
                if os.path.isfile(self.__filename):
                    os.remove(self.__filename + ".new")
                else:
                    os.rename(self.__filename + ".new", self.__filename)
        if not os.path.isfile(self.__filename):
            raise ValueError, "Database file not found: %s" % self.__filename
        config = ConfigParser()
        config.read(self.__filename)
        for section in config.sections():
            if self.DEFAULT.has_key(section):
                self[section] = dict()
                for key, value in config.items(section):
                    if self.DEFAULT[section].has_key(key):
                        self.__save(section, key, value)
        self.__lock.release()

    def backup(self):
        config = ConfigParser()
        for key, value in self.items():
            config.add_section(key)
            for subKey, subValue in value.items():
                config.set(key, subKey, subValue)
        self.__lock.acquire()
        if os.path.isfile(self.__saved):
            os.remove(self.__saved)
        handle = open(self.__filename + ".new", "w")
        config.write(handle)
        handle.close()
        handle = open(self.__saved, "w")
        handle.close()
        if os.path.isfile(self.__filename):
            os.remove(self.__filename)
        os.rename(self.__filename + ".new", self.__filename)
        self.__lock.release()
