#!/usr/bin/env python
# choupi. June 2014

from flask import Flask
from flask import g
from threading import Thread
import sensortag
import time
import math
import sqlite3
import json

global app_data

app = Flask(__name__)

def get_threads():
    if 'threads' not in app_data:
        app_data['threads'] = {}
    return app_data['threads']

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(app_data['dbfile'])
    return db

def check_env():
    cur=get_db().cursor()
    cur.execute('SELECT data FROM SensorTagData WHERE handle="%s" ORDER BY ts DESC LIMIT 20'%('T006'))
    dataT=[r[0] for r in cur.fetchall() if float(r[0])>30 or float(r[0])<22]
    cur.execute('SELECT data FROM SensorTagData WHERE handle="%s" ORDER BY ts DESC LIMIT 20'%('HUMD'))
    dataT+=[r[0] for r in cur.fetchall() if float(r[0])>80 or float(r[0])<40]
    return 15-len(dataT)

def check_brake():
    cur=get_db().cursor()
    cur.execute('SELECT data FROM SensorTagData WHERE handle="%s" ORDER BY ts DESC LIMIT 20'%('ACCL'))
    dataT=[]
    for r in cur.fetchall():
        sr=r[0].strip().split()
        if float(sr[0])>1.0: dataT.append(sr[0])
    return 15-len(dataT)

def check_startoff():
    cur=get_db().cursor()
    cur.execute('SELECT data FROM SensorTagData WHERE handle="%s" ORDER BY ts DESC LIMIT 20'%('ACCL'))
    dataT=[]
    for r in cur.fetchall():
        sr=r[0].strip().split()
        if float(sr[0])<1.0: dataT.append(sr[0])
    return 15-len(dataT)

def check_turn():
    cur=get_db().cursor()
    cur.execute('SELECT data FROM SensorTagData WHERE handle="%s" ORDER BY ts DESC LIMIT 20'%('ACCL'))
    dataT=[]
    for r in cur.fetchall():
        sr=r[0].strip().split()
        if math.fabs(float(sr[1]))>1.0: dataT.append(sr[1])
    return 15-len(dataT)

def check_road():
    cur=get_db().cursor()
    cur.execute('SELECT data FROM SensorTagData WHERE handle="%s" ORDER BY ts DESC LIMIT 20'%('ACCL'))
    dataT=[]
    for r in cur.fetchall():
        sr=r[0].strip().split()
        if math.fabs(float(sr[2]))>1.0: dataT.append(sr[2])
    return 15-len(dataT)

@app.route('/')
def hello_world():
    return 'Hello World!'

@app.route('/threads')
def countthread():
    ta = get_threads()
    return ' '.join([str(ta[t].ident) for t in ta])

@app.route('/datas')
def newdatas():
    db=get_db()
    cur=db.cursor()
    cur.execute('SELECT ts,handle,data FROM SensorTagData ORDER BY ts DESC LIMIT 1')
    r=cur.fetchone()
    return r

@app.route('/data/RADAR')
def get_data_radar():
    dataR=[[{"axis":"environment", "value": check_env()}, 
        {"axis":"brake", "value": check_brake()},
        {"axis":"start off", "value": check_startoff()}, 
        {"axis":"road quality", "value": check_road()},
        {"axis":"turning", "value": check_turn()}
    ]]
    return json.dumps(dataR)

@app.route('/data/ACCL')
def get_data_ACCL():
    cur=get_db().cursor()
    cur.execute('SELECT data FROM SensorTagData WHERE handle="%s" ORDER BY ts DESC LIMIT 20'%('ACCL'))
    dataA=[[],[],[]]
    for r in cur.fetchall():
        rl=map(math.fabs,map(float,r[0].split()))
        for i in xrange(0,3): dataA[i].append(rl[i])
    dataA.reverse()
    return json.dumps({'data':dataA})

@app.route('/data/TMHM')
def get_data_TMHM():
    cur=get_db().cursor()
    cur.execute('SELECT data FROM SensorTagData WHERE handle="%s" ORDER BY ts DESC LIMIT 20'%('T006'))
    dataT=[]
    for r in cur.fetchall():
        dataT.append(float(r[0]))
    cur.execute('SELECT data FROM SensorTagData WHERE handle="%s" ORDER BY ts DESC LIMIT 20'%('HUMD'))
    dataH=[]
    for r in cur.fetchall():
        dataH.append(float(r[0]))
    dataT.reverse()
    dataH.reverse()
    return json.dumps({'dataT':dataT, 'dataH':dataH})

@app.route('/sensortag/start/<ble_addr>')
def sensortag_start(ble_addr):
    ta = get_threads()
    st = sensortag.SensorTag(ble_addr, app_data['dbfile'])
    st.start()
    ta[ble_addr]=st
    return ble_addr

@app.route('/sensortag/stop/<ble_addr>')
def sensortag_stop(ble_addr):
    ta = get_threads()
    if ble_addr not in ta: return 'Not found'
    ta[ble_addr].enable=False
    ta[ble_addr].join()
    return ble_addr

if __name__ == '__main__':
    app_data={}
    app_data['dbfile']='s.db'
    app.run(host='0.0.0.0', port=8080, debug=True)
