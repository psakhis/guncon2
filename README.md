# guncon2
GunCon2 daemon for Windows

This project is based on sonik-br work https://github.com/sonik-br/GunconUSB

With a daemon and their winusb driver, is possible to connect GunCon2 as vjoy joystick 

Install
 1) Install VJoy - https://sourceforge.net/projects/vjoystick/
 2) Install GunCon2 Driver - https://github.com/sonik-br/GunconUSB
 
 Setup
 1) Calibration tool to obtain x and y ABS. This can be innacurate. Do with 320x240 resolution
 2) Run daemon
 
    a) By default, daemon runs on x and y ABS settings, you can provide other with args
    
       Example:
         -x=(175,720) -y=(9,249)
    
    b) For a more GunCon2 devices, set index (by default index=1)
    
       Example:
         -index=2
    
    c) You can see mapped GunCon2 to vjoy device 
    
    d) You can set as a mouse with -m=(width,height). You need set screen resolution
    
    e) Pressing C-Button and D-PAD directions you can recalibrate X-Axis on run-time (very useful inside games)
    
    f) Q key to exit daemon
      
 
 
 
