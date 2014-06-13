#!/usr/bin/env python
# Modified from Michael Saunby's ble-sensor-pi
# by choupi. June 2014
#
# Michael Saunby. April 2013
#
# Notes.
# pexpect uses regular expression so characters that have special meaning
# in regular expressions, e.g. [ and ] must be escaped with a backslash.
#
#   Copyright 2013 Michael Saunby
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.

import pexpect
import sys
import time
from sensor_calcs import *
import json
import select
import threading
import sqlite3
import datetime

HCIBIN='./'

def floatfromhex(h):
    t = float.fromhex(h)
    if t > float.fromhex('7FFF'):
        t = -(float.fromhex('FFFF') - t)
        pass
    return t

class SensorTag(threading.Thread):

    def __init__( self, bluetooth_adr, dbfile ):
        threading.Thread.__init__(self)
        #self.connect(bluetooth_adr)
        self.con = None
        self.db = None
        self.dbfile=dbfile
        self.addr = bluetooth_adr
        self.cb = {}
        self.data = {}
        self.barometer = None
        self.datalog = sys.stdout
        self.data['addr'] = bluetooth_adr
        self.enable=True
        return

    def __del__(self):
        self.disconnet()
        threading.Thread.__del__(self)

    def run(self):
        self.connect(self.data['addr'])
        self.db = sqlite3.connect(self.dbfile)
        self.init_cb()
        self.notification_loop()
        self.disconnect()

    def connect(self, bluetooth_adr):
        self.con = pexpect.spawn(HCIBIN+'gatttool -b ' + bluetooth_adr + ' --interactive')
        self.con.expect('\[LE\]>', timeout=60)
        print "Preparing to connect. You might need to press the side button..."
        self.con.sendline('connect')
        # test for success of connect
	self.con.expect('Connection successful.*\[LE\]>')
        # Earlier versions of gatttool returned a different message.  Use this pattern -
        #self.con.expect('\[CON\].*>')
	return

        self.con.expect('\[CON\].*>')
        self.cb = {}
        return

    def disconnect(self):
        if self.con: self.con.kill(9)

    def char_write_cmd( self, handle, value ):
        # The 0%x for value is VERY naughty!  Fix this!
        cmd = 'char-write-cmd 0x%02x 0%x' % (handle, value)
        print cmd
        self.con.sendline( cmd )
        return

    def char_read_hnd( self, handle ):
        self.con.sendline('char-read-hnd 0x%02x' % handle)
        self.con.expect('descriptor: .*? \r')
        after = self.con.after
        rval = after.split()[1:]
        return [long(float.fromhex(n)) for n in rval]

    # Notification handle = 0x0025 value: 9b ff 54 07
    def notification_loop( self ):
        while self.enable:
	    try:
              pnum = self.con.expect('Notification handle = .*? \r', timeout=4)
            except pexpect.TIMEOUT:
              print "TIMEOUT exception!"
              break
	    if pnum==0:
                after = self.con.after
	        hxstr = after.split()[3:]
            	handle = long(float.fromhex(hxstr[0]))
            	#try:
	        if True:
                  self.cb[handle]([long(float.fromhex(n)) for n in hxstr[2:]])
            	#except:
                #  print "Error in callback for %x" % handle
                #  print sys.argv[1]
                pass
            else:
              print "TIMEOUT!!"
        print '%s End'%self.data['addr']
        pass

    def register_cb( self, handle, fn ):
        self.cb[handle]=fn;
        return

    def init_cb(self):
      # enable TMP006 sensor
      self.register_cb(0x25,self.tmp006)
      self.char_write_cmd(0x29,0x01)
      self.char_write_cmd(0x26,0x0100)

      # enable accelerometer
      self.register_cb(0x2d,self.accel)
      self.char_write_cmd(0x31,0x01)
      self.char_write_cmd(0x2e,0x0100)

      # enable humidity
      self.register_cb(0x38, self.humidity)
      self.char_write_cmd(0x3c,0x01)
      self.char_write_cmd(0x39,0x0100)

      # enable magnetometer
      self.register_cb(0x40,self.magnet)
      self.char_write_cmd(0x44,0x01)
      self.char_write_cmd(0x41,0x0100)

      # enable gyroscope
      self.register_cb(0x57,self.gyro)
      self.char_write_cmd(0x5b,0x07)
      self.char_write_cmd(0x58,0x0100)

      # fetch barometer calibration
      self.char_write_cmd(0x4f,0x02)
      rawcal = self.char_read_hnd(0x52)
      self.barometer = Barometer( rawcal )
      # enable barometer
      self.register_cb(0x4b,self.baro)
      self.char_write_cmd(0x4f,0x01)
      self.char_write_cmd(0x4c,0x0100)

    def tmp006(self,v):
        objT = (v[1]<<8)+v[0]
        ambT = (v[3]<<8)+v[2]
        targetT = calcTmpTarget(objT, ambT)
        self.data['t006'] = targetT
        self.db.execute('INSERT INTO SensorTagData VALUES(?,?,?,?,?)', ('fff',self.addr,datetime.datetime.now(),'T006',targetT))
        self.db.commit()
        print "T006 %.1f" % targetT

    def accel(self,v):
        (xyz,mag) = calcAccel(v[0],v[1],v[2])
        self.data['accl'] = xyz
        out=' '.join(map(str,xyz))
        self.db.execute('INSERT INTO SensorTagData VALUES(?,?,?,?,?)', ('fff',self.addr,datetime.datetime.now(),'ACCL',out))
        self.db.commit()
        print "ACCL", xyz

    def humidity(self, v):
        rawT = (v[1]<<8)+v[0]
        rawH = (v[3]<<8)+v[2]
        (t, rh) = calcHum(rawT, rawH)
        self.data['humd'] = [t, rh]
        self.db.execute('INSERT INTO SensorTagData VALUES(?,?,?,?,?)', ('fff',self.addr,datetime.datetime.now(),'HUMD',rh))
        self.db.commit()
        print "HUMD %.1f" % rh

    def baro(self,v):
        rawT = (v[1]<<8)+v[0]
        rawP = (v[3]<<8)+v[2]
        (temp, pres) =  self.data['baro'] = self.barometer.calc(rawT, rawP)
        print "BARO", temp, pres
        self.data['time'] = long(time.time() * 1000);
        # The socket or output file might not be writeable
        # check with select so we don't block.
        #(re,wr,ex) = select.select([],[datalog],[],0)
        #if len(wr) > 0:
        #    datalog.write(json.dumps(self.data) + "\n")
        #    datalog.flush()
        #    pass

    def magnet(self,v):
        x = (v[1]<<8)+v[0]
        y = (v[3]<<8)+v[2]
        z = (v[5]<<8)+v[4]
        xyz = calcMagn(x, y, z)
        self.data['magn'] = xyz
        out=' '.join(map(str,xyz))
        self.db.execute('INSERT INTO SensorTagData VALUES(?,?,?,?,?)', ('fff',self.addr,datetime.datetime.now(),'MAGN',out))
        self.db.commit()
        print "MAGN", xyz

    def gyro(self,v):
        x = (v[1]<<8)+v[0]
        y = (v[3]<<8)+v[2]
        z = (v[5]<<8)+v[4]
        xyz = calcMagn(x, y, z)
        out=' '.join(map(str,xyz))
        self.db.execute('INSERT INTO SensorTagData VALUES(?,?,?,?,?)', ('fff',self.addr,datetime.datetime.now(),'GYRO',out))
        self.db.commit()
        print "GYRO", xyz

def main():
    bluetooth_adr = sys.argv[1]
    tag = SensorTag(bluetooth_adr)
    tag.start()
    time.sleep(10)
    print '@@@@'
    tag.enable=False
    tag.join()

#    #data['addr'] = bluetooth_adr
#    if len(sys.argv) > 2:
#        datalog = open(sys.argv[2], 'w+')
#
#    while True:
#     try:   
#      print "[re]starting.."
#
#      cbs = SensorCallbacks(bluetooth_adr)
#
#      # enable TMP006 sensor
#      tag.register_cb(0x25,cbs.tmp006)
#      tag.char_write_cmd(0x29,0x01)
#      tag.char_write_cmd(0x26,0x0100)
#
#      # enable accelerometer
#      tag.register_cb(0x2d,cbs.accel)
#      tag.char_write_cmd(0x31,0x01)
#      tag.char_write_cmd(0x2e,0x0100)
#
#      # enable humidity
#      tag.register_cb(0x38, cbs.humidity)
#      tag.char_write_cmd(0x3c,0x01)
#      tag.char_write_cmd(0x39,0x0100)
#
#      # enable magnetometer
#      tag.register_cb(0x40,cbs.magnet)
#      tag.char_write_cmd(0x44,0x01)
#      tag.char_write_cmd(0x41,0x0100)
#
#      # enable gyroscope
#      tag.register_cb(0x57,cbs.gyro)
#      tag.char_write_cmd(0x5b,0x07)
#      tag.char_write_cmd(0x58,0x0100)
#
#      # fetch barometer calibration
#      tag.char_write_cmd(0x4f,0x02)
#      rawcal = tag.char_read_hnd(0x52)
#      barometer = Barometer( rawcal )
#      # enable barometer
#      tag.register_cb(0x4b,cbs.baro)
#      tag.char_write_cmd(0x4f,0x01)
#      tag.char_write_cmd(0x4c,0x0100)
#
#      tag.notification_loop()
#     except:
#      pass

if __name__ == "__main__":
    main()

