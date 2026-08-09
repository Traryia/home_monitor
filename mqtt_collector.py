#!/usr/bin/env python3
# MQTT Collector v3.3
# v3.3: 离线判定 45s->120s (配合 ESP32 keepalive=120, 丢包链路减少显示抖动)
# v3.2: 分层存储 — 原始数据保留 8 天, sensor_minute 1分钟聚合保留 2 年;
#       (device,timestamp) 索引; WAL 模式 (dashboard 并发读); 启动时 VACUUM
import paho.mqtt.client as mqtt
import sqlite3, json, os, time, logging, threading

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')
log = logging.getLogger('collector')

DB = os.path.expanduser('~/home_monitor/sensors.db')
MQTT_HOST = 'localhost'

RAW_KEEP_DAYS = 8        # 原始数据保留 (2s/条)
AGG_KEEP_YEARS = 2       # 1分钟聚合保留

def init_db():
    conn = sqlite3.connect(DB)
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_sd_dev_ts ON sensor_data(device, timestamp)')
    conn.execute('''CREATE TABLE IF NOT EXISTS sensor_minute (
        device TEXT NOT NULL,
        minute TEXT NOT NULL,          -- 'YYYY-MM-DD HH:MM' localtime
        lux REAL, temperature REAL, humidity REAL, pressure REAL,
        adc0_voltage REAL, adc1_voltage REAL, rssi REAL,
        cpu_usage REAL, cpu_temp REAL, mem_used REAL,
        n INTEGER,
        PRIMARY KEY (device, minute))''')
    conn.commit(); conn.close()
    log.info('DB init ok (WAL + index + sensor_minute)')
    # 启动时回收空间 (retention 删除后文件不会自动缩小)
    try:
        conn = sqlite3.connect(DB); conn.execute('VACUUM'); conn.close()
    except Exception as e:
        log.warning('vacuum skip: ' + str(e))

def _maintain():
    """每 5 分钟聚合已完成的分钟; 每小时清理过期数据"""
    last_clean = 0
    while True:
        time.sleep(300)
        try:
            conn = sqlite3.connect(DB)
            conn.execute('''INSERT OR REPLACE INTO sensor_minute
                SELECT device, strftime('%Y-%m-%d %H:%M', timestamp),
                    round(avg(lux),1), round(avg(temperature),2), round(avg(humidity),1),
                    round(avg(pressure),1), round(avg(adc0_voltage),4), round(avg(adc1_voltage),4),
                    round(avg(rssi),1), round(avg(cpu_usage),1), round(avg(cpu_temp),1),
                    round(avg(mem_used),1), count(*)
                FROM sensor_data
                WHERE timestamp >= datetime('now','localtime','-15 minutes')
                  AND timestamp < strftime('%Y-%m-%d %H:%M','now','localtime')
                GROUP BY device, strftime('%Y-%m-%d %H:%M', timestamp)''')
            conn.commit()
            if time.time() - last_clean > 3600:
                last_clean = time.time()
                cur = conn.execute("DELETE FROM sensor_data WHERE timestamp < datetime('now','localtime','-%d days')" % RAW_KEEP_DAYS)
                conn.execute("DELETE FROM sensor_minute WHERE minute < datetime('now','localtime','-%d years')" % AGG_KEEP_YEARS)
                conn.commit()
                log.info('retention: raw>%dd rows deleted=%d' % (RAW_KEEP_DAYS, cur.rowcount))
            conn.close()
        except Exception as e:
            log.error('maintain error: ' + str(e))

def insert_sensor(data):
    try:
        conn = sqlite3.connect(DB)
        conn.execute('''INSERT INTO sensor_data
            (device, sensor_type, lux, rssi, ip, mem_free, mem_used,
             uptime, counter, cpu_usage, cpu_temp,
             temperature, humidity, pressure, adc0_voltage, adc1_voltage,
             payload)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', (
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
            data.get('cpu_temp'),
            data.get('temperature'),
            data.get('humidity'),
            data.get('pressure'),
            data.get('adc0_voltage'),
            data.get('adc1_voltage'),
            json.dumps(data)
        ))
        conn.commit(); conn.close()
    except Exception as e:
        log.error('DB insert error: ' + str(e))

def upsert_status(data):
    try:
        conn = sqlite3.connect(DB)
        conn.execute('''INSERT INTO device_status (device, online, last_seen, ip, rssi, cpu_temp)
            VALUES (?,1,datetime("now","localtime"),?,?,?)
            ON CONFLICT(device) DO UPDATE SET
            online=1, last_seen=datetime("now","localtime"),
            ip=COALESCE(excluded.ip, device_status.ip),
            rssi=COALESCE(excluded.rssi, device_status.rssi),
            cpu_temp=COALESCE(excluded.cpu_temp, device_status.cpu_temp)''',
            (data.get('device'), data.get('ip'), data.get('rssi'), data.get('cpu_temp')))
        conn.commit(); conn.close()
    except Exception as e:
        log.error('Status upsert error: ' + str(e))

def on_connect(client, userdata, flags, reason_code, props):
    if reason_code == 0:
        client.subscribe('home/sensors', 1)
        client.subscribe('home/status', 1)
        log.info('Subscribed: home/sensors, home/status')
    else:
        log.warning('Connect failed: ' + str(reason_code))

def on_message(client, userdata, msg):
    try:
        data = json.loads(msg.payload.decode())
        device = data.get('device', '?')
        if msg.topic == 'home/status':
            upsert_status(data)
            log.info('[' + device + '] status updated')
        else:
            insert_sensor(data); upsert_status(data)
            lux = data.get('lux'); temp = data.get('temperature')
            hum = data.get('humidity'); pres = data.get('pressure')
            log.info('[' + device + '] lux=' + str(lux) + ' T=' + str(temp) + ' H=' + str(hum) + ' P=' + str(pres))
    except json.JSONDecodeError:
        log.warning('Bad JSON: ' + str(msg.payload[:80]))
    except Exception as e:
        log.error('Error: ' + str(e))

def offline_checker():
    while True:
        try:
            conn = sqlite3.connect(DB)
            conn.execute("UPDATE device_status SET online=0 WHERE last_seen < datetime('now','localtime','-120 seconds')")
            conn.commit(); conn.close()
        except: pass
        time.sleep(30)

_pi_cpu_prev = [0, 0]
def _pi_cpu_temp():
    try:
        with open('/sys/class/thermal/thermal_zone0/temp') as f:
            return round(int(f.read().strip()) / 1000.0, 1)
    except: return None
def _pi_cpu_usage():
    global _pi_cpu_prev
    try:
        with open('/proc/stat') as f:
            v = [int(x) for x in f.readline().split()[1:8]]
        t, idle = sum(v), v[3] + v[4]
        if _pi_cpu_prev[0] == 0: _pi_cpu_prev = [t, idle]; return None
        td, idled = t - _pi_cpu_prev[0], idle - _pi_cpu_prev[1]
        _pi_cpu_prev = [t, idle]
        return round(100 * (1 - idled / td), 1) if td else None
    except: return None
def _pi_memory():
    try:
        with open('/proc/meminfo') as f: lines = f.readlines()
        total = int(lines[0].split(':')[1].strip().split()[0]) // 1024
        avail = int(lines[2].split(':')[1].strip().split()[0]) // 1024
        return total, total - avail, avail
    except: return None, None, None
def _pi_record():
    while True:
        time.sleep(10)
        try:
            ct = _pi_cpu_temp(); cu = _pi_cpu_usage()
            mt, mu, mf = _pi_memory()
            data = {'device':'pi-system','type':'system','cpu_temp':ct,'cpu_usage':cu,'mem_free':mf,'mem_used':mu}
            conn = sqlite3.connect(DB)
            conn.execute('''INSERT INTO sensor_data
                (device,sensor_type,lux,rssi,ip,mem_free,mem_used,uptime,counter,cpu_usage,cpu_temp,payload)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)''',
                (data['device'],data['type'],None,None,None,data['mem_free'],data['mem_used'],None,None,data['cpu_usage'],data['cpu_temp'],json.dumps(data)))
            conn.commit(); conn.close()
        except Exception as e: log.error('pi_record error: ' + str(e))

threading.Thread(target=_pi_record, daemon=True).start()

def main():
    init_db()
    threading.Thread(target=_maintain, daemon=True).start()
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id='mqtt-collector-v3')
    client.on_connect = on_connect
    client.on_message = on_message
    client.reconnect_delay_set(min_delay=5, max_delay=30)
    while True:
        try:
            client.connect(MQTT_HOST, 1883, keepalive=60)
            log.info('MQTT Collector v3.2 started (5-sensor, tiered retention)')
            threading.Thread(target=offline_checker, daemon=True).start()
            client.loop_forever()
        except Exception as e:
            log.error('Connection lost: ' + str(e) + ', retrying')
            time.sleep(10)

if __name__ == '__main__':
    main()
