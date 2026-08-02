#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MQTT Collector v2.1: route home/sensors->sensor_data, home/status->device_status."""
import paho.mqtt.client as mqtt
import sqlite3, json, os, time, logging, threading

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')
log = logging.getLogger('collector')

DB = os.path.expanduser('~/home_monitor/sensors.db')
MQTT_HOST = 'localhost'

def insert_sensor(data):
    try:
        conn = sqlite3.connect(DB)
        conn.execute('''INSERT INTO sensor_data
            (device, sensor_type, lux, rssi, ip, mem_free, mem_used,
             uptime, counter, cpu_usage, cpu_temp, payload)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)''', (
            data.get('device', 'unknown'),
            data.get('type', 'unknown'),
            data.get('lux'),
            data.get('rssi'),
            data.get('ip'),
            data.get('mem_free'),
            data.get('mem_used'),
            data.get('uptime'),
            data.get('counter'),
            data.get('cpu_usage'),
            json.dumps(data)
        ))
        conn.commit()
        conn.close()
    except Exception as e:
        log.error(f'DB insert error: {e}')

def upsert_status(data):
    try:
        conn = sqlite3.connect(DB)
        conn.execute('''INSERT INTO device_status (device, online, last_seen, ip, rssi, cpu_temp)
            VALUES (?,1,datetime("now","localtime"),?,?,?)
            ON CONFLICT(device) DO UPDATE SET
            online=1,
            last_seen=datetime("now","localtime"),
            ip=COALESCE(excluded.ip, device_status.ip),
            rssi=COALESCE(excluded.rssi, device_status.rssi),
            cpu_temp=COALESCE(excluded.cpu_temp, device_status.cpu_temp)''',
            (data.get('device'), data.get('ip'), data.get('rssi'), data.get('cpu_temp'))
        )
        conn.commit()
        conn.close()
    except Exception as e:
        log.error(f'Status upsert error: {e}')

def on_connect(client, userdata, flags, reason_code, props):
    if reason_code == 0:
        client.subscribe('home/sensors', 1)
        client.subscribe('home/status', 1)
        log.info('Subscribed: home/sensors, home/status')
    else:
        log.warning(f'Connect failed: {reason_code}')

def on_message(client, userdata, msg):
    try:
        data = json.loads(msg.payload.decode())
        device = data.get('device', '?')

        if msg.topic == 'home/status':
            upsert_status(data)
            log.info(f'[{device}] status updated')
        else:
            insert_sensor(data)
            lux = data.get('lux')
            cpu = data.get('cpu_temp')
            log.info(f'[{device}] lux={lux} cpu={cpu}')
    except json.JSONDecodeError:
        log.warning(f'Bad JSON: {msg.payload[:80]}')
    except Exception as e:
        log.error(f'Error: {e}')

def offline_checker():
    while True:
        try:
            conn = sqlite3.connect(DB)
            conn.execute("UPDATE device_status SET online=0 WHERE last_seen < datetime('now','localtime','-45 seconds')")
            conn.commit()
            conn.close()
        except:
            pass
        time.sleep(30)


# ==== Pi5 system info recording ====
_pi_cpu_prev = [0, 0]

def _pi_cpu_temp():
    try:
        with open("/sys/class/thermal/thermal_zone0/temp") as f:
            return round(int(f.read().strip()) / 1000.0, 1)
    except: return None

def _pi_cpu_usage():
    global _pi_cpu_prev
    try:
        with open("/proc/stat") as f:
            v = [int(x) for x in f.readline().split()[1:8]]
        t, idle = sum(v), v[3] + v[4]
        if _pi_cpu_prev[0] == 0: _pi_cpu_prev = [t, idle]; return None
        td, idled = t - _pi_cpu_prev[0], idle - _pi_cpu_prev[1]
        _pi_cpu_prev = [t, idle]
        return round(100 * (1 - idled / td), 1) if td else None
    except: return None

def _pi_memory():
    try:
        with open("/proc/meminfo") as f:
            lines = f.readlines()
        total = int(lines[0].split(":")[1].strip().split()[0]) // 1024
        avail = int(lines[2].split(":")[1].strip().split()[0]) // 1024
        return total, total - avail, avail
    except: return None, None, None

def _pi_record():
    import sqlite3 as _sql
    while True:
        time.sleep(10)
        try:
            ct = _pi_cpu_temp(); cu = _pi_cpu_usage()
            mt, mu, mf = _pi_memory()
            data = {"device":"pi-system","type":"system","cpu_temp":ct,"cpu_usage":cu,"mem_free":mf,"mem_used":mu}
            conn = _sql.connect(DB)
            conn.execute("""INSERT INTO sensor_data
                (device,sensor_type,lux,rssi,ip,mem_free,mem_used,uptime,counter,cpu_usage,cpu_temp,payload)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (data["device"],data["type"],None,None,None,data["mem_free"],data["mem_used"],None,None,data["cpu_usage"],data["cpu_temp"],json.dumps(data)))
            conn.commit(); conn.close()
        except Exception as e: log.error(f"pi_record error: {e}")

threading.Thread(target=_pi_record, daemon=True).start()

def main():
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id='mqtt-collector-v2')
    client.on_connect = on_connect
    client.on_message = on_message
    client.reconnect_delay_set(min_delay=5, max_delay=30)

    while True:
        try:
            client.connect(MQTT_HOST, 1883, keepalive=60)
            log.info('MQTT Collector started (v2.2: sync connect + offline checker)')
            threading.Thread(target=offline_checker, daemon=True).start()
            client.loop_forever()
        except Exception as e:
            log.error(f'Connection lost: {e}, retrying in 10s')
            time.sleep(10)

if __name__ == '__main__':
    main()
