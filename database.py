#!/usr/bin/python
import sys, os, ConfigParser, threading, types
sys.path.append(os.path.join(os.path.dirname(__file__), "lib"))

from helper import Debug

class Database(Debug, ConfigParser.ConfigParser):
    SECTIONS = {"mode":{"pump":2,"robot":2,"ph":2,"orp":2,"filling":2,"program":True},
                "ph":{"current":0.0,"offset":0.0,"min":7.0,"idle":7.2,"max":8.0,"delay":0,"lbound":0.0,"ubound":14.0},
                "orp":{"current":0,"offset":0,"min":350,"idle":650,"max":950,"delay":0,"lbound":-2000,"ubound":2000},
                "temp":{"current":0.0,"winter":10.0,"max":-50.0},
                "pressure":{"current":0.0,"max":1.3,"critical":1.5},
                "state":{"pump":False,"robot":False,"ph":False,"orp":False,"filling":False,"light":False,"open":False,"defaults":[]},
                "program":{"pumps":[],"robots":[]}}
    def __init__(self, filename="database.ini"):
        Debug.__init__(self)
        self.lock = threading.RLock()
        ConfigParser.ConfigParser.__init__(self)
        test = os.path.join("media", "pi", "data")
        if os.path.isdir(os.path.join("media", "pi", "data")):
            self.__filename = os.path.join("media", "pi", "data", filename)
        else:
            self.__filename = os.path.join(os.path.dirname(__file__), filename)
        if not os.path.exists(self.__filename) and not os.path.exists(self.__filename + ".new"):
            for section in self.SECTIONS:
                self.add_section(section)
                for key in self.SECTIONS[section]:
                    super(Database, self).set(section, key, str(self.SECTIONS[section][key]))
            self.backup()
        else:
            if os.path.exists(self.__filename + ".new"):
                os.rename(self.__filename + ".new", self.__filename)
            self.lock.acquire()
            self.read(self.__filename)
            self.lock.release()

    def __str__(self):
        return self.html("\n", "\n")

    def html(self, subeol="<br>", eol="<br>"):
        text = ""
        for section in self.sections():
            text += "%s[%s]%s" % (eol, section, eol)
            for key, value in self.items(section):
                text += "%s = %s%s" % (key, value, subeol)
        return text

    def __check(self, section, key, value=None):
        # Check that couple of section/key exists
        if section not in self.sections():
            raise ValueError, "Unexpected section \"%s\" not in %s" % (section, self.sections())
        elif key not in self.options(section):
            raise ValueError, "Unexpected key \"%s::%s\" not in %s" % (section, key, self.options(section))
        if not value is None:
            # Check value type
            if type(value) != type(self.SECTIONS[section][key]):
                raise ValueError, "Unexpected value %s of \"%s::%s\": %s" % (type(value), section, key, type(self.SECTIONS[section][key]))

    def clear(self, section, key):
        self.lock.acquire()
        self.__check(section, key)
        super(Database, self).set(section, key, str(type(self.SECTIONS[section][key])()))
        self.lock.release()

    def get(self, section, key):
        self.lock.acquire()
        self.__check(section, key)
        if type(self.SECTIONS[section][key]) in types.StringTypes:
            value = super(Database, self).get(section, key)
        else:
            value = eval(super(Database, self).get(section, key))
        self.lock.release()
        return value

    def set(self, section, key, value):
        self.lock.acquire()
        self.__check(section, key, value)
        super(Database, self).set(section, key, str(value))
        self.lock.release()

    def backup(self):
        self.lock.acquire()
        handle = open(self.__filename + ".new",'w')
        self.write(handle)
        handle.close()
        if os.path.isfile(self.__filename):
            os.remove(self.__filename)
        os.rename(self.__filename + ".new", self.__filename)
        self.lock.release()

if __name__ == '__main__':
    try:
        database = Database()
        print database
        database.set("ph", "current", 7.3)
        print database.get("ph", "current")
        database.clear("state", "defaults")
        print database.get("state", "defaults")
        database.set("state", "pump", True)
        print database.get("state", "pump")
        print database
        assert type(database.get("program", "pumps")) == type([]), "error on list type"
        database.set("state", "pumps", False)
    except Exception as error:
        database.backup()
        print error
