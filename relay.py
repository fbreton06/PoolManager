#!/usr/bin/python
import sys, os
sys.path.append(os.path.join(os.path.pardir, "RRaspPY"))
import RPi.GPIO as GPIO

class Relay:
    def __init__(self, pin):
        self.__pin = pin
        GPIO.setup(pin, GPIO.OUT, initial=GPIO.HIGH)

    def switchOn(self):
        GPIO.output(self.__pin, GPIO.LOW)

    def switchOff(self):
        GPIO.output(self.__pin, GPIO.HIGH)

    def switchToggle(self):
        if GPIO.input(self.__pin) == GPIO.LOW:
            GPIO.output(self.__pin, GPIO.HIGH)
        else:
            GPIO.output(self.__pin, GPIO.LOW)

    def isSwitchOn(self):
        return GPIO.input(self.__pin) == GPIO.LOW

    def isSwitchOff(self):
        return GPIO.input(self.__pin) == GPIO.HIGH
