#!/usr/bin/env python
# coding: utf-8 
import socket, threading
from importlib import import_module

from helper import Debug
from serialize import *
from protocol import *

#verbosity = Debug.ERROR
#verbosity = Debug.DEBUG
verbosity = Debug.DUMP

local = True
if local:
    CLIENT_ADDRESS = ("", 7070)
    SERVER_ADDRESS = ("", 8080)
else:
    CLIENT_ADDRESS = ("192.168.0.32", 7070)
    SERVER_ADDRESS = (GetIPAddress("wlan0"), 8080)

__lockHdl = threading.RLock()
__instances = dict()

def LocalAddNewInstance(instance):
    global __lockHdl, __instances
    with __lockHdl:
        for handle in range(65536):
            if not __instances.has_key(handle):
                __instances[handle] = instance
                break
        if not __instances.has_key(handle):
            raise ValueError, "Cannot registered new instance"
    return handle

def LocalRemoveInstance(handle):
    global __lockHdl, __instances
    with __lockHdl:
        if __instances.has_key(handle):
            __instances.pop(handle)

def LocalGetInstance(handle):
    global __lockHdl, __instances
    instance = None
    with __lockHdl:
        if __instances.has_key(handle):
            instance = __instances[handle]
    return instance

__lockCb = threading.RLock()
__callbacks = dict()

def LocalAddNewCallback(cbId):
    global __lockCb, __callbacks
    with __lockCb:
        if __callbacks.has_key(cbId):
            #raise ValueError, "Callback ID already exists: %s" % cbId
            newCb = __callbacks[cbId]
        else:
            newCb = CallbackThread(cbId)
            __callbacks[cbId] = newCb
    return newCb

def LocalRemoveCallback(cbId):
    global __lockCb, __callbacks
    callback = None
    with __lockCb:
        if __callbacks.has_key(cbId):
            callback = __callbacks.pop(cbId)
    if callback != None:
        callback.stop()
    
def LocalRemoveAllCallback(idName):
    global __lockCb, __callbacks
    with __lockCb:
        cbIds = list()
        for cbId in __callbacks:
            if cbId.startswith(idName):
                if cbId[len(idName):].isdigit():
                    cbIds.append(cbId)
        for cbId in cbIds:
            callback = __callbacks.pop(cbId)
            callback.stop()

class CallbackThread(threading.Thread, Debug):
    def __init__(self, cbId):
        threading.Thread.__init__(self)
        Debug.__init__(self, verbosity)
        self.__cbId = cbId

    def __del__(self):
        self.stop()

    def callback(self, *args):
        enc = Encode(CMD_CALLBACK)
        enc.addCallback(self.__cbId)
        enc.addType(*args)     
        EventCallbackThread(self.__cbId, *CLIENT_ADDRESS).notification(enc.getData(SOCKET_SIZE_MAX))

    def run(self):
        self.TRACE(self.DEBUG, "CallbackThread: Callback %s thread started\n", self.__cbId)
        self.__active = True
        while self.__active:
            time.sleep(1)

    def stop(self):
        self.TRACE(self.DEBUG, "CallbackThread: Callback %s thread stopped\n", self.__cbId)
        self.__active = False

class EventCallbackThread(threading.Thread, Debug):
    def __init__(self, cbId, address="", port=7070):
        threading.Thread.__init__(self)
        Debug.__init__(self, verbosity)
        self.__event = threading.Event()
        self.__cbId = cbId
        self.__socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.__socket.connect((address, port))

    def notification(self, data):
        self.TRACE(Debug.DUMP, "EventCallbackThread: NOTIFICATION %s\n", " ".join(["%02X " % ord(c) for c in data]))
        self.__socket.send(data)
        self.TRACE(Debug.DEBUG, "EventCallbackThread: Notification to host sent (%d)\n", id(data))
        self.start()
        self.__event.wait(SOCKET_TIMEOUT_S)
        self.TRACE(Debug.DEBUG, "EventCallbackThread: Notification confirmed (%d)\n", id(data))
        self.__socket.close()

    def run(self):
        self.TRACE(Debug.DEBUG, "EventCallbackThread: Wait request response from device\n")
        try:
            data = self.__socket.recv(SOCKET_SIZE_MAX)
            if data != "":
                self.TRACE(Debug.DUMP, "EventCallbackThread: RECEIVE %s\n", " ".join(["%02X" % ord(c) for c in data]))
                dec = Decode(data)
            else:
                dec = Decode(UNKNOWN)
        except socket.error:
            dec = Decode(UNKNOWN)
        self.__event.set()
        if dec.kind != RSP_OK:
            raise NotImplemented
        # End of ONESHOT thread

class ClientThread(threading.Thread, Debug):
    def __init__(self, socket):
        threading.Thread.__init__(self)
        Debug.__init__(self, verbosity)
        self.__socket = socket
        self.start()

    def __result(self, *args):
        self.TRACE(self.DEBUG, "ClientThread: Return %s to host\n", *args)
        enc = Encode(RSP_ARGS)
        enc.addType(*args)
        self.__socket.send(enc.getData(SOCKET_SIZE_MAX))

    def __instance(self, instance):
        self.TRACE(self.DEBUG, "ClientThread: Return %s instance to host\n", instance)
        handle = LocalAddNewInstance(instance)
        enc = Encode(RSP_HANDLE)
        enc.addHandle(handle)
        self.__socket.send(enc.getData(SOCKET_SIZE_MAX))

    def __sendOK(self):
        self.TRACE(self.DEBUG, "ClientThread: Request from host confirmed\n")
        enc = Encode(RSP_OK)
        self.__socket.send(enc.getData(SOCKET_SIZE_MAX))

    def __sendError(self, message):
        self.TRACE(self.DEBUG, "ClientThread: Error %s\n", message)
        enc = Encode(RSP_ERR)
        enc.addType(message)
        self.__socket.send(enc.getData(SOCKET_SIZE_MAX))

    def __sendResult(self, result):
        if type(result) != types.NoneType:
            if type(result) in MARSHAL_SUPPORTED_TYPES:
                self.__result(result)
            else:
                self.__instance(result)
        else:
            self.__sendOK()

    def __import(self, module, name, package):
        try:
            if not globals().has_key(name):
                self.TRACE(self.DEBUG, "ClientThread: Import %s %s\n", module, name)
                globals()[name] = import_module(module, package)
            else:
                self.TRACE(self.DEBUG, "ClientThread: Import %s %s (Already imported!)\n", module, name)
            self.__sendOK()
        except Exception as err:
            self.__sendError(str(err))

    def __removeHandle(self, handle):
        LocalRemoveInstance(handle)
        self.TRACE(self.DEBUG, "ClientThread: Remove handle %X\n", handle)
        self.__sendOK()

    def __removeCallback(self, cbId):
        LocalRemoveCallback(cbId)
        self.TRACE(self.DEBUG, "ClientThread: Remove callback ID %s\n", cbId)
        self.__sendOK()

    def __removeAllCallback(self, idName):
        LocalRemoveAllCallback(idName)
        self.TRACE(self.DEBUG, "ClientThread: Remove all callback ID %s\n", idName)
        self.__sendOK()

    def __execute(self, handle, cbId, command):
        if handle != None:
            instance = LocalGetInstance(handle)
            if instance == None:
                raise ValueError, "Instance doesn't exist anymore"
        if cbId != None:
            self.TRACE(self.DEBUG, "ClientThread: New callback %s\n", cbId)
            newCbThread = LocalAddNewCallback(cbId)
            assert command.count(CB_KEYWORD) == 1, "Command with callback must have \"%s\" keyword that replace the callback function" % CB_KEYWORD
            command = command.replace(CB_KEYWORD, "newCbThread.callback")
        try:
            if handle != None:
                self.TRACE(self.DEBUG, "ClientThread: Execute %s->%s\n", instance, command)
                result = eval("instance." + command)
            else:
                self.TRACE(self.DEBUG, "ClientThread: Execute %s\n", command)
                result = eval(command)
            self.__sendResult(result)
        except Exception as err:
            self.__sendError(str(err))

    def run(self):
        self.TRACE(Debug.DEBUG, "ClientThread: Wait data from host\n")
        try:
            data = self.__socket.recv(SOCKET_SIZE_MAX)
            if data != "":
                dec = Decode(data)
            else:
                dec = Decode(UNKNOWN)
        except socket.error:
            dec = Decode(UNKNOWN)
        # Response
        self.TRACE(Debug.DEBUG, "ClientThread: Treat request from host %d\n", dec.kind)
        if dec.kind == RSP_OK:
            self.TRACE(self.DEBUG, "ClientThread: Receive reponse OK from host\n")
        elif dec.kind == RSP_ERR:
            raise ValueError, dec.args[0]
        # Command
        elif dec.kind == CMD_IMPORT:
            if len(dec.args) == 3:
                self.__import(*dec.args)
            else:
                raise NotImplemented
        elif dec.kind == CMD_EXECUTE:
            if len(dec.args) == 3:
                self.__execute(*dec.args)
            else:
                raise ValueError, "Unexpected number of arguments of Execute function: got %s expected [handle, callback, command]" % dec.args
        elif dec.kind == CMD_REMOVE_HANDLE:
            if len(dec.args) == 1:
                self.__removeHandle(dec.args[0])
            else:
                raise NotImplemented
        elif dec.kind == CMD_REMOVE_CALLBACK:
            if len(dec.args) == 1:
                self.__removeCallback(dec.args[0])
            else:
                raise NotImplemented
        elif dec.kind == CMD_REMOVE_ALL_CALLBACK:
            if len(dec.args) == 1:
                self.__removeAllCallback(dec.args[0])
            else:
                raise NotImplemented
        else:
            raise NotImplemented
        self.__socket.close()

debug = Debug(verbosity)

def Server(address="", port=8080):
    serverSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    serverSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    serverSocket.settimeout(30)
    serverSocket.bind((address, port))
    active = True
    while active:
        try:
            serverSocket.listen(10)
            (receiveSocket, (ip, port)) = serverSocket.accept()
            debug.TRACE(Debug.DEBUG, "Server: Request received from host\n")
            ClientThread(receiveSocket)
        except socket.timeout:
            pass
        except socket.error:
            active = False

# Test purpose only
class Test:
    def __init__(self, delay_s=10):
        self.delay_s = delay_s

    def test(self, message):
        print message
        return message

    def __callback(self):
        self.cbTest[0](*self.cbTest[1:])

    def callbackTest(self, callback, *args):
        self.cbTest =  [callback]
        self.cbTest.extend(args)
        threading.Timer(self.delay_s, self.__callback).start()

if __name__ == "__main__":    
    Server(*SERVER_ADDRESS)
