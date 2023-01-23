import argparse
import re
import sys
import time
from collections import namedtuple
from math import floor, ceil
from queue import Queue

import usb.core
import usb.util

import pyvjoy

import logging

log = logging.getLogger("guncon2-daemon")

Postion = namedtuple("Postion", ["x", "y"])


class Guncon2(object):
    def __init__(self, device, mX, MX, mY, MY):
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
        self.device.set_configuration()
        self.cfg = self.device[0] 
        self.intf = self.cfg[(0,0)] 
        self.ep = self.intf[0] 
        self.connect(x=0,y=0)        
        
    def __del__(self):
        usb.util.dispose_resources(self.device)   
        
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
        #if self.trigger:
        #     print("Normalised ",self.pos.y, self.min_y, self.max_y,self.normalise(self.pos.y, self.min_y, self.max_y))
        return Postion(self.normalise(self.pos.x, self.min_x, self.max_x),
                       self.normalise(self.pos.y, self.min_y, self.max_y))

    @staticmethod
    def normalise(pos, min_, max_):        
        return (pos - min_) / float(max_ - min_)
 
    #winusb 
    def connect(self, x=0, y=0):     
        sx = 0
        sy = 0   
        if x < 0:
          sx = 255 #0xff      
        if y < 0:
          sy = 255 #0xff            
        command = [abs(x), sx, abs(y), sy, 0, 1] #60hz mode interlaced
        assert self.device.ctrl_transfer(bmRequestType=0x21, bRequest=0x09,  wValue=0x200,  wIndex=0, data_or_wLength=command, timeout=100000) == len(command)                        
    
    #winusb
    def update(self):        
       #read 6 bytes               
       try:             
         data = self.device.read(0x81, 6)  # self.ep.bEndpointAddress         
         
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
                
         return True
       except  KeyboardInterrupt:
         raise KeyboardInterrupt      
       except:        
         self.connect(x=0, y=0)  
         return self.update()           
        
    
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
    parser.add_argument("-log", default=False, type=bool)  
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)   
    log.info("Using calibration x=({},{}) y=({},{})".format(args.x[0],args.x[1],args.y[0],args.y[1]))
    log.info("Using analog scale = {}".format(args.scale))
    
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
        while running:         
            #start_time = time.time()                                 
            running = guncon.update()             
            #if  guncon.trigger:     
            #    print("--- %s secondsRead ---" % (time.time() - start_time))   
            
            if guncon.pos_normalised[0] < 0 or guncon.pos_normalised[1] < 0 or guncon.pos_normalised[0] > 1 or guncon.pos_normalised[1] > 1:
                j.data.wAxisX = 0
                j.data.wAxisY = 0
            else:                
                j.data.wAxisX = int(float(args.scale * guncon.pos_normalised[0]))
                j.data.wAxisY = int(float(args.scale * guncon.pos_normalised[1]))
            
            if  args.log and guncon.trigger:              
              print(guncon.pos_normalised[0], guncon.pos_normalised[1], j.data.wAxisX, j.data.wAxisY )     
              
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

if __name__ == "__main__":
    sys.exit(main() or 0)

