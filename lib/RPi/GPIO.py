import sys, os, time
sys.path.append(os.path.join(os.path.dirname(__file__), os.path.pardir))
import host

host.ImportModule(".GPIO", "GPIO", "RPi")

class Pmw:
    def __init__(self, handle):
        self.__handle = handle

    def __del__(self):
        if self.__handle != None:
            host.RemoveHandle(self.__handle)

    def start(self, percent):
        host.Execute("start(%s)" % str(percent), self.__handle)

    def stop(self):
        host.Execute("stop()", self.__handle)

    def ChangeFrequency(self, freq):
        host.Execute("ChangeFrequency(%s)" % str(freq), self.__handle)

    def ChangeDutyCycle(self, dc):
        host.Execute("ChangeDutyCycle(%s)" % str(dc), self.__handle)

class Gpio:
    LOW = 0
    HIGH = 1
    IN = 1
    OUT = 0
    SERIAL = 40
    SPI = 41
    I2C = 42
    HARD_PWM = 43
    PUD_UP = 22
    PUD_DOWN = 21
    PUD_OFF = 20
    RISING = 31
    FALLING = 32
    BOTH = 33
    BCM = 11
    BOARD = 10
    VERSION = "0.6.3"
    def __init__(self):
        self.__pwms = dict()

    def __del__(self):
        for channel in self.__pwms:
            del self.__pwms[channel]

    def getmode(self):
        return host.Execute("GPIO.getmode()")

    def setmode(self, mode):
        host.Execute("GPIO.setmode(%s)" % str(mode))

    def setwarnings(self, on):
        host.Execute("GPIO.setwarnings(%s)" % str(on))

    def cleanup(self): # use *args
        host.Execute("GPIO.cleanup()")
        host.RemoveAllCallback("evtDetect")

    def input(self, channel):
        return host.Execute("GPIO.input(%s)" % str(channel))
    
    def output(self, channel, value):
        host.Execute("GPIO.output(%s, %s)" % (str(channel), str(value)))

    def setup(self, channel, direction, pull_up_down=None, initial=None):
        if direction == self.OUT:
            if initial == None:
                host.Execute("GPIO.setup(%s, %s)" % (str(channel), str(direction)))
            else:
                host.Execute("GPIO.setup(%s, %s, initial=%s)" % (str(channel), str(direction), str(initial)))
        else:
            if pull_up_down == None:
                host.Execute("GPIO.setup(%s, %s)" % (str(channel), str(direction)))
            else:
                host.Execute("GPIO.setup(%s, %s, pull_up_down=%s)" % (str(channel), str(direction), str(pull_up_down)))

    def add_event_detect(self, channel, edge, callback=None, bouncetime=50):
        if callback != None:
            cbItems = ("evtDetect%d" % channel, callback)
        else:
            cbItems == None
        host.Execute("GPIO.add_event_detect(%s, %s, %s, %s)" % (str(channel), str(edge), host.CB_KEYWORD, str(bouncetime)), callback=cbItems)

    def event_detected(self, channel):
        return host.Execute("GPIO.event_detected(%s)" % str(channel))

    def remove_event_detect(self, channel):
        host.Execute("GPIO.remove_event_detect(%s)" % str(channel))
        host.RemoveCallback("evtDetect%d" % channel)

    def wait_for_edge(self, channel, edge, bouncetime=0, timeout=-1):
        return host.Execute("GPIO.wait_for_edge(%s, %s, %s, %s)" % (str(channel), str(edge), str(bouncetime), str(timeout)))
    
    def gpio_function(self, channel):
        return host.Execute("GPIO.gpio_function(%s)" % str(channel))
    
    def PWM(self, channel, frequency):
        handle = host.Execute("GPIO.PWM(%s, %s)" % (str(channel), str(frequency)))
        if self.__pwms.has_key(channel):
            pwm = self.__pwms.pop(channel)
            del pwm
        self.__pwms[channel] = Pmw(handle)
        return self.__pwms[channel]

GPIO = Gpio()

def __btnCb(pin):
    print pin, GPIO.input(pin)

if __name__ == '__main__':
    GPIO.setmode(GPIO.BCM)
    pin_out = 26
    pin_in = 19
    pin_cb = 6
    # From here: need to have a jumper plugged
    GPIO.setup(pin_in, GPIO.IN)
    GPIO.setup(pin_out, GPIO.OUT)
    for state in (False, True, False, True, False):
        print "Test GPIO %d->%d at %s" % (pin_out, pin_in, ["False", "True"][state])
        GPIO.output(pin_out, state)
        value = GPIO.input(pin_in)
        assert value == state, "Mismatch: got %d and expect %d" % (value, state)
    # From here: need to have a button plugged
    GPIO.setup(pin_cb, GPIO.IN)
    GPIO.add_event_detect(pin_cb, GPIO.BOTH, callback=__btnCb)
    duration = 10
    print "You have %ds to trig your events!" % duration
    time.sleep(duration)
    GPIO.cleanup()
    print "Done"
    #raw_input("Appuyer sur entree pour continuer")
