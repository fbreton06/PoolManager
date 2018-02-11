#!/usr/bin/env python
import types, syslog, traceback

class Debug(object):
    VERBOSITY = ("Unknown", "NONE", "INFO", "ERROR", "DETAIL", "DEBUG", "DUMP")
    NONE = 1
    INFO = 2
    ERROR = 3
    DETAIL = 4
    DEBUG = 5
    DUMP = 6
    def __init__(self,  level=NONE):
        assert level > 0, "Unexpected debug level value: %s" % level
        self.debug_level = level

    def getVerbosity(self):
        try:
            return self.VERBOSITY[self.debug_level]
        except:
            return self.VERBOSITY[0]

    def TAG(self, level, name, width=25, deco='#'):
        if self.debug_level >= level:
            print deco * width + ' ' + name + ' ' + deco * width

    def TRACE(self, level, *args):
        if self.debug_level >= level or level == self.ERROR or level == self.DEBUG:
            if type(args[0]) in types.StringTypes:
                message = args[0] % args[1:],
            else:
                message =  ' '.join([str(x) for x in args]),
        if self.debug_level >= level:
            print message
        if level == self.ERROR or level == self.DEBUG:
            syslog.syslog(str(message))

    def TRACEBACK(self):
        raise NotImplemented

if __name__ == "__main__":
    dbg = Debug(Debug.DETAIL)
    dbg.TAG(Debug.DEBUG, "test")
    dbg.TRACE(Debug.ERROR, "LOG error: %s\n",  "test!")
    dbg.TRACE(Debug.DETAIL, "Format %s\n",  "OK!")
    dbg.TRACE(Debug.DETAIL, 25, 12, 23.0, "\n")
    dbg.TAG(Debug.INFO, "done", 10, '!')
