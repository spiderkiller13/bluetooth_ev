#!/usr/bin/env python

from bluetooth_template import BLUE_COM
from global_logger import logger
import signal 
import time 

is_running = True
def sigint_handler(signum, frame):
    global is_running
    is_running = False
    logger.warning('[sigint_handler] catched interrupt signal!')
signal.signal(signal.SIGINT, sigint_handler)
signal.signal(signal.SIGHUP, sigint_handler)
signal.signal(signal.SIGTERM, sigint_handler)

WAIT_AWK_MAX_TIME = 20 # sec 

blue_com = BLUE_COM(logger)
    

# blue_com.connect('B8:27:EB:51:BF:F5', 3)

while is_running: 
    if blue_com.is_connect: 
        
        sa = blue_com.send("hello world")
        ts = time.time()
        while time.time() - ts < WAIT_AWK_MAX_TIME: 
            if sa.is_awk : # pop out 
                break
            else:
                time.sleep(0.1)
        
        
    else: 
        logger.info("[Main] Reconnected.")
        blue_com.connect('B8:27:EB:51:BF:F5', 3)
    time.sleep(1)


print ("[Main] DISCONNECT ")
blue_com.disconnect() 







