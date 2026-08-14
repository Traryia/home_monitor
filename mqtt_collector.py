#!/usr/bin/env python3
# MQTT Collector v4.0 (接收/存储重写)
# v4.0: 支持 ESP32 v4.0 断网补传 — payload 带 ts(采集时刻 epoch) 时按
#       原始时间入库, 历史空洞被回填; 持久连接+写锁替代每消息开关库;
#       启动自检建表; 数值字段统一清洗; 补传日志带 lag 标记
# v3.3: 离线判定 45s->120s; v3.2: 分层存储 (原始 8 天 / sensor_minute 2 年)
# v4.1: 离线阈值 120s->20s (2026-08-14 用户要求更快反应; 检查周期 30s->5s)
import paho.mqtt.client as mqtt
import sqlite3, json, os, time, logging, threading

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')
log = logging.getLogger('collector')

DB = os.path.expanduser('~/home_monitor/sensors.db')
MQTT_HOST = 'localhost'

RAW_KEEP_DAYS = 8        # 原始数据保留 (2s/条)
AGG_KEEP_YEARS = 2       # 1分钟聚合保留
OFFLINE_AFTER_S = 20     # 配合 ESP32 keepalive=120 (20s 内无数据判离线)
TS_MAX_SKEW_S = 600      # 补传 ts 允许的最大未来偏差

NUM_FIELDS = ('lux', 'temperature', 'humidity', 'pressure',
              'adc0_voltage', 'adc1_voltage', 'rssi',
              'uptime', 'counter', 'mem_free', 'mem_used',
              'cpu_usage', 'cpu_temp')

# ---- 存储层: 单连接 + 写锁 (WAL 下 dashboard 并发读不阻塞) ----
class Storage:
    def __init__(self, path):
        self.lock = threading.Lock()
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.execute('PRAGMA journal_mode=WAL')
        self.conn.execute('PRAGMA busy_timeout=5000')
        self._init_schema()

    def _init_schema(self):
        with self.lock:
            c = self.conn
            c.execute('''CREATE TABLE IF NOT EXISTS sensor_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT DEFAULT (datetime('now','localtime')),
                device TEXT, sensor_type TEXT,
                lux REAL, rssi REAL, ip TEXT,
                mem_free REAL, mem_used REAL, uptime REAL, counter REAL,
                cpu_usage REAL, cpu_temp REAL,
                temperature REAL, humidity REAL, pressure REAL,
                adc0_voltage REAL, adc1_voltage REAL,
                payload TEXT)''')
            c.execute('''CREATE TABLE IF NOT EXISTS device_status (
                device TEXT PRIMARY KEY,
                online INTEGER DEFAULT 0, last_seen TEXT,
                ip TEXT, rssi REAL, cpu_temp REAL)''')
            c.execute('''CREATE TABLE IF NOT EXISTS sensor_minute (
                device TEXT NOT NULL,
                minute TEXT NOT NULL,          -- 'YYYY-MM-DD HH:MM' localtime
                lux REAL, temperature REAL, humidity REAL, pressure REAL,
                adc0_voltage REAL, adc1_voltage REAL, rssi REAL,
                cpu_usage REAL, cpu_temp REAL, mem_used REAL,
                n INTEGER,
                PRIMARY KEY (device, minute))''')
            c.execute('CREATE INDEX IF NOT EXISTS idx_sd_dev_ts ON sensor_data(device, timestamp)')
            self.conn.commit()
        log.info('DB init ok (WAL + schema check)')

    def vacuum(self):
        # 启动时回收空间 (retention 删除后文件不会自动缩小)
        try:
            with self.lock:
                self.conn.isolation_level = None
                self.conn.execute('VACUUM')
                self.conn.isolation_level = ''
        except Exception as e:
            log.warning('vacuum skip: ' + str(e))

    def execute(self, sql, params=()):
        with self.lock:
            cur = self.conn.execute(sql, params)
            self.conn.commit()
            return cur

    # ---- 写入 ----
    def insert_sensor(self, data):
        """ts 合法 (过去~未来10分钟内) 按原始采集时间入库, 否则用到达时间。
        返回 (lag_seconds|None) 供日志标记补传"""
        ts = data.get('ts')
        when = None
        lag = None
        if isinstance(ts, (int, float)) and not isinstance(ts, bool):
            lag = time.time() - ts
            if lag < 3600 * 24 * RAW_KEEP_DAYS and lag > -TS_MAX_SKEW_S:
                when = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(ts))
            else:
                lag = None  # 离谱的 ts 视为没有
        cols = ['device', 'sensor_type', 'lux', 'rssi', 'ip', 'mem_free', 'mem_used',
                'uptime', 'counter', 'cpu_usage', 'cpu_temp',
                'temperature', 'humidity', 'pressure', 'adc0_voltage', 'adc1_voltage',
                'payload']
        vals = [data.get('device', 'unknown'), data.get('type', 'unknown')]
        vals.append(_num(data.get('lux')))
        vals.append(_num(data.get('rssi')))
        vals.append(str(data.get('ip')) if data.get('ip') else None)
        for f in ('mem_free', 'mem_used', 'uptime', 'counter', 'cpu_usage', 'cpu_temp',
                  'temperature', 'humidity', 'pressure', 'adc0_voltage', 'adc1_voltage'):
            vals.append(_num(data.get(f)))
        vals.append(json.dumps(data, ensure_ascii=False))
        if when:
            cols.insert(0, 'timestamp')
            vals.insert(0, when)
        self.execute(
            'INSERT INTO sensor_data (%s) VALUES (%s)' % (','.join(cols), ','.join('?' * len(cols))),
            vals)
        return lag

    def upsert_status(self, data):
        self.execute('''INSERT INTO device_status (device, online, last_seen, ip, rssi, cpu_temp)
            VALUES (?,1,datetime("now","localtime"),?,?,?)
            ON CONFLICT(device) DO UPDATE SET
            online=1, last_seen=datetime("now","localtime"),
            ip=COALESCE(excluded.ip, device_status.ip),
            rssi=COALESCE(excluded.rssi, device_status.rssi),
            cpu_temp=COALESCE(excluded.cpu_temp, device_status.cpu_temp)''',
            (data.get('device'),
             str(data.get('ip')) if data.get('ip') else None,
             _num(data.get('rssi')), _num(data.get('cpu_temp'))))

    # ---- 维护 ----
    def aggregate(self):
        """聚合已完成的分钟 (幂等, INSERT OR REPLACE)"""
        self.execute('''INSERT OR REPLACE INTO sensor_minute
            SELECT device, strftime('%Y-%m-%d %H:%M', timestamp),
                round(avg(lux),1), round(avg(temperature),2), round(avg(humidity),1),
                round(avg(pressure),1), round(avg(adc0_voltage),4), round(avg(adc1_voltage),4),
                round(avg(rssi),1), round(avg(cpu_usage),1), round(avg(cpu_temp),1),
                round(avg(mem_used),1), count(*)
            FROM sensor_data
            WHERE timestamp >= datetime('now','localtime','-15 minutes')
              AND timestamp < strftime('%Y-%m-%d %H:%M','now','localtime')
            GROUP BY device, strftime('%Y-%m-%d %H:%M', timestamp)''')

    def cleanup(self):
        cur = self.execute("DELETE FROM sensor_data WHERE timestamp < datetime('now','localtime','-%d days')" % RAW_KEEP_DAYS)
        self.execute("DELETE FROM sensor_minute WHERE minute < datetime('now','localtime','-%d years')" % AGG_KEEP_YEARS)
        return cur.rowcount

    def mark_offline(self):
        self.execute("UPDATE device_status SET online=0 WHERE last_seen < datetime('now','localtime','-%d seconds')" % OFFLINE_AFTER_S)


def _num(v):
    """只接受真正的数值, 其余一律 None"""
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    return v


st = None  # Storage, main() 里初始化

# ---- MQTT 回调 ----
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
        if not isinstance(data, dict):
            raise ValueError('not a dict')
        device = str(data.get('device', '?'))
        if msg.topic == 'home/status':
            st.upsert_status(data)
            log.info('[' + device + '] status updated')
            return
        lag = st.insert_sensor(data)
        st.upsert_status(data)
        tag = ''
        if lag is not None and lag > 30:
            tag = ' BACKFILL(lag=%ds)' % lag
        log.info('[%s] lux=%s T=%s H=%s P=%s%s' % (
            device, data.get('lux'), data.get('temperature'),
            data.get('humidity'), data.get('pressure'), tag))
    except (json.JSONDecodeError, ValueError):
        log.warning('Bad JSON: ' + str(msg.payload[:80]))
    except Exception as e:
        log.error('Error: ' + str(e))

# ---- 后台线程 ----
def _maintain():
    """每 5 分钟聚合已完成的分钟; 每小时清理过期数据"""
    last_clean = 0
    while True:
        time.sleep(300)
        try:
            st.aggregate()
            if time.time() - last_clean > 3600:
                last_clean = time.time()
                n = st.cleanup()
                log.info('retention: raw>%dd rows deleted=%d' % (RAW_KEEP_DAYS, n))
        except Exception as e:
            log.error('maintain error: ' + str(e))

def _offline_checker():
    while True:
        try:
            st.mark_offline()
        except Exception as e:
            log.error('offline check error: ' + str(e))
        time.sleep(5)

# ---- Pi 自身系统指标 ----
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
            st.insert_sensor({'device': 'pi-system', 'type': 'system',
                              'cpu_temp': ct, 'cpu_usage': cu,
                              'mem_free': mf, 'mem_used': mu})
        except Exception as e:
            log.error('pi_record error: ' + str(e))

def main():
    global st
    st = Storage(DB)
    st.vacuum()
    threading.Thread(target=_maintain, daemon=True).start()
    threading.Thread(target=_offline_checker, daemon=True).start()
    threading.Thread(target=_pi_record, daemon=True).start()
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id='mqtt-collector-v4')
    client.on_connect = on_connect
    client.on_message = on_message
    client.reconnect_delay_set(min_delay=5, max_delay=30)
    while True:
        try:
            client.connect(MQTT_HOST, 1883, keepalive=60)
            log.info('MQTT Collector v4.0 started (backfill-aware, tiered retention)')
            client.loop_forever()
        except Exception as e:
            log.error('Connection lost: ' + str(e) + ', retrying')
            time.sleep(10)

if __name__ == '__main__':
    main()
