#!/usr/bin/python
import time
from button import Button
from helper import *


class TicksPerSecond(Debug):
    TPS_TIMES_PER_PERIOD = 3
    def __init__(self, holdLastTimeoutMillis):
        Debug.__init__(self)
        self.__tps = 0.0
        self.__counters = list()
        self.__started = list()
        self.__previousTime = time.time() * 1000
        for i in range(self.TPS_TIMES_PER_PERIOD):
            self.__counters.append(0)
            self.__started.append(self.__previousTime)
        self.__curCounter = 0
        self.__deltaTime = holdLastTimeoutMillis / self.TPS_TIMES_PER_PERIOD

    def update(self, tick=True):
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
            currentTime = 1 # This is a division by zero protection.
        self.__tps = float(self.__counters[self.__curCounter] * 1000) / currentTime

    def getTPS(self):
        return int(self.__tps)

class Rotary(TicksPerSecond):
    MIN_TPS = 5
    MAX_TPS = 30
    TICKS_AT_MAX_SPEED_FOR_FULL_SPAN = 100
    def __init__(self, pinA, pinB, max=1000, min=0, position=0, callback=None, debounce_ms=1, holdLastTimeout_ms=500):
        TicksPerSecond.__init__(self, holdLastTimeout_ms)
        self.__minValue = min
        self.__maxValue = max
        self.__position = position
        self.__btnA = Button(pinA, debounce_ms, self.__callback)
        self.__btnB = Button(pinB, debounce_ms)
        self.callback = callback

    def __constrain(self, value, min, max):
        if value > max:
            return max
        if value < min:
            return min
        return value

    def __callback(self, pin, state):
        self.update()
        if self.callback:
            self.callback(self.__position)

    def update(self):
        self.__btnA.update()
        self.__btnB.update()
        if self.__btnA.isPressed():
            super(Rotary, self).update(True)
            speed = self.__constrain(self.getTPS(), self.MIN_TPS, self.MAX_TPS) - self.MIN_TPS
            delta = max(1, (self.__maxValue - self.__minValue) / self.TICKS_AT_MAX_SPEED_FOR_FULL_SPAN)
#            // Linear acceleration (very sensitive - not comfortable)
#            // long step = 1 + delta * speed / (MAX_TPS - MIN_TPS);
#
#            // Exponential acceleration - square (OK for [maxValue - minValue] = up to 5000)
#            // long step = 1 + delta * speed * speed / ((MAX_TPS - MIN_TPS) * (MAX_TPS - MIN_TPS));
#
#            // Exponential acceleration - cubic (most comfortable)
            step = 1 + delta * speed * speed * speed / \
                    ((self.MAX_TPS - self.MIN_TPS) * (self.MAX_TPS - self.MIN_TPS) * (self.MAX_TPS - self.MIN_TPS))

            self.__position = self.__constrain(self.__position + [step, -step][self.__btnB.isUp()], self.__minValue, self.__maxValue)
        else:
            super(Rotary, self).update(False)

    def getPosition(self):
#        disableInterrupts()
        result = self.__position
#        restoreInterrupts()
        raise ValueError, "Not yet implemented!"
        return result

    def setPosition(self, newPosition):
#        disableInterrupts()
#        self.__position = self.__constrain(newPosition, self.__minValue, self.__maxValue)
#        restoreInterrupts()
        raise ValueError, "Not yet implemented!"

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
