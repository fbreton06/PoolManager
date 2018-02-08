#!/usr/bin/env python
# coding: utf-8 
import socket, threading, time

from helper import Debug
from serialize import *
from protocol import *

# Wireshark filter
# (tcp.srcport == 8080 or tcp.srcport == 7070 or tcp.dstport == 8080 or tcp.dstport == 7070) and tcp.flags & 0x8

verbosity = Debug.ERROR
#verbosity = Debug.DEBUG
#verbosity = Debug.DUMP

local= False
if local:
    CLIENT_ADDRESS = ("", 7070)
    SERVER_ADDRESS = ("", 8080)
else:
    CLIENT_ADDRESS = (GetIPAddress("eno1"), 7070)
    SERVER_ADDRESS = ("192.168.0.40", 8080)

__lockCb = threading.RLock()
__callbacks = dict()
__clientThread = None

def LocalAddNewCallback(cbId, cbFunction):
    global __lockCb, __callbacks, __clientThread
    if __clientThread == None:
        __clientThread = CallbackThread(*CLIENT_ADDRESS)
    with __lockCb:
        if __callbacks.has_key(cbId):
            raise ValueError, "Callback ID already used: %s" % cbId
        __callbacks[cbId] = cbFunction

def LocalRemoveCallback(cbId):
    global __lockCb, __callbacks, __clientThread
    with __lockCb:
        if __callbacks.has_key(cbId):
            __callbacks.pop(cbId)
        if len(__callbacks) == 0:
            __clientThread =__clientThread.stop()

def LocalRemoveAllCallback(idName):
    global __lockCb, __callbacks, __clientThread
    cdIds = list()
    with __lockCb:
        for cbId in __callbacks:
            if cbId.startswith(idName):
                if cbId[len(idName):].isdigit():
                    cdIds.append(cbId)
        for cbId in cdIds:
            __callbacks.pop(cbId)
        if len(cdIds) > 0 and len(__callbacks) == 0:
            __clientThread =__clientThread.stop()

def LocalGetCallback(cbId):
    global __lockCb, __callbacks
    cbFunction = None
    with __lockCb:
        if not __callbacks.has_key(cbId):
            raise ValueError, "Callback ID not found: %s" % cbId
        cbFunction = __callbacks[cbId]
    return cbFunction

class CallbackThread(threading.Thread, Debug):
    def __init__(self, address="", port=7070):
        threading.Thread.__init__(self)
        Debug.__init__(self, verbosity)
        self.__socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.__socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.__socket.settimeout(5)
        self.__socket.bind((address, port))
        self.start()

    def run(self):
        self.TRACE(Debug.DEBUG, "CallbackThread: Started\n")
        self.__active = True
        while self.__active:
            try:
                self.__socket.listen(10)
                (receiveSocket, (ip, port)) = self.__socket.accept()
                self.TRACE(Debug.DEBUG, "CallbackThread: Event received from device\n")
                ServerThread(receiveSocket)
            except socket.timeout:
                pass
            except socket.error:
                self.TRACE(Debug.DEBUG, "CallbackThread: Aborted\n")
                self.__active = False

    def stop(self):
        # Keep it forever event if there is no more callback
        #self.TRACE(Debug.DEBUG, "CallbackThread: Stopped\n")
        #self.__active = False
        #self.__socket.shutdown(socket.SHUT_WR)
        #self.__socket.close()
        #self.join()
        #return None
        return self

class ServerThread(threading.Thread, Debug):
    def __init__(self, socket):
        threading.Thread.__init__(self)
        Debug.__init__(self, verbosity)
        self.__socket = socket
        self.start()

    def __sendOK(self):
        enc = Encode(RSP_OK)
        self.__socket.send(enc.getData(SOCKET_SIZE_MAX))

    def run(self):
        self.TRACE(Debug.DEBUG, "ServerThread: Wait callback event from device\n")
        try:
            data = self.__socket.recv(SOCKET_SIZE_MAX)
            if data != "":
                dec = Decode(data)
            else:
                dec = Decode(UNKNOWN)
        except socket.error:
            dec = Decode(UNKNOWN)
        # Command
        if dec.kind == CMD_CALLBACK:
            self.TRACE(Debug.DEBUG, "ServerThread: Treat callback notification from device %d\n", dec.kind)
            if len(dec.args) > 1:
                cbId = dec.args.pop(0)
                callback = LocalGetCallback(cbId)
                if callback == None:
                    raise ValueError, "No callback for this callback ID %s" % cbId
                self.TRACE(Debug.DEBUG, "ServerThread: Callback%s callback\n", cbId)
                callback(*dec.args)
                self.__sendOK()
                self.TRACE(Debug.DEBUG, "ServerThread: Callback %s response sent\n", cbId)
            else:
                raise ValueError, "Unexpected number of arguments: %s" % dec.args
        else:
            raise NotImplemented
        self.__socket.close()

class RequestThread(threading.Thread, Debug):
    def __init__(self, address="", port=8080):
        threading.Thread.__init__(self)
        Debug.__init__(self, verbosity)
        self.__event = threading.Event()
        self.__socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.__socket.connect((address, port))

    def send(self, data):
        self.__result = None
        self.TRACE(Debug.DUMP, "RequestThread: SEND %s\n", " ".join(["%02X " % ord(c) for c in data]))
        self.__socket.send(data)
        self.TRACE(Debug.DEBUG, "RequestThread: Request to device sent (%d)\n", id(data))
        self.start()
        self.__event.wait(SOCKET_TIMEOUT_S)
        self.TRACE(Debug.DEBUG, "RequestThread: Request confirmed (%d)\n", id(data))
        self.__socket.close()
        return self.__result

    def run(self):
        self.TRACE(Debug.DEBUG, "RequestThread: Wait request response from device\n")
        try:
            data = self.__socket.recv(SOCKET_SIZE_MAX)
            if data != "":
                self.TRACE(Debug.DUMP, "RequestThread: RECEIVE %s\n", " ".join(["%02X" % ord(c) for c in data]))
                dec = Decode(data)
            else:
                dec = Decode(UNKNOWN)
        except socket.error:
            dec = Decode(UNKNOWN)
        if dec.kind == RSP_ERR:
            if len(dec.args) > 0:
                raise ValueError, str(dec.args[0])
            raise ValueError, "Unexpected error!"
        elif dec.kind == RSP_HANDLE:
            if len(dec.args) != 1:
                raise ValueError, "Unexpected number of arguments: %s" % dec.args
            self.__result = dec.args[0]
        elif dec.kind == RSP_ARGS:
            if len(dec.args) > 1:
                self.__result = tuple(dec.args)
            elif len(dec.args) == 1:
                self.__result = dec.args[0]
        elif dec.kind != RSP_OK:
            self.__event.set()
            raise NotImplemented
        self.__event.set()
        # End of ONESHOT thread

debug = Debug(verbosity)

def ImportModule(module, name="", package=None):
    if not name:
        name = module
    enc = Encode(CMD_IMPORT)
    enc.addType(module, name, package)
    debug.TRACE(Debug.DEBUG, "ImportModule(%s, %s, %s) request\n", module, name, package)
    return RequestThread(*SERVER_ADDRESS).send(enc.getData(SOCKET_SIZE_MAX))

def RemoveHandle(handle):
    enc = Encode(CMD_REMOVE_HANDLE)
    enc.addHandle(handle)
    debug.TRACE(Debug.DEBUG, "RemoveHandle(%X) request\n", handle)
    return RequestThread(*SERVER_ADDRESS).send(enc.getData(SOCKET_SIZE_MAX))

def RemoveCallback(cbId):
    enc = Encode(CMD_REMOVE_CALLBACK)
    enc.addCallback(cbId)
    LocalRemoveCallback(cbId)
    debug.TRACE(Debug.DEBUG, "RemoveCallback(%s) request\n", cbId)
    return RequestThread(*SERVER_ADDRESS).send(enc.getData(SOCKET_SIZE_MAX))

def RemoveAllCallback(idName):
    enc = Encode(CMD_REMOVE_ALL_CALLBACK)
    enc.addCallback(idName)
    LocalRemoveAllCallback(idName)
    debug.TRACE(Debug.DEBUG, "RemoveAllCallback(%s) request\n", idName)
    return RequestThread(*SERVER_ADDRESS).send(enc.getData(SOCKET_SIZE_MAX))

def Execute(command, handle=None, callback=None):
    enc = Encode(CMD_EXECUTE)
    if handle != None:
        enc.addHandle(handle)
        handle = "%X" % handle
    else:
        enc.addType(None)
    if callback != None:
        cbId, cbFunction = callback
        LocalAddNewCallback(*callback)
        enc.addCallback(cbId)
    else:
        enc.addType(None)
    enc.addType(command)
    debug.TRACE(Debug.DEBUG, "Execute(%s, %s, %s) request\n", command, handle, callback)
    return RequestThread(*SERVER_ADDRESS).send(enc.getData(SOCKET_SIZE_MAX))

#Test purpose only
def Test(*args):
    print "Args:", args

if __name__ == "__main__":
    if local:
        ImportModule("os")
        print Execute("os.getcwd()")
        ImportModule("time", "my_module_name")
        print Execute("my_module_name.time()")
        obj = Execute("Test()")
        print obj
        print Execute("test(\"OK\")",obj)
        obj2 = Execute("Test()")
        print obj2
        print Execute("test(\"OK2\")", obj2)
        RemoveHandle(obj)
        RemoveHandle(obj2)
        obj3 = Execute("Test(2)")
        print obj3
        Execute("callbackTest(%s, \"arg1\", 30, True)" % CB_KEYWORD, obj3, ("Test30", Test))
        time.sleep(1)
        Execute("callbackTest(%s, \"arg2\", 31, False)" % CB_KEYWORD, obj3, ("Test31", Test))
        Execute("callbackTest(%s, \"arg3\", 32, False)" % CB_KEYWORD, obj3, ("Test33", Test))
        time.sleep(5)
        RemoveAllCallback("Test")
        RemoveHandle(obj3) 
    else:# Remote test: Raspberry PI
        ImportModule("os")
        print Execute("os.getcwd()") # /home/pi/python/PoolSurvey
        # From here: need to plug LCD on I2C
        ImportModule("smbus")
        busHandle = Execute("smbus.SMBus(1)")
        print "LCD Light OFF for 2s"
        Execute("write_byte(0x27, 0)", busHandle)
        time.sleep(2)
        print "LCD Light ON for 2s"
        Execute("write_byte(0x27, 8)", busHandle)
        time.sleep(2)
        print "LCD Light OFF"
        Execute("write_byte(0x27, 0)", busHandle)
        RemoveHandle(busHandle)
    print "Done"
    #raw_input("Appuyer sur entree pour continuer")
