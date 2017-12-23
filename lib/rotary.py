#!/usr/bin/python
import time
from button import Button
from helper import *
from threading import Lock

class TicksPerSecond(Debug):
    TPS_TIMES_PER_PERIOD = 3
    def __init__(self, holdLastTimeoutMillis):
        Debug.__init__(self)
        self.__counters = list()
        self.__started = list()
        self.__previousTime = time.time() * 1000
        for i in range(self.TPS_TIMES_PER_PERIOD):
            self.__counters.append(0)
            self.__started.append(self.__previousTime)
        self.__curCounter = 0
        self.__deltaTime = holdLastTimeoutMillis / self.TPS_TIMES_PER_PERIOD

    def __StateUpdate(self, tick=True):
        currentTime = time.time() * 1000
        if currentTime - self.__previousTime >= self.__deltaTime:
            self.__counters[self.__curCounter] = 0
            self.__curCounter += 1
            self.__previousTime = currentTime
            if self.__curCounter >= self.TPS_TIMES_PER_PERIOD:
                self.__curCounter = 0
            self.__started[self.__curCounter] = currentTime
        if tick:
            for i in range(self.TPS_TIMES_PER_PERIOD):
                self.__counters[i] += 1
        currentTime -= self.__started[self.__curCounter]
        if currentTime <= 0:
            currentTime = 1
        return int(float(self.__counters[self.__curCounter] * 1000) / currentTime)

class Rotary(TicksPerSecond):
    MIN_TPS = 5
    MAX_TPS = 30
    TICKS_AT_MAX_SPEED_FOR_FULL_SPAN = 100
    def __init__(self, pinA, pinB, max=1000, min=0, position=0, callback=None, debounce_ms=1, holdLastTimeout_ms=500):
        TicksPerSecond.__init__(self, holdLastTimeout_ms)
        self.__minValue = min
        self.__maxValue = max
        self.__previousPosition = self.__position = position
        self.__btnA = Button(pinA, debounce_ms, self.__callback)
        self.__btnB = Button(pinB, debounce_ms)
        self.callback = callback
        self.__lock = Lock()

    def __constrain(self, value, min, max):
        if value > max:
            return max
        if value < min:
            return min
        return value

    def StateUpdate(self):
        self.__btnA.StateUpdate()
        self.__btnB.StateUpdate()
        if self.__btnA.isPressed():
            tps = self.__StateUpdate(True)
            speed = self.__constrain(tps, self.MIN_TPS, self.MAX_TPS) - self.MIN_TPS
            delta = max(1, (self.__maxValue - self.__minValue) / self.TICKS_AT_MAX_SPEED_FOR_FULL_SPAN)
            step = 1 + delta * speed * speed * speed / \
                    ((self.MAX_TPS - self.MIN_TPS) * (self.MAX_TPS - self.MIN_TPS) * (self.MAX_TPS - self.MIN_TPS))
            self.__lock.acquire()
            self.__position = self.__constrain(self.__position + [step, -step][self.__btnB.isUp()], self.__minValue, self.__maxValue)
            self.__lock.release()
        else:
            self.__StateUpdate(False)

    def __callback(self, pin, state):
        self.StateUpdate()
        if self.callback:
            self.__lock.acquire()
            position = self.__position
            delta = position - self.__previousPosition
            self.__previousPosition = position
            self.__lock.release()
            self.callback(position, delta)

    def getPosition(self):
        self.__lock.acquire()
        position = self.__position
        self.__lock.release()
        return position

    def setPosition(self, newPosition):
        self.__lock.acquire()
        self.__previousPosition = self.__position = self.__constrain(newPosition, self.__minValue, self.__maxValue)
        self.__lock.release()

def __button(pin, state):
        print 'Btn:', pin, state

def __rotation(position):
        print 'Rot:', position

if __name__ == '__main__':
    rotary = Rotary(17, 18, 5000, 50, 500, __rotation, 2)
    button = Button(27, 100, __button)
    try:
        while True:
            time.sleep(5.0)
    except KeyboardInterrupt:
        print 'done'
