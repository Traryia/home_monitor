#!/bin/bash
# Read-only: test Open-Meteo forecast + air quality APIs from the Pi
LAT=31.49
LON=120.36

echo "=== forecast API ==="
curl -s --max-time 15 -o /tmp/wx_fc.json -w "HTTP %{http_code}  %{size_download} bytes\n" \
  "https://api.open-meteo.com/v1/forecast?latitude=${LAT}&longitude=${LON}&current=temperature_2m,relative_humidity_2m,apparent_temperature,is_day,weather_code,wind_speed_10m&hourly=temperature_2m,weather_code,precipitation_probability,is_day&daily=weather_code,temperature_2m_max,temperature_2m_min,sunrise,sunset,precipitation_probability_max&timezone=Asia%2FShanghai&forecast_days=7"
head -c 400 /tmp/wx_fc.json; echo; echo

echo "=== air quality API ==="
curl -s --max-time 15 -o /tmp/wx_aq.json -w "HTTP %{http_code}  %{size_download} bytes\n" \
  "https://air-quality-api.open-meteo.com/v1/air-quality?latitude=${LAT}&longitude=${LON}&current=us_aqi,european_aqi,pm2_5,pm10"
head -c 400 /tmp/wx_aq.json; echo; echo

echo "=== key values from forecast JSON ==="
python3 - <<'EOF'
import json
d = json.load(open('/tmp/wx_fc.json'))
c = d.get('current', {})
print('current:', {k: c.get(k) for k in ('time','temperature_2m','weather_code','is_day','relative_humidity_2m','apparent_temperature','wind_speed_10m')})
print('hourly keys:', list(d.get('hourly', {}).keys()), 'len:', len(d.get('hourly', {}).get('time', [])))
print('daily keys:', list(d.get('daily', {}).keys()), 'len:', len(d.get('daily', {}).get('time', [])))
print('daily[0]:', {k: d['daily'][k][0] for k in d['daily']})
try:
    aq = json.load(open('/tmp/wx_aq.json'))
    print('aqi current:', aq.get('current'))
except Exception as e:
    print('aq parse error:', e)
EOF
echo "API_TEST_DONE"
