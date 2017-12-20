#!/usr/bin/python
import os, time, sys, types
from datetime import date
sys.path.append(os.path.join(os.path.dirname(__file__), os.pardir, "lib"))

from helper import Debug
from database import Database

class Manager(Debug):
    class Fake: pass
    SIMU = True
    def __init__(self, tmp):
        Debug.__init__(self, self.DEBUG)
        self.database = Database()
        self.database.debug_level = self.debug_level
        for section in self.database.sections():
            assert not self.__dict__.has_key(section), "Member name \"%s\" conflict!" % section
            self.__dict__[section] = self.Fake()
            for key, value in self.database.items(section):
                self.__dict__[section].__dict__[key] = self.database.get(section, key)
        self.program.auto = list()

    def __str__(self):
        return self.html("\n", "\n")

    def html(self, subeol="<br>", eol="<br>"):
        text = ""
        for section in self.database.sections():
            text += "%s[%s]%s" % (eol, section, eol)
            for key, value in self.database.items(section):
                text += "%s = %s%s" % (key, self.__dict__[section].__dict__[key], subeol)
        return text

    def start(self):
        pass

    def stop(self):
        pass

    def appendProgram(self, kind, entry):
        pass
