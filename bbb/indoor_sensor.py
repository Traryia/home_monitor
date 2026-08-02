#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AM3358 BBB Indoor Sensor Node - Skeleton
   MQTT broker: Pi5 (192.168.7.1 via USB gadget)
   I2C buses: /dev/i2c-0 (P9.19/SCL + P9.20/SDA), /dev/i2c-2 (P9.21/SCL + P9.22/SDA)

   To add sensors:
   1. import smbus
   2. bus = smbus.SMBus(1)  # or 2 for i2c-2
   3. Fill in read_temperature() / read_humidity() below
"""
import paho.mqtt.client as mqtt
import time, json, logging, os, socket

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')
log = logging.getLogger('bbb-indoor')

MQTT_HOST = '192.168.7.1'   # Pi5 USB gadget
DEVICE_ID = 'bbb-indoor'
PUBLISH_S = 10

# ==== Placeholder sensor functions ====
def read_temperature():
    return None

def read_humidity():
    return None

def get_cpu_temp():
    try:
        with open('/sys/class/thermal/thermal_zone0/temp') as f:
            return round(int(f.read().strip()) / 1000.0, 1)
    except:
        return None

def main():
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=DEVICE_ID)
    client.connect(MQTT_HOST, 1883)
    log.info(f'BBB Indoor node started, broker={MQTT_HOST}')

    count = 0
    while True:
        try:
            temp = read_temperature()
            hum = read_humidity()
            cpu_temp = get_cpu_temp()
            hostname = socket.gethostname()

            payload = {
                'device': DEVICE_ID, 'type': 'indoor',
                'temperature': temp, 'humidity': hum,
                'cpu_temp': cpu_temp, 'hostname': hostname,
                'counter': count,
            }
            client.publish('home/sensors', json.dumps(payload))
            client.publish('home/status', json.dumps({
                'device': DEVICE_ID, 'online': True,
                'cpu_temp': cpu_temp, 'hostname': hostname,
            }))
            count += 1
        except Exception as e:
            log.error(f'Error: {e}')
            try:
                client.reconnect()
            except:
                pass
            time.sleep(5)
        time.sleep(PUBLISH_S)

if __name__ == '__main__':
    main()
