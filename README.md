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
    
    d) You can set as a mouse with -m=1
    
    e) You can enable internal flasher with -f=n, where n are number of frames
    
    f) If flasher is enabled, brightness setting can be customized with -b=[0-300]
    
    g) Pressing C-Button and D-PAD directions you can recalibrate X-Axis on run-time (very useful inside games)
      - Example 1: Your gun is shooting outside on left  --> C-Button + D-PAD Left to decrase x-min absis 
      - Example 2: Your gun is shooting outside on right --> C-Button + D-PAD Up to increase x-max absis 
      
    i) Q key to exit daemon
      
 
 
 
