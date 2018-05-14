#!/usr/bin/python
import threading, time
from datetime import date

try:
    from tmp import tmpClass as MyClass
except:
    class MyClass:
        def alert(self, message):
            pass

class Default(dict, MyClass):
    CRITICAL = 0
    IMPORTANT = 1
    INFORMATION = 2
    LEVELS = ("CRITICAL", "IMPORTANT", "INFORMATION")
    def __init__(self):
        self.critical = 0
        self.__lock = threading.RLock()

    def add(self, severity, kind, message):
        assert kind != "", "Unsupport empty  kind"
        with self.__lock:
            debug.TRACE(debug.DETAIL, "Add default %s%s [%s]\n", kind, message, self.LEVELS[severity])
            today = date.today()
            timeStamp = "%s %s %s" % (date.strftime(today, "%d %B %Y"), date.strftime(today, "%A"), time.strftime("%H:%M"))
            if self.has_key(kind):
                if severity == self.CRITICAL and self[kind][0] != self.CRITICAL:
                    self.critical += 1
                # Update it
                self[kind] = (severity, timeStamp, message)
            else:
                if severity == self.CRITICAL:
                    self.critical += 1
                # Create new one
                self[kind] = (severity, timeStamp, message)

    def remove(self, kind):
        with self.__lock:
            if self.has_key(kind):
                if self[kind][0] == self.CRITICAL and self.critical > 0:
                    self.critical -= 1

    def getKindFromIndex(self, index):
        kind = ""
        with self.__lock:
            if index >= 0 and index < len(self):
                kind = self.keys()[index]
        return kind

    def getMessage(self, kind_or_index):
        message = "Message %s not found!" % kind
        with self.__lock:
            if self.has_key(kind):
                message = self[kind][-1]
        return message

default = None
def CreateDefault():
    global default
    from debug import debug
    globals().update({"debug":debug})    
    default = Default()
    return default
