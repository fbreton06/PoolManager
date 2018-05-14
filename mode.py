#!/usr/bin/python
class Mode:
    # Values used by the html!
    OFF_STATE = 0
    ON_STATE = 1
    AUTO_STATE = 2
    READ_STATE = 3
    NONE_STATE = 4
    MODES = ("Off", "On", "Auto", "Read", "None")
    def __init__(self, database, section):
        self.__database = database
        self.__section = section
        self.setMode(database.mode[section])

    def __str__(self):
        return self.MODES[self.__mode]

    def getDatabase(self):
        return self.__database

    def isOffMode(self):
        return self.__mode == self.OFF_STATE

    def isOnMode(self):
        return self.__mode == self.ON_STATE

    def isAutoMode(self):
        return self.__mode == self.AUTO_STATE

    def isReadMode(self):
        return self.__mode <= self.READ_STATE

    def isNoneMode(self):
        return self.__mode == self.NONE_STATE

    def getMode(self):
        return self.__mode

    def setMode(self, mode):
        if mode < 0 or mode >= len(self.MODES):
            raise ValueError, "Unbound mode value: %d" % mode
        self.__mode = mode
        self.__database.save("mode", self.__section, mode)
