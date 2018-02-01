#!/usr/bin/env python
# coding: utf-8 
import struct, types

from helper import Debug

# convert (big-endian) ">" or "!"
# convert (little-endian) "<"
BYTE_ORDER = ">" # see sys.byteorder == "little"

TYPE_NONE = 0x00
TYPE_INT8 = 0x01
TYPE_INT16 = 0x02
TYPE_INT32 = 0x03
TYPE_INT64 = 0x04
TYPE_UINT8 = 0x05
TYPE_UINT16 = 0x06
TYPE_UINT32 = 0x07
TYPE_UINT64 = 0x08
TYPE_BOOL = 0x09
TYPE_STR = 0x0A
TYPE_USTR = 0x0B
TYPE_FLOAT = 0x0C
TYPE_DOUBLE = 0x0D

TYPE_SIMPLE_MAX = 0x63
TYPE_HANDLE = 0x64
TYPE_TUPLE = 0x65
TYPE_LIST = 0x66
TYPE_DICT = 0x67
TYPE_CALLBACK = 0x68

MARSHAL_SUPPORTED_TYPES = (types.StringType, types.BooleanType, types.IntType, types.LongType, types.FloatType, \
                           types.DictType, types.TupleType, types.ListType, types.NoneType, types.UnicodeType)

class Encode(Debug):
    def __init__(self, kind, verbosity=Debug.ERROR):# DEBUG or ERROR
        Debug.__init__(self, verbosity)
        self.__byteorder = BYTE_ORDER
        self.__data = self.__pack("B", kind)

    def __repr__(self):
        return str(self)
    
    def __str__(self):
        return " ".join(["%02X" % ord(c) for c in self.__data])

    def __pack(self, fmt, value):
        if type(value) == types.ListType:
            data = struct.pack(self.__byteorder + fmt, *value)
        else:
            data = struct.pack(self.__byteorder + fmt, value)
        self.TRACE(self.DEBUG, "%s(%s): %s\n", self.__byteorder + fmt, str(value), ["0x%02X" % ord(x) for x in data])
        return data

    def __addType(self, arg):   
        if type(arg) == types.NoneType:
            self.__data += self.__pack("B", TYPE_NONE)
        elif type(arg) == types.BooleanType:
            self.__data += self.__pack("B", TYPE_BOOL)
            self.__data += self.__pack("B", int(arg))
        elif type(arg) == types.IntType:
            self.__data += self.__pack("B", TYPE_INT32)
            self.__data += self.__pack("i", arg)
        elif type(arg) == types.LongType:
            self.__data += self.__pack("B", TYPE_INT64)
            self.__data += self.__pack("q", arg)
        elif type(arg) == types.FloatType:
            self.__data += self.__pack("B", TYPE_FLOAT)
            self.__data += self.__pack("f", arg)
        elif type(arg) == types.StringType:
            self.__data += self.__pack("B", TYPE_STR)
            self.__data += self.__pack("H", len(arg))
            self.__data += self.__pack("c"*len(arg), list(arg))
        elif type(arg) == types.UnicodeType:
            self.__data += self.__pack("B", TYPE_USTR)
            self.__data += self.__pack("H", len(arg))
            raise NotImplemented
        elif type(arg) == types.TupleType or type(arg) == types.ListType:
            self.__data += self.__pack("B", [TYPE_TUPLE, TYPE_LIST][type(arg) == types.ListType])
            self.__data += self.__pack("H", len(arg))
            for item in arg:
                self.__addType(item)
        elif type(arg) == types.DictType:
            self.__data += self.__pack("B", TYPE_DICT)
            self.__data += self.__pack("H", len(arg))
            for key, value in arg.items():
                self.__addType(key)
                self.__addType(value)
        else:
            raise NotImplemented

    def addHandle(self, handle):
        assert handle < 65536, "Instance handle %d exceeds" % handle
        self.__data += self.__pack("B", TYPE_UINT16)
        self.__data += self.__pack("H", handle)

    def addCallback(self, cbId):
        assert type(cbId) == types.StringType, "Unexpected type of callback ID %s" % type(cbId)
        self.__data += self.__pack("B", TYPE_STR)
        self.__data += self.__pack("H", len(cbId))
        self.__data += self.__pack("c"*len(cbId), list(cbId))

    def addType(self, *args):
        for arg in args:
            self.__addType(arg)

    def getData(self, maxSize=None):
        if maxSize != None and len(self.__data) > maxSize:
            raise ValueError, "Too many parameters: size %d exceeds" % len(self.__data)
        return self.__data

class Decode(Debug):
    def __init__(self, data, verbosity=Debug.ERROR):# DEBUG or ERROR
        Debug.__init__(self, verbosity)
        self.__byteorder = BYTE_ORDER
        self.args = self.__getArgs(data)

    def __repr__(self):
        return str(self)

    def __str__(self):
        text = "[%s]\n" % self.kind
        for arg in self.args:
            text += "%s\n" % str(arg)
        return text

    def __unpack(self, fmt, data):
        return struct.unpack(self.__byteorder + fmt, data)[0]

    def __getArgs(self, data):
        args = list()
        index = 1
        self.kind = self.__unpack("B", data[:index])
        while index < len(data):
            arg, index = self.__getType(index, data)
            args.append(arg)
        if index != len(data):
            raise ValueError, "Unexpected data length: read %d bytes in buffer of %d bytes" % (index, len(data))
        return args

    def __getType(self, index, data):
        argType = self.__unpack("B", data[index:index+1]); index += 1
        if argType < TYPE_SIMPLE_MAX:
            arg, index = self.__getBaseType(argType, index, data)
        elif argType == TYPE_TUPLE or argType == TYPE_LIST:
            nbItem = self.__unpack("H", data[index:index+2]); index += 2
            arg = list()
            for i in range(nbItem):
                item, index = self.__getType(index, data)
                arg.append(item)
            if argType == TYPE_TUPLE:
                arg = tuple(arg)
        elif argType == TYPE_DICT:
            nbItem = self.__unpack("H", data[index:index+2]); index += 2
            arg = dict()
            for i in range(nbItem):
                key, index = self.__getType(index, data)
                value, index = self.__getType(index, data)
                arg[key] = value
        else:
            raise NotImplemented
        return arg, index

    def __getBaseType(self, argType, index, data):
        if argType == TYPE_NONE:
            arg = None
        elif argType == TYPE_INT8:
            arg = self.__unpack("b", data[index:index+1]); index += 1
        elif argType == TYPE_INT16:
            arg = self.__unpack("h", data[index:index+2]); index += 2
        elif argType == TYPE_INT32:
            arg = self.__unpack("i", data[index:index+4]); index += 4
        elif argType == TYPE_INT64:
            arg = self.__unpack("q", data[index:index+8]); index += 8
        elif argType == TYPE_UINT8:
            arg = self.__unpack("B", data[index:index+1]); index += 1
        elif argType == TYPE_UINT16:
            arg = self.__unpack("H", data[index:index+2]); index += 2
        elif argType == TYPE_UINT32:
            arg = self.__unpack("I", data[index:index+4]); index += 4
        elif argType == TYPE_UINT64:
            arg = self.__unpack("Q", data[index:index+8]); index += 8
        elif argType == TYPE_BOOL:
            arg = [False, True][self.__unpack("B", data[index:index+1]) != 0]; index += 1
        elif argType == TYPE_STR:
            length = self.__unpack("H", data[index:index+2]); index += 2
            arg = "".join(struct.unpack(self.__byteorder+"c"*length, data[index:index+length])); index += length
        elif argType == TYPE_USTR:
            length = self.__unpack("H", data[index:index+2]); index += 2
            raise NotImplemented
        elif argType == TYPE_FLOAT:
            arg = self.__unpack("f", data[index:index+4]); index += 4
        elif argType == TYPE_DOUBLE:
            arg = self.__unpack("d", data[index:index+8]); index += 8
        return arg, index
    
if __name__ == "__main__":
    # Encode/Decode check
    enc = Encode(33)
    enc.addHandle(666)
    l = [1, "6", None, False]
    t = (3, True, "ok")
    d = {"a":1, "b":2, "c":3, "d":4}
    enc.addType(12, True, None, "test", 16.03, l, t, d)
    dec = Decode(enc.getData())
    print enc
    print dec
    assert dec.kind == 33
    assert dec.args[:5] == [666, 12, True, None, 'test'], "Args mismatch: got %s expected %s" % (dec.args[:5], [666, 12, True, None, 'test'])
    assert abs(dec.args[5] - 16.03) < 0.001, "Float mismatch: got %.02f expected 16.03" % dec.args[5]
    assert dec.args[6] == l, "List mismatch: got %s expected %s" % (dec.args[6], l)
    assert dec.args[7] == t, "Tuple mismatch: got %s expected %s" % (dec.args[7], t)
    assert dec.args[8] == d, "Dict mismatch: got %s expected %s" % (dec.args[8], d)
    print "Check OK!"
