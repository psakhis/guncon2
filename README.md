# guncon2
GunCon2 daemon for Windows

This project is based on sonik-br work https://github.com/sonik-br/GunconUSB

With a daemon and their winusb driver, is possible to connect GunCon2 as vjoy joystick 

Install
 1) Install VJoy - https://sourceforge.net/projects/vjoystick/
 2) Install GunCon2 Driver - https://github.com/sonik-br/GunconUSB
 
 Setup
 1) Calibration tool to obtain x and y ABS. This can be innacurate. Do with 320x240 resolution
 2) Run daemon (-tray=1 if you want tray icon on status bar)
 
    a) By default, daemon runs on x and y ABS settings, you can provide other with args
    
       Example:
         -x=(175,720) -y=(9,249)
    
    b) For a more GunCon2 devices, set index (by default index=1)
    
       Example:
         -index=2
    
    c) You can see mapped GunCon2 to vjoy device 
    
    d) You can set as a mouse with -m=1
    
    e) You can enable internal flasher with -f=n, where n are number of frames. If enabled daemon sends to vjoy/mouse only when flashing
    
    f) If flasher is enabled, brightness setting can be customized with -b=[1-128]
    
    g) If flasher is enabled, delay setting can be customized with -d=n, where n are number of frames to delay input. 
    
    h) Pressing C-Button and D-PAD directions you can recalibrate X-Axis on run-time (very useful inside games)
      - Example 1: Your gun is shooting outside on left  --> C-Button + D-PAD Left to decrase x-min absis 
      - Example 2: Your gun is shooting outside on right --> C-Button + D-PAD Up to increase x-max absis 
    
    i) Offscreen option. -o=1,2,3 for A,B or C. Switch trigger with this button when shooting out of screen.       
    
    j) Q key to exit daemon
      
 
 TO DO
   - Tray icon
 
