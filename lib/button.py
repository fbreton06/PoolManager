#!/usr/bin/python
import time
import RPi.GPIO as GPIO

class Button:
    def __init__(self, pin, debounce_ms=50, btnCb=None, edge=GPIO.FALLING, pullupDown=GPIO.PUD_UP):
        self.__pin = pin
        self.__debounce_ms = debounce_ms
        GPIO.setup(self.__pin, GPIO.IN, pull_up_down=pullupDown)
        self.__btnCb = btnCb
        if edge == GPIO.BOTH:
            GPIO.add_event_detect(self.__pin, GPIO.BOTH, callback=self.__callbackBoth)
        elif edge == GPIO.RISING:
            GPIO.add_event_detect(self.__pin, GPIO.RISING, callback=self.__callbackRising)
        else:
            GPIO.add_event_detect(self.__pin, GPIO.FALLING, callback=self.__callbackFalling)

    def __callbackBoth(self, pin):
        debounce = self.__debounce_ms
        value = GPIO.input(pin)
        while debounce > 0:
            time.sleep(0.01)
            new_value = GPIO.input(pin)
            if value != new_value:
                value = new_value
                debounce = self.__debounce_ms
            self.__debounce_ms -= 10
        self.value = (value == GPIO.HIGH)
        if self.__btnCb:
            self.__btnCb(pin, self.value)

    def __callbackRising(self, pin):
        debounce = self.__debounce_ms
        while debounce > 0:
            time.sleep(0.01)
            if GPIO.input(pin) != GPIO.HIGH:
                debounce = self.__debounce_ms
            self.__debounce_ms -= 10
        self.value = True
        if self.__btnCb:
            self.__btnCb(pin, self.value)

    def __callbackFalling(self, pin):
        debounce = self.__debounce_ms
        while debounce > 0:
            time.sleep(0.01)
            if GPIO.input(pin) != GPIO.LOW:
                debounce = self.__debounce_ms
            self.__debounce_ms -= 10
        self.value = False
        if self.__btnCb:
            self.__btnCb(pin, self.value)
