#!/usr/bin/env python
# file: rfcomm-client.py
# auth: Albert Huang <albert@csail.mit.edu>
# desc: simple demonstration of a client application that uses RFCOMM sockets
#       intended for use with rfcomm-server
#
# $Id: rfcomm-client.py 424 2006-08-24 03:35:54Z albert $

from bluetooth import *
from global_logger import logger 
import sys
import time
import random # for getMid()
import threading
import logging 
import gobject

# REC_TIMEOUT = 0.1 # Sec 
WAIT_AWK_MAX_TIME = 3 # sec 
MAX_RESEND_TIMES = 6 # times 
START_CHAR = '['
END_CHAR = ']'
KEEPALIVE = 2 # sec ping,pong every 2 sec , 
# recbufDir = dict() # key: "MID"  , value ,payload  # TODO infinitly expand 
recbufList  = [] # [mid  ,  msg_type , content ]
recAwkDir = dict() # key: "MID" , value "AWK"

class SEND_AGENT(object):
    def __init__(self, bl_obj, payload, mid, qos = 1):
        self.payload  = payload 
        self.bl_obj = bl_obj
        self.mid = mid 
        self.is_awk = False
        self.qos = qos 
        # self.logger = logger
        #
        if qos == 1 : 
            self.send_thread = threading.Thread(target = self.send_target) # Client sock ????
            self.send_thread.start()
        elif qos == 0 : 
            self.send_thread = threading.Thread(target = self.send_no_trace) # Client sock ????
            self.send_thread.start()
        #
        
    def send_no_trace(self) : # QOS0 # PING PONG , AWK
        for i in range(MAX_RESEND_TIMES):
            if not self.bl_obj.is_connect:
                self.bl_obj.logger.info("[BLUETOOTH] Lost connection, Give up sending " + self.payload)
                return 
            try: 
                self.bl_obj.logger.info("[BLUETOOTH] Sending " + self.payload + "(" + self.mid + ")")
                self.bl_obj.sock.send( '['+self.payload+',mid'+ self.mid+']')
            except Exception as e : 
                self.bl_obj.logger.error("[BLUETOOTH] BluetoothError: " + str(e) )
                self.bl_obj.logger.error("[BLUETOOTH] Urge disconnected by send exception, when sending " + self.payload)
                self.bl_obj.is_connect = False 
                return 
            else: 
                self.is_awk = True 
                return 
        self.bl_obj.logger.error ("[BLUETOOTH] Fail to Send After trying " + str(MAX_RESEND_TIMES) + " times. Abort." )

    def send_target(self):
        global recAwkDir
        for i in range(MAX_RESEND_TIMES):
            if not self.bl_obj.is_connect:
                self.bl_obj.logger.info("[BLUETOOTH] Lost connection, Give up sending " + self.payload)
                return 
            #------ Send message -------#  # TODO 
            try: 
                self.bl_obj.logger.info("[BLUETOOTH] Sending: " + self.payload + "(" + self.mid + ")") # totally non-blocking even if disconnect
                self.bl_obj.sock.send( '['+self.payload+',mid'+ self.mid+']')
            except Exception as e :
                self.bl_obj.logger.error("[BLUETOOTH] BluetoothError: " + str(e) )
                self.bl_obj.logger.error("[BLUETOOTH] Urge disconnected by send exception, when sending " + self.payload)
                self.bl_obj.is_connect = False 
                return 
                # self.logger.error ("[BLUETOOTH] send_target() : "+ str(e) + ". Retry " + str(i) + "/" + str(MAX_RESEND_TIMES) ) 
                # time.sleep (1)
            else: 
                t_start = time.time() 
                while time.time() - t_start < WAIT_AWK_MAX_TIME: 
                    ans = recAwkDir.pop(self.mid, "not match") # Pop out element, if exitence 
                    #ans  = "not match"
                    #for i in range(len(recbufList)): 
                    #    if recbufList[i][0] == self.mid:
                    #        ans = recbufList.pop(i) # Msg_type 
                    #        break 
                    if ans != "not match": # Get AWK 
                        self.bl_obj.logger.info("[BLUETOOTH] Get AWK (" + self.mid + ")")
                        self.is_awk = True 
                        break
                    else: # Keep waiting 
                        pass 
                        # print ('[is_send_awk] MID NOT FOUND ')
                        # self.is_awk = False 
                    time.sleep (0.05)
            
                if self.is_awk : 
                    return 
                else: 
                    self.bl_obj.logger.warning("[BLUETOOTH] Need to resend "+ self.payload +" (" + str(i) + "/" + str(MAX_RESEND_TIMES) + ", "+ self.mid +")")
                    time.sleep(1) # for rest 
        self.bl_obj.logger.error ("[BLUETOOTH] Fail to Send After trying " + str(MAX_RESEND_TIMES) + " times. Abort." )



class BLUE_COM(object): # PING PONG TODO 
    def __init__(self, logger, BT_cmd_CB):
        # -------- Connection --------# 
        self.is_connect = False
        self.sock = None # Communicate sock , not server socket 
        self.recv_thread = None 
        self.engine_thread = None 
        self.is_engine_running = False  
        self.server_sock = None  # Only for Server 
        self.keepAlive_count = None 
        self.ping_count = None 
        #-------- For Recevied -------# 
        # self.recbufArr = []
        self.logger = logger 
        self.BT_cmd_CB  = BT_cmd_CB
        # self.tid_counter = 0
    
    def server_engine_start(self, port = 3): # Totolly blocking function 
        self.server_sock=BluetoothSocket(RFCOMM)
        self.server_sock.bind(("",port))
        self.server_sock.listen(1)

        self.is_engine_running = True 
        self.engine_thread = threading.Thread(target = self.server_engine, args=(port,))
        self.engine_thread.start()

    def server_engine_stop(self):
        self.is_connect = False 
        self.is_engine_running = False 
        try:
            self.logger.info("[BLUETOOTH] Waiting server thread to join...")
            self.engine_thread.join(10)
        except : 
            self.logger.error("[BLUETOOTH] Fail to join server thread.")
        
        try:
            self.logger.info("[BLUETOOTH] Waiting recv thread to join...")
            self.recv_thread.join(10)
        except : 
            self.logger.error("[BLUETOOTH] Fail to join recv thread.")
        
        try: 
            self.close(self.server_sock) # Server socket close 
        except : 
            self.logger.error("[BLUETOOTH] Fail to close socket.")
        
        self.logger.info("[BLUETOOTH] server engine stop ")
    '''
    def incoming_connection(self):
        self.logger.debug("[BLUETOOTH] Waiting for connection on RFCOMM channel %d" % 3)
        client_sock, client_info = self.sock.accept() # Blocking 
        self.client_sock = client_sock
        self.logger.info("[BLUETOOTH] Accepted connection from "+  str(client_info))
        self.is_connect = True 
        self.keepAlive_count = time.time() 
        
        self.recv_thread = threading.Thread(target = self.recv_engine, args=(client_sock,))
        self.recv_thread.start()
    '''
    
    def server_engine (self, port): # ToTally Blocking 
        global recbufList
        #client_sock.settimeout(1)
        # try:
        if True : 
            while self.is_engine_running: # Durable Server
                #---------
                #print "Before"
                # gobject.io_add_watch(self.sock, gobject.IO_IN, self.incoming_connection)
                # print "AFter "
                if self.is_connect : 
                    #----  Check KeepAlive ------# 
                    if recbufList != []:
                        msg = recbufList.pop(0) # FIFO
                        if   msg[1] == 'DISCONNECT': # Close connection with  client 
                            self.close(self.sock)
                        elif msg[1] == 'PING':
                            self.logger.info("[BLUETOOTH] Get PING  ")
                        elif msg[1] == 'CMD':
                            self.logger.info("[BLUETOOTH] Get cmd ") 
                        else: 
                            self.logger.error("[BLUETOOTH] Unresconized cmd: " + msg[1]) 
                    else:
                        self.logger.debug ("nothing to do ")
                    
                else: # Need to Reconnect 
                    self.logger.debug("[BLUETOOTH] Waiting for connection on RFCOMM channel %d" % port)
                    self.server_sock.settimeout(10)
                    try: 
                        client_sock, client_info = self.server_sock.accept() # Blocking for 10 sec
                    except BluetoothError as e:
                        if e.args[0] == 'timed out':
                            self.logger.debug("[BLUETOOTH] Timeout." )
                        else:
                            self.logger.error("[BLUETOOTH] BluetoothError: " + str(e) )
                    else: 
                        self.sock = client_sock
                        self.logger.info("[BLUETOOTH] Accepted connection from "+  str(client_info))
                        self.is_connect = True 
                        self.keepAlive_count = time.time() 
                        
                        self.recv_thread = threading.Thread(target = self.recv_engine) # , args=(self.sock,))
                        self.recv_thread.start()
                        #connection_threading  = threading.Thread(target = self.incoming_connection)
                        #connection_threading.start()
                        #print "Before "
                        #connection_threading.join(10) # Blocking for 10 sec 
                        #print "After "
                time.sleep(0.1) 
                # TODO 
                #self.logger.warning("[BLUETOOTH] Disconnection from " + str(client_info) + "Stop recv thread.")
                #self.recv_thread.join()
        # except IOError:
        # xcept: 
        else: 
            self.logger.error("[BLUETOOTH] Something wrong at server_engine.")
        self.logger.info("[BLUETOOTH] END of server_engine")
            # print ("IOERROR!!!")
            # print("[main] disconnected from " + str(client_info))
        
        # client_sock.close()
    
    def client_engine_start(self):
        self.is_engine_running = True 
        self.engine_thread = threading.Thread(target = self.client_engine)
        self.engine_thread.start()
    
    def client_engine_stop(self):
        self.client_disconnect() # Block for 3 sec to send DISCONNECT to server . 
        self.is_connect = False
        self.is_engine_running = False
        try:
            self.logger.info("[BLUETOOTH] Waiting server thread to join...")
            self.engine_thread.join(10)
        except : 
            self.logger.error("[BLUETOOTH] Fail to join server thread.")
        
        try:
            self.logger.info("[BLUETOOTH] Waiting recv thread to join...")
            self.recv_thread.join(10)
        except : 
            self.logger.error("[BLUETOOTH] Fail to join recv thread.")
        
        try: 
            self.close(self.sock)
        except : 
            self.logger.error("[BLUETOOTH] Fail to close socket.")
        self.logger.info("[BLUETOOTH] server engine stop ")
    
    
    def client_engine(self):
        while self.is_engine_running: 
            if self.is_connect: 
                # ------- PING PONG -------# Keep alive 
                if time.time() - self.keepAlive_count >= KEEPALIVE * 1.5 : # Give up connection
                    self.is_connect = False 
                    self.logger.warning ("[BLUETOOTH] Disconnected, because KEEPAVLIE isn't response. (PING, PONG)")
                # TODO TODO TODO 
                elif  time.time() - self.ping_count >= KEEPALIVE: # Only for client to send "PING"
                    self.send('PING', 0)
                    self.ping_count = time.time()
                    # SEND_AGENT(self.sock, 'PING', self.getMid(), self.logger, 0)
                    # self.sock.send('[PING,mid'+ self.getMid()+']')
                #------- Check List --------# 
                if recbufList != []: # Something to do 
                    msg = recbufList.pop(0)
                    self.BT_cmd_CB(msg)
            else: 
                # logger.info("[client_engine] Reconnected.")
                self.client_connect('B8:27:EB:51:BF:F5', 3)
            time.sleep(0.1)
    

    def client_connect  (self, host = 'B8:27:EB:51:BF:F5', port = 3):
        '''
        Only for client socket 
        '''
        self.logger.info("[BLUETOOTH] connecting to " + host)
        ts = time.time()
        # Create the client socket
        self.sock=BluetoothSocket(RFCOMM)
        # self.sock.settimeout(10) # Timeout 10 sec  # TODO This will cause the bug 
        try: 
            self.sock.connect((host, port)) # What if can't connected TODO
        except BluetoothError as e:
            if e.args[0] == 'timed out':
                self.logger.debug("[BLUETOOTH] Connection Timeout 10 sec ." )
            else:
                self.logger.error("[BLUETOOTH] Not able to Connect, BluetoothError: " + str(e) )
            rc = False 
        else : 
            rc = True 
            self.is_connect = True 
            self.keepAlive_count = time.time()
            self.ping_count = time.time()
            self.logger.info("[BLUETOOTH] connected. Spend " + str(time.time() - ts) + " sec.") #Link directly, Faster ????? TODO 

            self.recv_thread = threading.Thread(target = self.recv_engine)# , args=(self.sock,))  # (self.sock))
            self.recv_thread.start()
        return rc 


    def client_disconnect(self): # Normally disconnect  # Only from client -> server 
        if self.is_connect: 
            rc = self.send("DISCONNECT", 1)
            t_s = time.time() 
            while not rc.is_awk:    
                if time.time() - t_s  > 3 : # Only wait 3 sec
                    self.logger.warning ("[BLUETOOTH] Fail to send DISCONNECT in 3 sec.") 
                    break
            self.close(self.sock)  # Close youself. 
        else: 
            self.logger.warning ("[BLUETOOTH] No need for disconnect, Connection already lost.")

    def close(self, socket): 
        # if self.sock != None:
        try: 
            self.is_connect = False 
            if self.recv_thread.is_alive():
                self.logger.info ("[BLUETOOTH] waiting join recv_threading ")
                self.recv_thread.join()
                # print ("[close] waiting join recv_threading ")
            self.logger.info ("[BLUETOOTH] close socket")
            socket.close() 
            socket = None 
        # else: 
        except : 
            self.logger.error ("[close] Can't close.")
    
    def getMid(self):
        '''
        return A(65)~Z(90) in sequence
        '''
        output = "" 
        for i in range(4) : 
            output += chr(random.randint(0,25) + 65)
        return output

    def send (self, payload, qos = 1, mid = None):
        '''
        Inptu : payload need to be STring
        Definetly nonblocking send.
        return mid 
        '''
        if mid == None : 
            mid = self.getMid()
        return SEND_AGENT(self, payload, mid, qos)

    def recv_engine(self): # Totolly -blocking  TODO  # Only block when something is need to recv , MAX BLOCK time is REC_TIMEOUT
        global recbufList, recAwkDir
        self.sock.settimeout(1)
        while self.is_connect:
            #---------RECV -----------# 
            try: 
                rec = self.sock.recv(1024) # Blocking for 1 sec. 
            except BluetoothError as e:
                if e.args[0] == 'timed out':
                    self.logger.debug("[BLUETOOTH] recv Timeout." )
                else:
                    self.logger.error("[BLUETOOTH] BluetoothError: " + str(e) )
                    self.logger.error("[BLUETOOTH] Urge disconnected by recv exception.")
                    self.is_connect = False 
                # print ("[recv_engine] timeout ")
                # logger.error("[EVwaitAnswer] read fail")
            else:
                self.logger.debug("rec: " + rec)
                is_valid = False 
                try:
                    #---------  Check start and end Char -------# 
                    if rec[0] == START_CHAR or rec[-1] == END_CHAR:
                        rec = rec[1:-1] # Del '[' and ']'
                        mid_str = rec[-8:]# ,midASDF
                        rec = rec[:-8] # Cut off mid 
                        #---------  Check MID --------# 
                        if mid_str[:4] != ',mid' or (not mid_str[4:].isupper()):
                            pass 
                        else: 
                            is_valid = True 
                    else: 
                        pass 
                except: 
                    is_valid = False 
                    self.logger.error ("[BLUETOOTH] recv_engine MID ERROR ")

                if is_valid: 
                    self.logger.info ("[BLUETOOTH] Received: " + rec )
                    if rec == "AWK":
                        # recbufList.append([mid_str[4:], rec , ""])
                        recAwkDir[mid_str[4:]] = rec
                    elif rec == "PING": # Server recv 
                        self.keepAlive_count = time.time()
                        # SEND_AGENT(self.sock, 'PING', self.getMid(), self.logger, 0)
                        self.send('PONG', 0, mid=mid_str[4:]) # Send the same mid with PING 
                        # self.client_sock.send( '[PONG,mid'+ self.getMid()+']')
                    elif rec == "PONG":# Client  recv 
                        self.keepAlive_count = time.time()
                    else:
                        # self.logger.debug("[BLUETOOTH] Sending AWK")
                        self.send('AWK', 0, mid = mid_str[4:])
                        # SEND_AGENT(self.sock, 'AWK',mid_str[4:] , self.logger, 0)
                        # recv_sock.send( '[AWK,mid'+mid_str[4:]+']') # Send AWK to back to sender 
                        
                        if rec == "DISCONNECT":
                            recbufList.append([mid_str[4:], rec , ""])
                        else :  # CMD
                            recbufList.append([mid_str[4:], "CMD" , rec ])
                            self.BT_cmd_CB(rec)
                else: 
                    self.logger.error("[[BLUETOOTH]] received not valid msg.")
                # ------ Reset Flag --------# 
                rec = ""
                # End of else 
            time.sleep(0.1)
            # End of while 
    '''
    def recv_engine (self, recv_sock): # Totolly -blocking  TODO  # Only block when something is need to recv , MAX BLOCK time is REC_TIMEOUT
        recv_sock.settimeout(1)
        rec_state = "waiting"
        rec = ""
        recbuf = ""
        while self.is_connect : 
            try: 
                rec = recv_sock.recv(1)# Non blocking # TODO Check for blocking
                print (rec)
            except:
                print ("[recv_engine] read fail")
                time.sleep(0.1)
                continue 
                # logger.error("[EVwaitAnswer] read fail")
            else: 
                pass 

            # -------- State Machine --------#
            # tStartWait = time.time()
            # if rec_state == "receiving": # time.time() - tStartWait < REC_TIMEOUT: # ~= 0.1 sec
                # if device.inWaiting() != 0: # Wait for ST_board answer, Should be '[H]' or '[L]'
                #----- Timeout Check -------# 
                #if time.time() - tStartWait < REC_TIMEOUT:
                #    rec_state = "timeout"
                #------ RECVEIVED--------# 
            if rec_state == "waiting":
                if rec == START_CHAR : 
                    rec_state = "receiving"
                else: 
                    print ("[Trash] rec ")
            elif rec_state == "receiving":
                if rec == END_CHAR:# is_completed
                    # rec_state = "waiting"
                    rec_state = "completed"
                elif rec == START_CHAR:
                    recbuf = ""
                else:
                    recbuf += rec
            
            
            if rec_state == "completed":
                print ("COmpleted recbuf: " + str(recbuf))
                #self.is_valid = True 
                #if self.is_valid:
                # Check mid ??!!
                try:
                    mid_str = recbuf[-8:]# ,midASDF
                    recbuf = recbuf[:-8] # Cut off mid 
                    #---------  Check MID --------# 
                    if mid_str[:4] != ',mid' or (not mid_str[4:].isupper()):
                        is_valid = False 
                    else: 
                        is_valid = True 
                except: 
                    is_valid = False 
                    print ("[recv_engine] MID ERROR ")

                if is_valid: 
                    # self.recbufArr.append(recbuf)
                    self.recbufDir[mid_str[4:]] = recbuf
                    if recbuf != "awk":
                        print ("Sending AWK")
                        recv_sock.send( '[awk,mid'+mid_str[4:]+']') # Send AWK to back to sender 
                else: 
                    print ("[recv_engine] Not Valid ")
                
                # ------ Reset Flag --------# 
                recbuf = ""
                rec_state = "waiting"
            #elif rec_state == "timeout":
            #    print ("[recv_engine] TIMEOUT !! ")
 
                
                # time.sleep(0.001) #TODO test#sleep 1ms, check device for every 1ms
                # End of receiving while
            # End of Engine while 
            time.sleep(0.001) #TODO test#sleep 1ms, check device for every 1ms 
    '''
