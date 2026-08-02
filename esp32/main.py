# ESP32-S3 v10: BH1750 + LED + MQTT (Pi5 Broker)
# I2C: IO43(SDA) + IO44(SCL) | BH1750 0x23 | WS2812 IO38
import time; time.sleep(3)

from machine import Pin, SoftI2C
from neopixel import NeoPixel
import network, json, gc, machine
from umqtt.simple import MQTTClient

WIFI_SSID   = 'HUAWEI-FI18J2'
WIFI_PASS   = '199908130922'
MQTT_BROKER = '192.168.3.36'
DEVICE_ID   = 'esp32-outdoor'
PUBLISH_S   = 10
LED_MS      = 1000

i2c = SoftI2C(scl=Pin(44), sda=Pin(43), freq=100000)
try:
    i2c.writeto(0x23, b'\x10')
    time.sleep_ms(180)
except OSError:
    pass

np = NeoPixel(Pin(38), 1)
colors = [(50,0,0), (0,50,0), (0,0,50)]
led_idx = 0
np[0] = colors[led_idx]; np.write()

wlan = network.WLAN(network.STA_IF)
wlan.active(True)
wlan.connect(WIFI_SSID, WIFI_PASS)
for _ in range(30):
    if wlan.isconnected(): break
    time.sleep(1)

def mqtt_connect():
    try:
        c = MQTTClient(DEVICE_ID, MQTT_BROKER, keepalive=30)
        c.connect()
        return c
    except Exception:
        return None

client = mqtt_connect()

def read_lux():
    try:
        d = i2c.readfrom(0x23, 2)
        return round((d[0] << 8 | d[1]) / 1.2, 1)
    except OSError:
        return None

last_pub = time.ticks_ms()
last_led = time.ticks_ms()
count = 0

while True:
    now = time.ticks_ms()

    if time.ticks_diff(now, last_led) >= LED_MS:
        led_idx = (led_idx + 1) % 3
        np[0] = colors[led_idx]; np.write()
        last_led = now

    if time.ticks_diff(now, last_pub) >= PUBLISH_S * 1000:
        try:
            if not wlan.isconnected():
                wlan.connect(WIFI_SSID, WIFI_PASS)
                time.sleep(3)
            if client is None:
                client = mqtt_connect()

            lux = read_lux()
            rssi = wlan.status('rssi')
            ip = wlan.ifconfig()[0]
            uptime = time.ticks_ms() // 1000

            payload = json.dumps({
                'device': DEVICE_ID, 'type': 'outdoor',
                'lux': lux, 'rssi': rssi, 'uptime': uptime,
                'counter': count, 'ip': ip,
                'mem_free': gc.mem_free(), 'mem_used': gc.mem_alloc(),
                'cpu_mhz': machine.freq() // 1000000,
                'ssid': WIFI_SSID,
            })
            client.publish('home/sensors', payload)
            client.publish('home/status', json.dumps({
                'device': DEVICE_ID, 'online': True,
                'ip': ip, 'rssi': rssi, 'lux': lux
            }))
            count += 1
            last_pub = now
        except Exception:
            try:
                client = mqtt_connect()
            except:
                pass
            time.sleep(3)

    time.sleep_ms(50)