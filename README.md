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
         
    b) You can see mapped GunCon2 to vjoy device   
    
    c) With Ctrl+C for exit daemon 
      
 
TO DO:
 * Mouse simulation
 * Update libusb when async works on it. Probably speed up some frames.
 
