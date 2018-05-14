#!/usr/bin/env python
import types, sys, syslog, traceback

class Debug(object):
    VERBOSITY = ("None", "Info", "Error", "Warning", "Detail", "Debug", "Dump", "Unknown")
    NONE = 0
    INFO = 1
    ERROR = 2
    WARNING = 3
    DETAIL = 4
    DEBUG = 5
    DUMP = 6
    UNKNOWN = 7
    def __init__(self, level):
        if level is None:
            self.__level = self.NONE
        else:
            self.__level = level

    def __str__(self):
        if self.__level >= self.NONE and self.__level < len(self.VERBOSITY):
            return self.VERBOSITY[self.__level]
        return self.VERBOSITY[-1]

    @property
    def verbosity(self):
        return self.__level

    @verbosity.setter
    def verbosity(self, level):
        if level < self.NONE or level >= len(self.VERBOSITY):
            raise ValueError, "Out of bound verbosity level value: %d" % level
        self.__level = level

    def TAG(self, level, name, width=25, deco='#'):
        if self.__level >= level:
            print deco * width + ' ' + name + ' ' + deco * width

    def TRACE(self, level, *args):
        if self.__level >= level or level == self.ERROR or level == self.DEBUG:
            if type(args[0]) in types.StringTypes:
                message = args[0] % args[1:],
            else:
                message =  ' '.join([str(x) for x in args]),
        if self.__level >= level:
            print message
        if level == self.ERROR or level == self.DEBUG:
            syslog.syslog(str(message))

    def TRACEBACK(self):
        traceback.print_exc(file=sys.stderr)
