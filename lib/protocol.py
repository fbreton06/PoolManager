#!/usr/bin/env python
# coding: utf-8 
from subprocess import Popen, PIPE, STDOUT

CB_KEYWORD = "CB_FUNCT"

UNKNOWN = "%c" % 0x00

RSP_ERR = 0x09
RSP_OK = 0x0A
RSP_ARGS = 0x0B
RSP_HANDLE = 0x0D

CMD_REMOVE_HANDLE = 0x90
CMD_REMOVE_CALLBACK = 0xA0
CMD_EXECUTE = 0xB0
CMD_IMPORT = 0xC0
CMD_CALLBACK = 0xD0
CMD_REMOVE_ALL_CALLBACK = 0xE0

SOCKET_TIMEOUT_S = 30
SOCKET_SIZE_MAX = 4096

def GetIPAddress(networkName):
    command = "ip addr show %s | awk -F\" +|/\" 'NR==3{print $3}'" % networkName
    process = Popen(command, stdout=PIPE, shell=True, stderr=STDOUT)
    result = process.communicate()
    if result[0].count(".") != 3:
        raise ValueError, "wlan0 IP address is not found: \"%s\"" % result[0]
    return result[0].strip()