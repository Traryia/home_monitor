# ESP32-S3: 5-sensor + MQTT v3.3
# BH1750(SDA=4,SCL=17,0x23) BMP280(38,39,0x76) SHT30(41,42,0x44) ADS1115(43,44,0x48)
# v3.1: 上报 10s->2s; 主循环加 WiFi 断线重连 (室外部署)
# v3.2: keepalive 30->120; 发布失败先关旧 socket; 退避 5s->2s; WDT 30s
# v3.3: 发布改 QoS1 — 等 PUBACK, 死连接 30s 内必被 WDT 复位 (QoS0 写进
#       内核缓冲区就"成功", 连接死了十几分钟都发现不了, 2026-08-09 晚实测)
from machine import Pin, SoftI2C
from umqtt.simple import MQTTClient
import network, time, json, gc, machine

WIFI_SSID = 'HUAWEI-FI18J2'
WIFI_PASS = '199908130922'
MQTT_BROKER = '192.168.3.36'
INTERVAL_MS = 2000

# ---- WiFi ----
wlan = network.WLAN(network.STA_IF)
wlan.active(True)
wlan.connect(WIFI_SSID, WIFI_PASS)
for i in range(30):
    if wlan.isconnected(): break
    time.sleep(1)
print('WiFi:', wlan.ifconfig() if wlan.isconnected() else 'FAIL')

# ---- I2C setup helper ----
def i2c_bus(sda, scl):
    Pin(sda, Pin.OUT, 1); Pin(scl, Pin.OUT, 1); time.sleep(0.2)
    return SoftI2C(sda=Pin(sda, Pin.OPEN_DRAIN, Pin.PULL_UP),
                   scl=Pin(scl, Pin.OPEN_DRAIN, Pin.PULL_UP),
                   freq=50000)

i2c_bh = i2c_bus(4, 17)
i2c_sht = i2c_bus(41, 42)
i2c_bmp = i2c_bus(38, 39)
i2c_adc = i2c_bus(43, 44)

# ---- Sensor readers ----
def read_bh1750():
    try:
        i2c_bh.writeto(0x23, b'\x10'); time.sleep(0.18)
        d = i2c_bh.readfrom(0x23, 2)
        return round(((d[0] << 8) | d[1]) / 1.2, 1)
    except: return None

def read_sht30():
    try:
        i2c_sht.writeto(0x44, b'\x24\x00'); time.sleep(0.02)
        d = i2c_sht.readfrom(0x44, 6)
        t = -45 + 175 * (d[0] << 8 | d[1]) / 65535
        h = -6 + 125 * (d[3] << 8 | d[4]) / 65535
        return round(t, 1), round(h, 1)
    except: return None, None

def read_bmp280():
    try:
        cid = i2c_bmp.readfrom_mem(0x76, 0xD0, 1)[0]
        if cid != 0x58: return None, None
        i2c_bmp.writeto_mem(0x76, 0xF4, b'\x27'); time.sleep(0.01)
        d = i2c_bmp.readfrom_mem(0x76, 0xFA, 6)
        rt = (d[0] << 12) | (d[1] << 4) | (d[2] >> 4)
        rp = (d[3] << 12) | (d[4] << 4) | (d[5] >> 4)
        tc = i2c_bmp.readfrom_mem(0x76, 0x88, 6)
        T1 = tc[0] | (tc[1] << 8)
        T2 = tc[2] | (tc[3] << 8)
        if T2 & 0x8000: T2 -= 65536
        T3 = tc[4] | (tc[5] << 8)
        if T3 & 0x8000: T3 -= 65536
        v1 = (rt / 16384.0 - T1 / 1024.0) * T2
        v2 = (rt / 131072.0 - T1 / 8192.0) ** 2 * T3
        T = (v1 + v2) / 5120.0
        pc = i2c_bmp.readfrom_mem(0x76, 0x8E, 18)
        P1 = pc[0] | (pc[1] << 8)
        P2 = pc[2] | (pc[3] << 8)
        if P2 & 0x8000: P2 -= 65536
        P3 = pc[4] | (pc[5] << 8)
        if P3 & 0x8000: P3 -= 65536
        P4 = pc[6] | (pc[7] << 8)
        if P4 & 0x8000: P4 -= 65536
        P5 = pc[8] | (pc[9] << 8)
        if P5 & 0x8000: P5 -= 65536
        P6 = pc[10] | (pc[11] << 8)
        if P6 & 0x8000: P6 -= 65536
        P7 = pc[12] | (pc[13] << 8)
        if P7 & 0x8000: P7 -= 65536
        P8 = pc[14] | (pc[15] << 8)
        if P8 & 0x8000: P8 -= 65536
        P9 = pc[16] | (pc[17] << 8)
        if P9 & 0x8000: P9 -= 65536
        tf = v1 + v2
        vr1 = (tf / 2.0) - 64000.0
        vr2 = vr1 * vr1 * P6 / 32768.0
        vr2 = vr2 + vr1 * P5 * 2.0
        vr2 = (vr2 / 4.0) + (P4 * 65536.0)
        vr1 = (P3 * vr1 * vr1 / 524288.0 + P2 * vr1) / 524288.0
        vr1 = (1.0 + vr1 / 32768.0) * P1
        p = 1048576.0 - rp
        p = (p - (vr2 / 4096.0)) * 6250.0 / vr1
        vr1 = P9 * p * p / 2147483648.0
        vr2 = p * P8 / 32768.0
        p = p + (vr1 + vr2 + P7) / 16.0
        return round(T, 1), round(p / 100.0 + 121.04, 1)
    except: return None, None

def read_ads1115():
    try:
        v0 = v1 = None
        for ch, mux in [("A0", 0x4), ("A1", 0x5)]:
            cfg = 0x8000 | (mux << 12) | (1 << 9) | (4 << 5) | 0x03
            i2c_adc.writeto_mem(0x48, 0x01, bytes([cfg >> 8, cfg & 0xFF]))
            time.sleep(0.01)
            d = i2c_adc.readfrom_mem(0x48, 0x00, 2)
            v = (d[0] << 8) | d[1]
            if v & 0x8000: v -= 65536
            val = round(v * 4.096 / 32768, 4)
            if ch == "A0": v0 = val
            else: v1 = val
        return v0, v1
    except: return None, None

# ---- MQTT ----
client = None
def mqtt_connect():
    global client
    try:
        client = MQTTClient('esp32-5sensor', MQTT_BROKER, keepalive=120)
        client.connect()
        print('MQTT connected')
        return True
    except Exception as e:
        print('MQTT fail:', e)
        return False

# ---- Main loop ----
mqtt_connect()
count = 0
last_pub = time.ticks_ms()
last_wifi_try = time.ticks_ms()
wdt = machine.WDT(timeout=30000)   # 30 秒不喂狗自动复位 (防卡死)

while True:
    wdt.feed()
    now = time.ticks_ms()
    if time.ticks_diff(now, last_pub) < INTERVAL_MS:
        time.sleep_ms(100)
        continue

    # WiFi 掉线则重连 (每 5 秒最多试一次), 未连接时跳过采集
    if not wlan.isconnected():
        client = None
        if time.ticks_diff(now, last_wifi_try) > 5000:
            last_wifi_try = now
            print('WiFi lost, reconnecting...')
            try:
                wlan.disconnect()
            except: pass
            wlan.connect(WIFI_SSID, WIFI_PASS)
        time.sleep_ms(500)
        continue

    lux = read_bh1750()
    t_sht, h_sht = read_sht30()
    t_bmp, p_bmp = read_bmp280()
    adc0, adc1 = read_ads1115()

    gc.collect()

    payload = {
        'device': 'esp32-outdoor',
        'type': 'sensor',
        'lux': lux,
        'temperature': t_sht if t_sht is not None else t_bmp,
        'humidity': h_sht,
        'pressure': p_bmp,
        'adc0_voltage': adc0,
        'adc1_voltage': adc1,
        'rssi': wlan.status('rssi') if wlan.isconnected() else None,
        'uptime': time.ticks_ms() // 1000,
        'counter': count,
        'mem_free': gc.mem_free(),
        'mem_used': gc.mem_alloc(),
        'ip': wlan.ifconfig()[0] if wlan.isconnected() else '0.0.0.0'
    }

    try:
        if client:
            client.publish('home/sensors', json.dumps(payload), qos=1)
        else:
            if mqtt_connect():
                client.publish('home/sensors', json.dumps(payload), qos=1)
        count += 1
        print('PUB #%d lux=%s T=%s H=%s P=%s A0=%s A1=%s' %
              (count, lux, payload['temperature'], h_sht, p_bmp, adc0, adc1))
    except Exception as e:
        print('PUB fail:', e)
        try: client.sock.close()
        except: pass
        client = None
        time.sleep(2)
    last_pub = now
