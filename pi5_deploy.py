#!/usr/bin/env python3
# Pi5 deploy: DB migration + collector + dashboard update
import sqlite3, os as _os, shutil, time, json

DB = _os.path.expanduser('~/home_monitor/sensors.db')
DIR = _os.path.expanduser('~/home_monitor')
print('=== DB Migration ===')
conn = sqlite3.connect(DB)
cur = conn.cursor()
existing = [r[1] for r in cur.execute('PRAGMA table_info(sensor_data)').fetchall()]
for col, typ in [('temperature','REAL'),('humidity','REAL'),('pressure','REAL'),('adc0_voltage','REAL'),('adc1_voltage','REAL')]:
    if col not in existing:
        cur.execute('ALTER TABLE sensor_data ADD COLUMN '+col+' '+typ)
        print('  Added:', col, typ)
    else:
        print('  Exists:', col)
conn.commit(); conn.close()
print('DB OK')
