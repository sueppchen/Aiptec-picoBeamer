#!/usr/bin/env python2

# send picture over USB to Aiptek Picobeamer
# original 1de1:1101 
# modeswitch send(hex) 5553 4243 6858 2784 0000 0000 0000 10ff 0200 0000 0000 0000 0000 0000 0000 00
#                       U S  B C  h X  
# video-device 08ca:2145 endpoint 04 
# init:

# devinfo anfrage:           vvvv| 
# Host-> USB: 0100 0000 0000 a475 0000 0000 0000 0000 0000 0000 0000 0000

# dev info antwort      vvvv     | weite    hoehe     unbekannt unbekannt
# USB-->Host: 0100 0000 0110 0000 6003 0000 e001 0000 0000 0000 0000 0000
#             0100 0000 dev info: 864px     480px 

# I send you a picture...
# Host-> USB: 0200 0000 0010 9060 | 0100 0000 | 6003 0000         | e001 0000         | 3850 0000  
#             02 = image Format,     Format 1 | 60:03:00:00 864px | e0:01:00:00 480px | 38:50:00:00 = size of next frame complete

# Frame:
# USB-->Host: jpg 864 x 480 px mit header komplett
# Host-> USB: 0200 0000 0010 9060 0100 0000 6003 0000 e001 0000 89c2 0000 
# buffer size 864x480x3

#image-options
#jfif Version 1.1, 
# Pixel/cm = 0x0046 / 0x0046
#thumbnail = 0 * 0 Px
#dct
#dht


import os
import sys
import usb.core                 # https://walac.github.io/pyusb/
import time

from screeninfo import get_monitors        #size of monitor
import subprocess as sp

import numpy as np
import cv2
from mss import mss
from PIL import Image, ImageDraw, ImageFont, ImageOps
import pyscreenshot as ImageGrab

import math

import io

import colorsys

mon = {'left': 10, 'top': 10, 'width': 864, 'height': 480}
#destination = "frame1.jpg"
output_net = Image.open('huffmann.jpg')
ss_region = (10, 10, 864, 480)


VENDOR_MASS = 0x1de1
PRODUCT_MASS =  0x1101

VENDOR_BEAM = 0x08ca
PRODUCT_BEAM =  0x2145

CONFIGURATION_MASS = 1       # 1-based
INTERFACE_MASS = 0           # 0-based
SETTING_MASS = 0             # 0-based
ENDPOINT_MASS = 1            # 0-based

CONFIGURATION_BEAM = 1       # 1-based
INTERFACE_BEAM = 0           # 0-based
SETTING_BEAM = 0             # 0-based
ENDPOINT_BEAM = 1            # 0-based

switch_command = b'USBChX\'\x84\0\0\0\0\0\0\x10\xff\2\0\0\0\0\0\0\0\0\0\0\0\0\0\0'

frame0 = "frame.jpg"
frame1 = "frame1.jpg"
frame2 = "frame2.jpg"
frame3 = "frame3.jpg"

def hsv2rgb(h,s,v):
    return tuple(round(i * 255) for i in colorsys.hsv_to_rgb(h,s,v))


def picoSwitch():
    # To send commands, we need an Endpoint.
    
    print("switch")
    #mass-storrage-Mode --> switch
    device = usb.core.find(idVendor=VENDOR_MASS, idProduct=PRODUCT_MASS)

    if device is not None:
        print("Found projector in mass-storrage-mode ... switching")
        if device.is_kernel_driver_active(INTERFACE_MASS):
            print("Detaching kernel driver")
            device.detach_kernel_driver(INTERFACE_MASS)
        configuration = device.get_active_configuration()
        interface = configuration[(INTERFACE_MASS, SETTING_MASS)]
        endpoint = interface[ENDPOINT_MASS]
        endpoint.write(switch_command)
        time.sleep(0.3)
        
    else:
        print("not found... already switched?")

#def picoInit():

    # reset
    print("reset!")

    device = usb.core.find(idVendor=VENDOR_BEAM, idProduct=PRODUCT_BEAM)

    if device is None:
        print("Is the projector connected and turned on?")
        sys.exit(1)

    if device.is_kernel_driver_active(INTERFACE_BEAM):
        print("Detaching kernel driver")
        device.detach_kernel_driver(INTERFACE_BEAM)

    configuration = device.get_active_configuration()
    interface = configuration[(INTERFACE_BEAM, SETTING_BEAM)]
    endpoint = interface[ENDPOINT_BEAM]
    print(endpoint)
    
#    endpoint.write(switch_command)
    time.sleep(0.3)
    
    beam_init_a = [0x01, 0x00, 0x00, 0x00,   #message-type = system
                   0x00, 0x00, 0xa4, 0x75,   
                   0x00, 0x00, 0x00, 0x00, 
                   0x00, 0x00, 0x00, 0x00, 
                   0x00, 0x00, 0x00, 0x00,
                   0x00, 0x00, 0x00, 0x00]
    beam_init = bytearray(beam_init_a)
    print(beam_init)
    
    import array
    #packet = array.array('B', [ord(c) for c in "hello World"])          # text --> List
    
    beam_init = b'\x01\x00\x00\x00\x00\x00\xa4\x75\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
    #beam_nextframe = b'\2\0\0\0\0\x10\x90\x60\1\0\0\0\x60\3\0\0\xe0\1\0\0'
    #print(packet)

    #print (' '.join(hex(ord(x))[2:] for x in beam_init))

    #dev ask size
 
    device.write(0x04, beam_init)
#    endpoint.write(beam_init)

    #USB-->Host: 0100 0000 0110 0000 6003 0000 e001 0000 0000 0000 0000 0000
    response = device.read(0x84,   24)
    if (response[0] == 0x01 ):
        hsize = (response[11] << 24 ) + (response[10] << 16 ) + (response[9] << 8 ) + response[8]
        vsize = (response[15] << 24 ) + (response[14] << 16 ) + (response[13] << 8 )+ response[12]
        dest_size = str(hsize)+"x"+str(vsize)
        #0200 0000 0010 9060 | 0100 0000 | 6003 0000         | e001 0000         |
        nextframe_h=[0x02,0x00,0x00,0x00,                                     #message-type = image header
                     0x00,0x10,0x90,0x60,                                     #? =
                     0x01,0x00,0x00,0x00,                                     #file-format = jpg
                     response[8],  response[9],  response[10], response[11],  #hsize
                     response[12], response[13], response[14], response[15]]  #vsize
        beam_nextframe = bytes( nextframe_h)
    

    #gespeicherten Frame oeffnen und ausgeben
    with open(frame1, "rb") as datei:
        frame = datei.read()
        print(type(frame))

    fnt = ImageFont.truetype("/usr/share/fonts/truetype/freefont/FreeMono.ttf", 28, encoding="unic")
    
    def drawClock(rotation, H,M,S, malen, bild):
        rotation += 1
        hLength = 160                 #66%
        hThick = 8                    # in Pixels
        hColor = 20                   # color Wheel 0- 359
        mLength = 200                 #80%
        mThick = 4                    # in Pixels
        mColor = 100                   # color Wheel 0- 359
        sLength = 220                 #90%
        sThick = 1                    # in Pixels
        sColor = 200                   # color Wheel 0- 359

        for num in range(1,13):
            AngleRadians = (3.14156295 / 180.0) * ((num % 12) * 30 + rotation * 90)   
            x1 = 434 - math.cos(AngleRadians) * 232
            y1 = 242 - math.sin(AngleRadians) * 232

            
            img_txt = Image.new('L', fnt.getsize( str(num)))
            draw_txt = ImageDraw.Draw(img_txt)
            draw_txt.text((0,0), str(num), 'white' ,font=fnt)
            
            w = img_txt.rotate(rotation * 90, expand=1)
            bild.paste( w, (x1-16, y1-16))
#            bild.paste( ImageOps.colorize(w, (0,0,0), (255,255,84)), (x1-16, y1-16),w)
            
        
        #h
        hAngle = ((H % 12) * 30) + (M // 2) 
        hAngleRadians = (3.14156295 / 180.0) * (hAngle + rotation * 90)   
        x1 = 434 - math.cos(hAngleRadians) * hLength
        y1 = 242 - math.sin(hAngleRadians) * hLength
        x2 = 430 + math.cos(hAngleRadians) * (hLength / 10)
        y2 = 238 + math.sin(hAngleRadians) * (hLength / 10)
        malen.line((x1, y1, x2, y2), fill=hsv2rgb(hColor/360,1.0,1.0), width=hThick)

        #m
        mAngle = (M * 6) + (S // 10) 
        mAngleRadians = (3.14156295 / 180.0) * (mAngle + rotation * 90)  
        x1 = 434 - math.cos(mAngleRadians) * mLength
        y1 = 242 - math.sin(mAngleRadians) * mLength
        x2 = 430 + math.cos(mAngleRadians) * (mLength / 10)
        y2 = 238 + math.sin(mAngleRadians) * (mLength / 10)
        malen.line((x1, y1, x2, y2), fill=hsv2rgb(mColor/360,1.0,1.0), width=mThick)

        #s
        sAngle = (S * 6) 
        sAngleRadians = (3.14156295 / 180.0) * (sAngle + rotation * 90)
        x1 = 434 - math.cos(sAngleRadians) * sLength
        y1 = 242 - math.sin(sAngleRadians) * sLength
        x2 = 430 + math.cos(sAngleRadians) * (sLength / 10)
        y2 = 238 + math.sin(sAngleRadians) * (sLength / 10)
        malen.line((x1, y1, x2, y2), fill=hsv2rgb(sColor/360,1.0,1.0), width=sThick)

    #in den Loop    
    sekunde = 0
    minute = 0
    stunde = 0
    width = 864
    hight = 480
    while True:
        
        sekunde += 1
        
        if sekunde > 59:
            sekunde = 0
            minute += 1

        if minute > 59:
            minute = 0
            stunde += 1

        if stunde > 11:
            stunde = 0

        ss_img = Image.new('RGB', (width,hight), (0,0,0))

        # Make into Numpy array so we can use OpenCV drawing functions
        draw = ImageDraw.Draw(ss_img)
        
        drawClock(2,stunde,minute,sekunde, draw, ss_img)

        buff = io.BytesIO()
        ss_img.save(buff, 
             format='jpeg', 
             dpi=(0x46,0x46),
             subsampling=2,
             qtables=output_net.quantization 
             )
        
        frame = buff.getvalue()
        
#        print(type(frame))
        framesize = len(frame)

        framesize_h = [ framesize        & 0xFF ,
                       (framesize >>  8) & 0xFF ,
                       (framesize >> 16) & 0xFF , 
                       (framesize >> 24) & 0xFF ]

        device.write(0x04,beam_nextframe + bytes(framesize_h))          #endpoint, content
        device.write(0x04,frame)
        
        cv2.imshow('test', np.array(ss_img))
        if cv2.waitKey(33) & 0xFF in ( ord('q'),  27,  ):
            break
    
    device.reset()
    
picoSwitch()
#picoInit()
#ev3_write(0)
