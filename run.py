import argparse
import re
import sys
import time
from collections import namedtuple
from math import floor, ceil
from queue import Queue
import contextlib as _contextlib


import usb.core
import usb.util

import usb1

import pyvjoy

import logging

log = logging.getLogger("guncon2-daemon")

Postion = namedtuple("Postion", ["x", "y"])

start_time = time.time() 

#https://stackoverflow.com/questions/24072790/how-to-detect-key-presses

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


class Guncon2(object):
    def __init__(self, device, mX, MX, mY, MY, scale):
        self.device = device
        self.pos = Postion(0, 0)        
        self.X_MIN = mX
        self.X_MAX = MX
        self.Y_MIN = mY
        self.Y_MAX = MY
        self.center = Postion(self.max_x/2, self.max_y/2)
        self.trigger = False      
        self.start = False
        self.select = False
        self.A = False
        self.B = False
        self.C = False
        self.padX = 0
        self.padY = 0
        self.j = pyvjoy.VJoyDevice(1) 
        self.scale = scale
        #PyUSB
        """
        self.device.set_configuration()
        self.cfg = self.device[0] 
        self.intf = self.cfg[(0,0)] 
        self.ep = self.intf[0] 
        self.connect(x=0,y=0)        
        self.ltag = 0.0
        """
        
        
        
    def __del__(self):
        if self.device is not None:
            usb.util.dispose_resources(self.device)   #PyUSB
        
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
        #Axis
        gunX = data[3];
        gunX <<= 8;
        gunX |= data[2];         
        gunY = data[5];
        gunY <<= 8;
        gunY |= data[4];
        self.pos = Postion(gunX, gunY) 
        
        #Buttons
        self.trigger = ((data[1] & 0x20) == 0)            
        self.A = ((data[0] & 0x08) == 0)
        self.B = ((data[0] & 0x04) == 0)         
        self.C = ((data[0] & 0x02) == 0)
        self.start = ((data[1] & 0x80) == 0)
        self.select = ((data[1] & 0x40) == 0)    
        
        #HAT
        if ((data[0] & 0x10) == 0):
            self.padY = -1
        else:
            if ((data[0] & 0x40) == 0):
               self.padY = 1
            else:
               self.padY = 0

        if ((data[0] & 0x80) == 0):
           self.padX = -1
        else:
           if ((data[0] & 0x20) == 0):
               self.padX = 1
           else:
               self.padX = 0   
               
    def updateVjoy(self):
        global start_time        
        if self.pos_normalised[0] < 0 or self.pos_normalised[1] < 0 or self.pos_normalised[0] > 1 or self.pos_normalised[1] > 1:
            self.j.data.wAxisX = 0
            self.j.data.wAxisY = 0            
        else:                                  
            self.j.data.wAxisX = int(float(self.scale * self.pos_normalised[0]))
            self.j.data.wAxisY = int(float(self.scale * self.pos_normalised[1]))
        """
        if  self.trigger:
            print("trigger detected")                 
            
        if  self.trigger:  
            print(time.time()) 
            print("--- %s secondsRead ---" % (time.time() - start_time))              
            print(self.pos_normalised[0], self.pos_normalised[1], self.j.data.wAxisX, self.j.data.wAxisY )             
        """      
          
        self.j.data.lButtons = 0 
        if self.trigger:
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
        self.updateVjoy()       
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
        
    #winusb - PyUSB
    """
    def connect(self, x=0, y=0):     
        sx = 0
        sy = 0   
        if x < 0:
          sx = 255 #0xff      
        if y < 0:
          sy = 255 #0xff            
        command = [abs(x), sx, abs(y), sy, 0, 1] #60hz mode interlaced
        assert self.device.ctrl_transfer(bmRequestType=0x21, bRequest=0x09,  wValue=0x200,  wIndex=0, data_or_wLength=command, timeout=100000) == len(command)                                
    
    #winusb - PyUSB
    def update(self):        
       #read 6 bytes        
       if self.ltag <= 0:                   
         self.ltag = 0.009
       else:
         self.ltag = self.ltag - 0.001
         return True
       try:                      
         data = self.device.read(0x81, 6)  # self.ep.bEndpointAddress         
         self.mapData(data)          
         return True
       except  KeyboardInterrupt:
         raise KeyboardInterrupt      
       except:        
         self.connect(x=0, y=0)  
         return self.update()           
    """
    
def main():
    def point_type(value):
        m = re.match(r"\(?(\d+)\s*,\s*(\d+)\)?", value)
        if m:
            return int(m.group(1)), int(m.group(2))
        else:
            raise ValueError("{} is an invalid point".format(value))

    parser = argparse.ArgumentParser()      
    parser.add_argument("-x", default=(175, 720), type=point_type)
    parser.add_argument("-y", default=(20, 240), type=point_type)  
    parser.add_argument("-scale", default=32768, type=int)  
    #parser.add_argument("-log", default=False, type=bool)  
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)   
    log.info("Using calibration x=({},{}) y=({},{})".format(args.x[0],args.x[1],args.y[0],args.y[1]))
    log.info("Using analog scale = {}".format(args.scale))              
    
    #LIBUSB1 async method    
    with usb1.USBContext() as context:
        handle = context.openByVendorIDAndProductID(
            0x0b9a,
            0x016a,
            skip_on_error=True,
        )
        if handle is None: 
            sys.stderr.write("Failed to find any attached GunCon2 devices")
            return 1        
        with handle.claimInterface(0) as ep:            
            guncon = Guncon2(None,args.x[0],args.x[1],args.y[0],args.y[1],args.scale)                       
            handle.controlWrite(request_type=0x21, request=0x09, value=0x200, index=0, data=guncon.getCommand(0,0), timeout=100000)                                    
            log.info("GunCon2 device attached")
            log.info("Daemon running: press any key to exit")              
            transfer = handle.getTransfer()
            transfer.setBulk(0x81, 6, guncon.updateAsync)
            transfer.submit()
            start_time = time.time()            
            running = True               
            while transfer.isSubmitted() and running:
                try:
                  if key_pressed():
                    running = False
                  context.handleEvents()                           
                except usb1.USBErrorInterrupted:
                  pass
    
    
    #old PyUSB (only sync)
    """    
    j = None
    # find vjoy device
    j = pyvjoy.VJoyDevice(1)    
    if j is None:
        sys.stderr.write("Failed to find any attached vJoy device")
        return 1  
        
    guncon2_dev = None
    # find the first guncon2
    guncon2_dev = usb.core.find(idVendor=0x0b9a, idProduct=0x016a)       
    if guncon2_dev is None:
       sys.stderr.write("Failed to find any attached GunCon2 devices")
       return 1   
       
    try:
        guncon = Guncon2(guncon2_dev,args.x[0],args.x[1],args.y[0],args.y[1])  
        log.info("GunCon2 device attached")          
        running = True     
        prev_trigger = False 
        next_log = 0
        sys.setswitchinterval(0.001)     
        while running:         
            start_time = time.time()                                 
            running = guncon.update()                         
            
            if guncon.pos_normalised[0] < 0 or guncon.pos_normalised[1] < 0 or guncon.pos_normalised[0] > 1 or guncon.pos_normalised[1] > 1:
                j.data.wAxisX = 0
                j.data.wAxisY = 0
            else:                
                j.data.wAxisX = int(float(args.scale * guncon.pos_normalised[0]))
                j.data.wAxisY = int(float(args.scale * guncon.pos_normalised[1]))
            
            if  args.log and guncon.trigger and not prev_trigger:
                print("trigger detected")     
              
            if  args.log and not guncon.trigger and prev_trigger:
                print("trigger down")     
                next_log = 4
                
            if  args.log and guncon.ltag < 0.001 and (guncon.trigger or next_log > 0):  
                print(time.time()) 
                print("--- %s secondsRead ---" % (time.time() - start_time))              
                print(guncon.ltag, guncon.pos_normalised[0], guncon.pos_normalised[1], j.data.wAxisX, j.data.wAxisY ) 
                next_log = next_log - 1    
            
            prev_trigger = guncon.trigger
              
            j.data.lButtons = 0 
            if guncon.trigger:
              j.data.lButtons = j.data.lButtons + 1
            if guncon.start:
              j.data.lButtons = j.data.lButtons + 2
            if guncon.select:
              j.data.lButtons = j.data.lButtons + 4    
            if guncon.A:  
              j.data.lButtons = j.data.lButtons + 8
            if guncon.B:  
              j.data.lButtons = j.data.lButtons + 16
            if guncon.C:  
              j.data.lButtons = j.data.lButtons + 32    
              
            if guncon.padX == 0 and guncon.padY == 0: 
              j.data.bHats = -1
            else:                            
              if guncon.padY == -1 and guncon.padX != -1:  
                if  guncon.padX == 1:           
                   j.data.bHats = 4500
                else:
                   j.data.bHats = 0
              elif guncon.padX == 1:
                if  guncon.padY == 1:
                   j.data.bHats = 13500    
                else:
                   j.data.bHats = 9000
              elif guncon.padY == 1:
                if  guncon.padX == -1:
                   j.data.bHats = 22500    
                else:
                   j.data.bHats = 18000      
              elif guncon.padX == -1:
                if  guncon.padY == -1:
                   j.data.bHats = 31500    
                else:
                   j.data.bHats = 27000                                      
              j.update()                                    
    except KeyboardInterrupt:
        running = False
        print("Program terminated manually!")            
        raise SystemExit                                   
    """
    
if __name__ == "__main__":
    sys.exit(main() or 0)

