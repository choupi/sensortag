#!/usr/bin/env python
# choupi. June 2014

from flask import Flask
from flask import g
from threading import Thread
import sensortag
import time
import sqlite3

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

@app.route('/')
def hello_world():
    return 'Hello World!'

@app.route('/threads')
def countthread():
    ta = get_threads()
    return str(len(ta))

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
    ta[ble_addr].enable=False
    return ble_addr

if __name__ == '__main__':
    app_data={}
    app_data['dbfile']='s.db'
    app.run(host='0.0.0.0', port=8080, debug=True)
