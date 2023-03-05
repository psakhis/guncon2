import argparse
import re
import sys
import time
from collections import namedtuple
import contextlib as _contextlib
import pyvjoy
import pydirectinput
import logging
import usb1
#import math
import threading
from pystray import Menu, MenuItem 
import pystray
from PIL import Image

import ctypes

log = logging.getLogger("guncon2-daemon")

Postion = namedtuple("Postion", ["x","y"])

#start_time = time.time() 
icon = None
calibrationText = "Calibration"
scaleText = "Scale"
mouseText =  "Mouse"
flasherText = "Flasher"
offscreenText = "Offscreen"
running = False
#action icon Quit
def action():  
    global running    
    global icon
    if running == False:
       icon.stop()
    else:   
       running = False
    
#https://stackoverflow.com/questions/24072790/how-to-detect-key-presses
########################################################################################
try:
    import msvcrt as _msvcrt

    # Length 0 sequences, length 1 sequences...
    _ESCAPE_SEQUENCES = [frozenset(("\x00", "\xe0"))]

    _next_input = _msvcrt.getwch

    _set_terminal_raw = _contextlib.nullcontext

    _input_ready = _msvcrt.kbhit

except ImportError:  # Unix
    import sys as _sys, tty as _tty, termios as _termios, \
        select as _select, functools as _functools

    # Length 0 sequences, length 1 sequences...
    _ESCAPE_SEQUENCES = [
        frozenset(("\x1b",)),
        frozenset(("\x1b\x5b", "\x1b\x4f"))]

    @_contextlib.contextmanager
    def _set_terminal_raw():
        fd = _sys.stdin.fileno()
        old_settings = _termios.tcgetattr(fd)
        try:
            _tty.setraw(_sys.stdin.fileno())
            yield
        finally:
            _termios.tcsetattr(fd, _termios.TCSADRAIN, old_settings)

    _next_input = _functools.partial(_sys.stdin.read, 1)

    def _input_ready():
        return _select.select([_sys.stdin], [], [], 0) == ([_sys.stdin], [], [])

_MAX_ESCAPE_SEQUENCE_LENGTH = len(_ESCAPE_SEQUENCES)

def _get_keystroke():
    key = _next_input()
    while (len(key) <= _MAX_ESCAPE_SEQUENCE_LENGTH and
           key in _ESCAPE_SEQUENCES[len(key)-1]):
        key += _next_input()
    return key

def _flush():
    while _input_ready():
        _next_input()

def key_pressed(key: str = None, *, flush: bool = True) -> bool:
    """Return True if the specified key has been pressed

    Args:
        key: The key to check for. If None, any key will do.
        flush: If True (default), flush the input buffer after the key was found.
    
    Return:
        boolean stating whether a key was pressed.
    """
    with _set_terminal_raw():
        if key is None:
            if not _input_ready():
                return False
            if flush:
                _flush()
            return True

        while _input_ready():
            keystroke = _get_keystroke()
            if keystroke == key:
                if flush:
                    _flush()
                return True
        return False

def print_key() -> None:
    """Print the key that was pressed
    
    Useful for debugging and figuring out keys.
    """
    with _set_terminal_raw():
        _flush()
        print("\\x" + "\\x".join(map("{:02x}".format, map(ord, _get_keystroke()))))

def wait_key(key=None, *, pre_flush=False, post_flush=True) -> str:
    """Wait for a specific key to be pressed.

    Args:
        key: The key to check for. If None, any key will do.
        pre_flush: If True, flush the input buffer before waiting for input.
        Useful in case you wish to ignore previously pressed keys.
        post_flush: If True (default), flush the input buffer after the key was
        found. Useful for ignoring multiple key-presses.
    
    Returns:
        The key that was pressed.
    """
    with _set_terminal_raw():
        if pre_flush:
            _flush()

        if key is None:
            key = _get_keystroke()
            if post_flush:
                _flush()
            return key

        while _get_keystroke() != key:
            pass
        
        if post_flush:
            _flush()

        return key
        
#############################################################################################################
#Brightness control
#############################################################################################################
GetSystemMetrics = ctypes.windll.user32.GetSystemMetrics  
GetDC = ctypes.windll.user32.GetDC
ReleaseDC = ctypes.windll.user32.ReleaseDC
SetDeviceGammaRamp = ctypes.windll.gdi32.SetDeviceGammaRamp
GetDeviceGammaRamp = ctypes.windll.gdi32.GetDeviceGammaRamp

def setBrightness(lpRamp, gamma):
    for i in range(256):                                                            
        #if i < 50:
        # iValue = math.floor(33000 * (gamma / 300))
        #elif i < 100:
        # iValue = math.floor(45000 * (gamma / 300))
        #elif i < 150:
        # iValue = math.floor(58000 * (gamma / 300))      
        #else:
        # iValue = math.floor(min(65535, max(0, math.pow((i + 1)/256.0, ((300 / gamma) + 1.3)*0.1)*65535 + 0.5))) 
        #Phasermaniac formula
        if i < gamma:
         iValue = gamma * 256
        else:
         iValue = i * 256
        if iValue > 65535: iValue = 65535     
        lpRamp[0][i] = lpRamp[1][i] = lpRamp[2][i] = iValue               
    return lpRamp
    
def bakBrightness(lpRamp, lpRamp2):
    for i in range(256):                                          
        lpRamp2[0][i] = lpRamp[0][i]
        lpRamp2[1][i] = lpRamp[1][i]
        lpRamp2[2][i] = lpRamp[2][i]              
    return lpRamp2

hdc = ctypes.wintypes.HDC(GetDC(None))    
GammaArray = ((ctypes.wintypes.WORD * 256) * 3)()
GammaArrayBak = ((ctypes.wintypes.WORD * 256) * 3)()
bBrightness = False
fBrightness = 0
if hdc:        
        GetDeviceGammaRamp(hdc, ctypes.byref(GammaArray))
        GammaArrayBak = bakBrightness(GammaArray, GammaArrayBak)      
        bBrightness = True          
                
############################################################################################

def openDeviceHandle(context, vendor_id, product_id, device_index=1):
    order = 0    
    device_iterator = context.getDeviceIterator(skip_on_error=True)
    try:
        for device in device_iterator:
                if device.getVendorID() == vendor_id and \
                        device.getProductID() == product_id:
                    order = order + 1
                    if order == device_index:    
                        return device.open()                    
                device.close()
    finally:
        device_iterator.close()
    return None           

class Guncon2(object):
    def __init__(self, device, mX, MX, mY, MY, scale, index, mouse_mode, frames_flash, input_delay, offscreen):
        self.device = device
        self.pos = Postion(0, 0)                
        self.X_MIN = mX
        self.X_MAX = MX
        self.Y_MIN = mY
        self.Y_MAX = MY        
        self.trigger = False
        self.prev_trigger = False       
        self.trigger_delay = 0  
        self.trigger_pending = 0   
        self.start = False
        self.prev_start = False
        self.select = False        
        self.A = False                
        self.B = False
        self.C = False
        self.padX = 0
        self.prev_padX = 0
        self.padY = 0
        self.prev_padY = 0
        self.j = pyvjoy.VJoyDevice(index)         
        pydirectinput.PAUSE = False
        pydirectinput.FAILSAFE = False
        self.scale = scale     
        self.mouse = mouse_mode
        self.mouse_prev_trigger = False
        self.mouse_prev_start = False
        self.mouse_prev_A = False
        self.flash = frames_flash     
        self.delay = input_delay
        self.offscr = offscreen
        self.do_offscr = False                        
    
    @property
    def absinfo(self):       
        return [(self.X_MIN, self.X_MAX), (self.Y_MIN, self.Y_MAX)]

    @property
    def min_x(self):        
        return self.X_MIN

    @property
    def max_x(self):        
        return self.X_MAX

    @property
    def min_y(self):        
        return self.Y_MIN

    @property
    def max_y(self):        
        return self.Y_MAX            
                       
    @property
    def pos_normalised(self):      
        return Postion(self.normalise(self.pos.x, self.min_x, self.max_x),
                       self.normalise(self.pos.y, self.min_y, self.max_y))

    @staticmethod
    def normalise(pos, min_, max_):        
        return (pos - min_) / float(max_ - min_)
    
    
    def mapData(self,data):              
        global fBrightness             
        global calibrationText  
        global icon
        #Axis
        gunX = data[3]
        gunX <<= 8
        gunX |= data[2]       
        gunY = data[5]
        gunY <<= 8
        gunY |= data[4]        
        self.pos = Postion(gunX, gunY) 
        
        self.prev_trigger = self.trigger 
        #Buttons
        self.trigger = ((data[1] & 0x20) == 0)            
        self.A = ((data[0] & 0x08) == 0)    
        self.B = ((data[0] & 0x04) == 0)         
        self.C = ((data[0] & 0x02) == 0)
        self.start = ((data[1] & 0x80) == 0)
        self.select = ((data[1] & 0x40) == 0)    
        
        #Brightness control (occurs every frame, 16ms)
        if fBrightness >= 0:
            fBrightness = fBrightness - 1                 
        if self.prev_trigger == False and self.trigger == True:
            fBrightness = self.flash   
        
        #Trigger input delay (only when no flash)
        if self.prev_trigger == False and self.trigger == True and fBrightness > 0:
            self.trigger_delay = max(self.delay, self.trigger_delay)                   
        
        if self.trigger_delay > 0:
            if self.trigger == True:                                   
                 self.trigger_pending = self.trigger_pending + 1
        else: 
            if self.trigger_pending > 0 and self.trigger == False:
                 self.trigger = True
                 self.trigger_pending = self.trigger_pending - 1                                           
        
        #Offscreen button mapping
        self.do_offscr = False
        if self.trigger_delay <= 0 and self.trigger == True and (self.pos_normalised[0] < 0 or self.pos_normalised[1] < 0 or self.pos_normalised[0] > 1 or self.pos_normalised[1] > 1):                                 
           if self.offscr == 1:
              self.do_offscr = True   
              self.A = True
           if self.offscr == 2:
              self.do_offscr = True
              self.B = True
           if self.offscr == 3:
              self.do_offscr = True
              self.C = True
              
        #HAT
        self.prev_padY = self.padY
        if ((data[0] & 0x10) == 0):
            self.padY = -1
        else:
            if ((data[0] & 0x40) == 0):
               self.padY = 1
            else:
               self.padY = 0

        self.prev_padX = self.padX
        if ((data[0] & 0x80) == 0):
           self.padX = -1
        else:
           if ((data[0] & 0x20) == 0):
               self.padX = 1
           else:
               self.padX = 0   
         
        if self.C and self.padX == 1 and self.prev_padX == 0:           
            self.X_MIN = self.X_MIN + 0x01     
            calibrationText = "Using calibration x=({},{}) y=({},{})".format(self.X_MIN,self.X_MAX,self.Y_MIN,self.Y_MAX)
            log.info(calibrationText)  
            icon.notify(calibrationText,title="Calibration updated: X_MIN++")                             
        if self.C and self.padX == -1 and self.prev_padX == 0:                       
            self.X_MIN = self.X_MIN - 0x01   
            calibrationText = "Using calibration x=({},{}) y=({},{})".format(self.X_MIN,self.X_MAX,self.Y_MIN,self.Y_MAX)
            log.info(calibrationText) 
            icon.notify(calibrationText,title="Calibration updated: X_MIN--")                              
        if self.C and self.padY == 1 and self.prev_padY == 0:                       
            self.X_MAX = self.X_MAX - 0x01
            calibrationText = "Using calibration x=({},{}) y=({},{})".format(self.X_MIN,self.X_MAX,self.Y_MIN,self.Y_MAX)
            log.info(calibrationText)  
            icon.notify(calibrationText,title="Calibration updated: X_MAX--")                              
        if self.C and self.padY == -1 and self.prev_padY == 0:                                
            self.X_MAX = self.X_MAX + 0x01
            calibrationText = "Using calibration x=({},{}) y=({},{})".format(self.X_MIN,self.X_MAX,self.Y_MIN,self.Y_MAX)
            log.info(calibrationText)  
            icon.notify(calibrationText,title="Calibration updated: X_MAX++")                              
            
    def updateMouse(self):      
        global fBrightness   
        report_all = True     
        if self.flash > 0 and fBrightness <= 0:
           report_all = False
        
        if report_all:            
           if self.pos_normalised[0] < 0 or self.pos_normalised[1] < 0 or self.pos_normalised[0] > 1 or self.pos_normalised[1] > 1:
               pydirectinput.moveTo(-65536,-65536)            
           else:                                       
               x = int(float(GetSystemMetrics(0) * self.pos_normalised[0]))
               y = int(float(GetSystemMetrics(1) * self.pos_normalised[1]))          
               pydirectinput.moveTo(x,y)
                
           if self.trigger and self.mouse_prev_trigger == False and self.do_offscr == False:                
               pydirectinput.mouseDown()  
           if self.trigger == False and self.mouse_prev_trigger and self.do_offscr == False:               
               pydirectinput.mouseUp()  
           self.mouse_prev_trigger = self.trigger
            
        if self.start and self.mouse_prev_start == False:     
            pydirectinput.mouseDown(button="middle")  
        if self.start == False and self.mouse_prev_start:     
            pydirectinput.mouseUp(button="middle")  
              
        if self.A and self.mouse_prev_A == False:     
            pydirectinput.mouseDown(button="right")  
        if self.A == False and self.mouse_prev_A:     
            pydirectinput.mouseUp(button="right")    
                  
        self.mouse_prev_start = self.start
        self.mouse_prev_A = self.A                                        
               
    def updateVjoy(self):
        #global start_time                               
        global fBrightness 
        report_all = True
        if self.flash > 0 and fBrightness <= 0:
           report_all = False
        
        if report_all:           
           if self.pos_normalised[0] < 0 or self.pos_normalised[1] < 0 or self.pos_normalised[0] > 1 or self.pos_normalised[1] > 1:
               self.j.data.wAxisX = 0
               self.j.data.wAxisY = 0            
           else:                                  
               self.j.data.wAxisX = int(float(self.scale * self.pos_normalised[0]))
               self.j.data.wAxisY = int(float(self.scale * self.pos_normalised[1]))
           """
           if self.trigger:
               print("trigger detected")                 
               
           if  self.trigger:  
               print(time.time()) 
               print("--- %s secondsRead ---" % (time.time() - start_time))              
               print(self.pos_normalised[0], self.pos_normalised[1], self.j.data.wAxisX, self.j.data.wAxisY )             
           """      
          
        self.j.data.lButtons = 0 
        if report_all:
           if self.trigger and self.do_offscr == False:
               self.j.data.lButtons = self.j.data.lButtons + 1
               
        if self.start:
          self.j.data.lButtons = self.j.data.lButtons + 2
        if self.select:
          self.j.data.lButtons = self.j.data.lButtons + 4    
        if self.A:  
          self.j.data.lButtons = self.j.data.lButtons + 8
        if self.B:  
          self.j.data.lButtons = self.j.data.lButtons + 16
        if self.C:  
          self.j.data.lButtons = self.j.data.lButtons + 32                    
                  
        if self.padX == 0 and self.padY == 0: 
          self.j.data.bHats = -1
        else:                            
          if self.padY == -1 and self.padX != -1:  
            if  self.padX == 1:           
               self.j.data.bHats = 4500
            else:
               self.j.data.bHats = 0
          elif self.padX == 1:
            if  self.padY == 1:
               self.j.data.bHats = 13500    
            else:
               self.j.data.bHats = 9000
          elif self.padY == 1:
            if  self.padX == -1:
               self.j.data.bHats = 22500    
            else:
               self.j.data.bHats = 18000      
          elif self.padX == -1:
            if  self.padY == -1:
               self.j.data.bHats = 31500    
            else:
               self.j.data.bHats = 27000                                      
               
        self.j.update()                               
     
    #libusb1
    def updateAsync(self,transfer):              
        if transfer.getStatus() != usb1.TRANSFER_COMPLETED:
           return
        data = transfer.getBuffer()[:transfer.getActualLength()]
        self.mapData(data)
        if self.trigger_delay > 0:
           self.trigger_delay = self.trigger_delay - 1
        else:   
           self.updateVjoy()       
           if self.mouse == 1:
              self.updateMouse()           
        transfer.submit()           
     
    def getCommand(self, x=0, y=0):     
        sx = 0
        sy = 0   
        if x < 0:
          sx = 255 #0xff      
        if y < 0:
          sy = 255 #0xff            
        command = [abs(x), sx, abs(y), sy, 0, 1] #60hz mode interlaced
        return command                                                    
           

def libusb_guncon(args):
    #LIBUSB1 async method     
    global fBrightness   
    global hdc    
    global GammaArray, GammaArrayBak      
    global icon
    global running
    setBrightness(GammaArray, args.b)                                 
    with usb1.USBContext() as context:      
        handle = openDeviceHandle(context, 0x0b9a, 0x016a, args.index)      
        if handle is None:            
            log.error("Failed to find any attached GunCon2 device")
            if icon is not None:
                icon.stop()    
            sys.exit(0)                     
        handle.claimInterface(0)          
        guncon = Guncon2(None, args.x[0], args.x[1], args.y[0], args.y[1], args.scale, args.index, args.m, args.f, args.d, args.o)                       
        handle.controlWrite(request_type=0x21, request=0x09, value=0x200, index=0, data=guncon.getCommand(0,0), timeout=100000)                                    
        log.info("Device attached")
        log.info("Press Q key to exit")              
        transfer = handle.getTransfer()
        transfer.setBulk(0x81, 6, guncon.updateAsync)
        transfer.submit()                 
        running = True       
        try:              
            while transfer.isSubmitted() and running:                
                if fBrightness > 0 and fBrightness == args.f:                 
                  SetDeviceGammaRamp(hdc, ctypes.byref(GammaArray))                                                                     
                if fBrightness == 0:                 
                  SetDeviceGammaRamp(hdc, ctypes.byref(GammaArrayBak))                
                try:
                  if key_pressed("q") or key_pressed("Q"):
                    running = False
                  context.handleEvents()                           
                except usb1.USBErrorInterrupted:                 
                  pass
        finally:
            handle.releaseInterface(0)             
        return running
                           
def main():
    global bBrightness
    global hdc
    global GammaArray, GammaArrayBak    
    global calibrationText, scaleText, mouseText, flasherText, offscreenText   
    
    def point_type(value):
        m = re.match(r"\(?(\d+)\s*,\s*(\d+)\)?", value)
        if m:
            return int(m.group(1)), int(m.group(2))
        else:
            raise ValueError("{} is an invalid point".format(value))

    parser = argparse.ArgumentParser()      
    parser.add_argument("-tray", default=0, type=int)      
    parser.add_argument("-index", default=1, type=int)      
    parser.add_argument("-x", default=(175, 720), type=point_type)
    parser.add_argument("-y", default=(20, 240), type=point_type)  
    parser.add_argument("-scale", default=32768, type=int)  
    parser.add_argument("-m", default=0, type=int)      
    parser.add_argument("-b", default=128, type=int)            
    parser.add_argument("-f", default=0, type=int)            
    parser.add_argument("-d", default=1, type=int)            
    parser.add_argument("-o", default=0, type=int)            
    args = parser.parse_args()
    
    logging.basicConfig(level=logging.INFO)   
    log.info("Using device index={}".format(args.index))
    calibrationText = "Using calibration x=({},{}) y=({},{})".format(args.x[0],args.x[1],args.y[0],args.y[1])
    log.info(calibrationText)            
        
    scaleText = "Using analog scale={}".format(args.scale)
    log.info(scaleText)              
                        
    if args.m == 1:        
        mouseText = "Mouse mode enabled m={}".format(args.m)             
    else:        
        mouseText = "Mouse mode disabled m={}".format(args.m)     
    log.info(mouseText)              
                             
    if (bBrightness == False):
        log.warning("Brightness can not be controlled")    
        args.f = 0                   
    
    if (args.f == 0):
        bBrightness = False              
    
    if args.f == 0:    
        flasherText = "Flasher disabled f={}".format(args.f)
    else:
        flasherText = "Flasher enabled (frames) f={} with (brightness) b={} and input delay d={}".format(args.f, args.b, args.d)    
    log.info(flasherText)
        
    if args.o == 0: 
        offscreenText = "Offscreen button disabled o={}".format(args.o)        
    else:
        offscreenText = "Offscreen button enabled o={}".format(args.o)
    log.info(offscreenText)    
    
    main_thread = True
    while (main_thread):      
        main_thread=libusb_guncon(args)
    
    if (bBrightness == True):       
        SetDeviceGammaRamp(hdc, ctypes.byref(GammaArrayBak))
    
    if icon is not None:
       icon.stop()
    
if __name__ == "__main__":    
    parser = argparse.ArgumentParser()      
    parser.add_argument("-tray", default=0, type=int)   
    parser.add_argument("-index", default=1, type=int)   
    args = parser.parse_args()      
    if args.tray == 1:  
        image = Image.open("gun{}.png".format(args.index))        
        icon = pystray.Icon("name", image, "GunCon 2", menu=Menu(        
            MenuItem(lambda text: calibrationText, action, enabled=False),
            MenuItem(lambda text: scaleText, action, enabled=False),
            MenuItem(lambda text: mouseText, action, enabled=False),
            MenuItem(lambda text: flasherText, action, enabled=False),
            MenuItem(lambda text: offscreenText, action, enabled=False),
            MenuItem("Quit", action)
        ))    
        icon.run_detached()   
    sys.exit(main() or 0)
