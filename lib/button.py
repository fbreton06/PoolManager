#!/usr/bin/python
import time
import RPi.GPIO as GPIO
from helper import *

class Button(Debug):
    def __init__(self, pin, debounce_ms=10, callback=None):
        Debug.__init__(self)
        self.__pin = pin;
        self.__debounce_ms = debounce_ms
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.__pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        self.__previousTime = time.time() * 1000
        self.__previousState = self.__currentState = GPIO.input(self.__pin)
        if callback:
            self.__btnCb = callback
            GPIO.add_event_detect(self.__pin, GPIO.BOTH, callback=self.__callback)

    def __callback(self, pin):
        self.__btnCb(pin, GPIO.input(pin))

    def update(self):
        state = GPIO.input(self.__pin)
        currentTime = time.time() * 1000
        self.__previousState = self.__currentState
        if state != self.__currentState:
            if currentTime - self.__previousTime >= self.__debounce_ms:
                self.__currentState = state
            self.__previousTime = currentTime
        elif currentTime - self.__previousTime >= self.__debounce_ms:
            self.__previousTime = currentTime - self.__debounce_ms - 1

    def isPressed(self):
        return not self.__currentState and self.__previousState

    def isReleased(self):
        return self.__currentState and not self.__previousState

    def isDown(self):
        return not self.__currentState

    def isUp(self):
        return self.__currentState
