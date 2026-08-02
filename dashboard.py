#!/usr/bin/env python3
"""Home Monitor Dashboard v5.1 - Unified layout, 24h charts"""
import sqlite3, json, os, time, threading, requests
from flask import Flask, jsonify, request
from datetime import datetime


app = Flask(__name__)
DB = os.path.expanduser("~/home_monitor/sensors.db")

# ---- DB helpers ----
def query_one(sql, params=()):
    conn = sqlite3.connect(DB); conn.row_factory = sqlite3.Row
    row = conn.execute(sql, params).fetchone(); conn.close()
    return dict(row) if row else {}

def query_all(sql, params=()):
    conn = sqlite3.connect(DB); conn.row_factory = sqlite3.Row
    rows = conn.execute(sql, params).fetchall(); conn.close()
    return [dict(r) for r in rows]

# ---- Pi system info ----
_pi_cpu_prev = [0, 0]
def pi_cpu_temp():
    try:
        with open("/sys/class/thermal/thermal_zone0/temp") as f:
            return round(int(f.read().strip())/1000.0, 1)
    except: return None

def pi_cpu_usage():
    global _pi_cpu_prev
    try:
        with open("/proc/stat") as f: v=[int(x) for x in f.readline().split()[1:8]]
        t,idle=sum(v),v[3]+v[4]
        if _pi_cpu_prev[0]==0: _pi_cpu_prev=[t,idle]; return None
        td,idled=t-_pi_cpu_prev[0],idle-_pi_cpu_prev[1]; _pi_cpu_prev=[t,idle]
        return round(100*(1-idled/td),1) if td else None
    except: return None

def pi_memory():
    try:
        with open("/proc/meminfo") as f: lines=f.readlines()
        total=int(lines[0].split(":")[1].strip().split()[0])
        avail=int(lines[2].split(":")[1].strip().split()[0])
        return total//1024, (total-avail)//1024, avail//1024
    except: return None,None,None

def pi_disk():
    try:
        s=os.statvfs("/"); return s.f_frsize*s.f_blocks//1048576, s.f_frsize*s.f_bavail//1048576
    except: return None,None

# ---- Pi metrics (5-min intervals, 300 entries = 25h) ----
# Pi metrics now recorded by mqtt_collector into sensor_data (device=pi-system)

# ---- Weather cache ----
_wx = {"data":None,"ts":0}
_wx_lock = threading.Lock()
_OM_URL = "https://api.open-meteo.com/v1/forecast?latitude=31.23&longitude=121.47&hourly=temperature_2m,relative_humidity_2m&daily=temperature_2m_max,temperature_2m_min,sunrise,sunset&current=temperature_2m,relative_humidity_2m&timezone=Asia/Shanghai&forecast_days=5"
def _fetch_weather():
    try:
        r=requests.get(_OM_URL,timeout=10)
        with _wx_lock:
            _wx["data"]=r.json(); _wx["ts"]=time.time()
    except: pass
def _weather_loop():
    _fetch_weather()
    while True:
        time.sleep(1800)
        _fetch_weather()
threading.Thread(target=_weather_loop, daemon=True).start()
def get_weather():
    with _wx_lock:
        if _wx["data"]: return _wx["data"]
    return None

# ---- Shared HTML fragments ----
CSS="""<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:system-ui,sans-serif;background:#0f172a;color:#e2e8f0;min-height:100vh}
nav{background:#1e293b;padding:12px 24px;border-bottom:1px solid #334155;display:flex;gap:20px}
nav a{color:#94a3b8;text-decoration:none;font-size:14px;padding:6px 12px;border-radius:4px}
nav a.active,nav a:hover{color:#e2e8f0;background:#334155}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:16px;padding:24px}
.card{background:#1e293b;border-radius:8px;padding:20px;border:1px solid #334155}
.card .label{font-size:12px;color:#94a3b8;text-transform:uppercase;letter-spacing:.5px}
.card .value{font-size:28px;font-weight:700;margin-top:4px}
.section{background:#1e293b;border-radius:8px;padding:16px;margin:0 24px 24px;border:1px solid #334155}
.section h2{font-size:14px;color:#94a3b8;margin-bottom:8px}
.chart{height:320px}
table{width:100%;border-collapse:collapse;margin-top:8px}
th,td{text-align:left;padding:6px 12px;font-size:13px}
th{color:#94a3b8;border-bottom:1px solid #334155}
td{border-bottom:1px solid #1e293b}
.footer{text-align:center;padding:16px;color:#475569;font-size:12px}
</style>"""
EC='<script src="/static/echarts.min.js" defer></script>'

def nav(page):
    def a(p,l): return f'<a href="{p}" class="active">{l}</a>' if p==page else f'<a href="{p}">{l}</a>'
    return f"<nav>{a('/','Home')}{a('/system','System')}{a('/weather','Weather')}</nav>"

CHART_INIT="""<script>
function initCharts(){
  if(typeof echarts==="undefined"){setTimeout(initCharts,200);return;}
  var BO={grid:{left:50,right:20,top:20,bottom:30},tooltip:{trigger:"axis"},xAxis:{data:[],axisLabel:{interval:6,color:"#94a3b8"}},yAxis:{name:"",axisLabel:{color:"#94a3b8"},splitLine:{lineStyle:{color:"#334155"}}},series:[{data:[],type:"line",smooth:true,symbol:"none",lineStyle:{color:"#38bdf8",width:2},areaStyle:{color:"rgba(56,189,248,0.1)"}}]};
  CHART_PLACEHOLDER
}
initCharts();
</script>"""

def chart_js(charts_code):
    return CHART_INIT.replace("CHART_PLACEHOLDER", charts_code)

# ---- Page 1: Home ----
def build_home():
    outdoor=query_one("SELECT * FROM sensor_data WHERE device='esp32-outdoor' AND lux IS NOT NULL ORDER BY id DESC LIMIT 1")
    indoor=query_one("SELECT * FROM sensor_data WHERE device='bbb-indoor' ORDER BY id DESC LIMIT 1")
    devs=query_all("SELECT device,online,last_seen FROM device_status ORDER BY device")
    lux=outdoor.get("lux"); rssi=outdoor.get("rssi"); ts=outdoor.get("timestamp") or ""; now_ts=datetime.now().strftime("%H:%M:%S")
    lux_s=f"{lux:.1f} lx" if lux is not None else "--"
    rssi_s=f"{rssi} dBm" if rssi is not None else "--"
    dr=""
    for d in devs:
        os_str="ONLINE" if d.get("online") else "OFFLINE"; co="#4ade80" if d.get("online") else "#ef4444"
        dr+=f'<tr><td style="color:{co}">&#9679;</td><td>{d["device"]}</td><td>{os_str}</td><td>{d.get("last_seen","")}</td></tr>\n'
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Home Monitor</title>{EC}{CSS}</head><body>
{nav("home")}
<div class="grid"><div class="card"><div class="label">Outdoor Light</div><div class="value">{lux_s}</div></div><div class="card"><div class="label">WiFi RSSI</div><div class="value">{rssi_s}</div></div><div class="card"><div class="label">Local Time</div><div class="value" style="font-size:24px">{now_ts}</div></div><div class="card"><div class="label">Last Update</div><div class="value" style="font-size:14px">{ts}</div></div></div>
<div class="section"><h2>Light Trend (24h)</h2><div id="lux_chart" class="chart"></div></div>
<div class="section"><h2>Devices</h2><table><tr><th></th><th>Device</th><th>Status</th><th>Last Seen</th></tr>{dr}</table></div>
<div class="footer">Home Monitor v5.1</div>
<script>
function loadChart(){{
  if(typeof echarts==="undefined"){{setTimeout(loadChart,200);return;}}
  var chart=echarts.init(document.getElementById("lux_chart"));
  chart.setOption({{grid:{{left:50,right:20,top:20,bottom:30}},tooltip:{{trigger:"axis"}},xAxis:{{data:[],axisLabel:{{interval:6,color:"#94a3b8"}}}},yAxis:{{axisLabel:{{color:"#94a3b8"}},splitLine:{{lineStyle:{{color:"#334155"}}}}}},series:[{{data:[],type:"line",smooth:true}}]}});
  function update(){{fetch("/api/history?limit=288").then(function(r){{return r.json()}}).then(function(h){{chart.setOption({{xAxis:{{data:h.map(function(r){{return r.timestamp}})}},series:[{{data:h.map(function(r){{return r.lux}}),type:"line",smooth:true,symbol:"none",lineStyle:{{color:"#38bdf8",width:2}},areaStyle:{{color:"rgba(56,189,248,0.1)"}}}}]}});}}).catch(function(){{}});}}
  update();setInterval(update,30000);
}}
loadChart();
</script></body></html>"""

# ---- Page 2: System ----
def build_system():
    ct=pi_cpu_temp(); cu=pi_cpu_usage(); m=pi_memory(); d=pi_disk()
    esp=query_one("SELECT * FROM sensor_data WHERE device='esp32-outdoor' ORDER BY id DESC LIMIT 1")
    bbb=query_one("SELECT * FROM sensor_data WHERE device='bbb-indoor' ORDER BY id DESC LIMIT 1")
    ts=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    def v(x,fmt): return fmt.format(x) if x is not None else "--"

    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>System Info</title>{EC}{CSS}</head><body>
{nav("system")}
<div class="grid">
<div class="card"><div class="label">Pi5 CPU Temp</div><div class="value">{v(ct,'{:.1f}C')}</div></div>
<div class="card"><div class="label">Pi5 CPU Usage</div><div class="value">{v(cu,'{:.1f}%')}</div></div>
<div class="card"><div class="label">Pi5 Memory Free</div><div class="value">{v(m[2] if m else None,'{}M')}</div></div>
<div class="card"><div class="label">ESP32 RSSI</div><div class="value">{v(esp.get('rssi'),'{}dBm')}</div></div>
</div>
<div class="section"><h2>Pi5 CPU Temp (24h)</h2><div id="p1" class="chart"></div></div>
<div class="section"><h2>Pi5 CPU Usage (24h)</h2><div id="p2" class="chart"></div></div>
<div class="section"><h2>Pi5 Memory Used (24h)</h2><div id="p3" class="chart"></div></div>
<div class="section"><h2>ESP32 WiFi RSSI (24h)</h2><div id="p4" class="chart"></div></div>
<div class="section"><h2>BBB CPU Usage (24h)</h2><div id="p5" class="chart"></div></div>
<div class="footer">System Info - {ts}</div>
""" + chart_js("""
  var BO=null;
  function mk(id,n){var c=echarts.init(document.getElementById(id));c.setOption({grid:{left:60,right:20,top:20,bottom:30},tooltip:{trigger:"axis"},xAxis:{data:[],axisLabel:{interval:6,color:"#94a3b8"}},yAxis:{name:n||"",nameTextStyle:{color:"#94a3b8",fontSize:11},nameGap:8,axisLabel:{color:"#94a3b8"},splitLine:{lineStyle:{color:"#334155"}}},series:[{data:[],type:"line",smooth:true,symbol:"none",lineStyle:{color:"#38bdf8",width:2},areaStyle:{color:"rgba(56,189,248,0.1)"}}]});return c;}
  var a=mk("p1","C"),b=mk("p2","%"),c=mk("p3","%"),d=mk("p4","dBm"),e=mk("p5","%");
  function L(u,ch,f){fetch(u).then(function(r){return r.json()}).then(function(x){ch.setOption({xAxis:{data:x.map(function(r){return r.timestamp})},series:[{data:x.map(function(r){return r[f]})}]});}).catch(function(){});}
  L("/api/pi_metrics?field=cpu_temp&limit=288",a,"cpu_temp");
  L("/api/pi_metrics?field=cpu_usage&limit=288",b,"cpu_usage");
  L("/api/pi_metrics?field=mem_used&limit=288",c,"mem_used");
  L("/api/esp_rssi",d,"rssi");
  L("/api/bbb_cpu",e,"cpu_usage");
  setInterval(function(){L("/api/pi_metrics?field=cpu_temp&limit=288",a,"cpu_temp");L("/api/pi_metrics?field=cpu_usage&limit=288",b,"cpu_usage");L("/api/pi_metrics?field=mem_used&limit=288",c,"mem_used");L("/api/esp_rssi",d,"rssi");L("/api/bbb_cpu",e,"cpu_usage");},60000);
""") + "</body></html>"

# ---- Page 3: Weather ----
def build_weather():
    w=get_weather()
    if not w:
        return '<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><title>Weather</title>' + EC + CSS + '</head><body>' + nav("weather") + '<div class="section"><p>Failed to fetch weather. Retrying in 30s.</p></div><meta http-equiv="refresh" content="30"></body></html>'
    cur = w.get("current",{})
    dail = w.get("daily",{})
    hour = w.get("hourly",{})
    ct = cur.get("temperature_2m","--")
    ch = cur.get("relative_humidity_2m","--")
    hi = dail.get("temperature_2m_max",["--"])[0]
    lo = dail.get("temperature_2m_min",["--"])[0]
    sr = (dail.get("sunrise",["--"])[0] or "--")[-5:]
    ss = (dail.get("sunset",["--"])[0] or "--")[-5:]
    htimes = json.dumps([t[-5:] for t in hour.get("time",[])[:24]])
    htemps = json.dumps(hour.get("temperature_2m",[])[:24])
    ddays = json.dumps([t[-5:] for t in dail.get("time",[])])
    dhi = json.dumps(dail.get("temperature_2m_max",[]))
    dlo = json.dumps(dail.get("temperature_2m_min",[]))
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Weather</title>{EC}{CSS}</head><body>
{nav("weather")}
<div class="grid">
<div class="card"><div class="label">Current Temp</div><div class="value">{ct}C</div></div>
<div class="card"><div class="label">Humidity</div><div class="value">{ch}%</div></div>
<div class="card"><div class="label">High / Low</div><div class="value" style="font-size:22px">{hi}C / {lo}C</div></div>
<div class="card"><div class="label">Sunrise / Sunset</div><div class="value" style="font-size:20px">{sr} / {ss}</div></div>
</div>
<div class="section"><h2>Today Hourly Temperature</h2><div id="c1" class="chart"></div></div>
<div class="section"><h2>5-Day High / Low</h2><div id="c2" class="chart"></div></div>
<div class="footer">Weather data from Open-Meteo (ECMWF)</div>
<script>
function initWx(){{
  if(typeof echarts==="undefined"){{setTimeout(initWx,200);return;}}
  var c1=echarts.init(document.getElementById("c1"));
  c1.setOption({{grid:{{left:50,right:20,top:20,bottom:30}},tooltip:{{trigger:"axis"}},xAxis:{{data:{htimes},axisLabel:{{color:"#94a3b8"}}}},yAxis:{{name:"C",axisLabel:{{color:"#94a3b8"}},splitLine:{{lineStyle:{{color:"#334155"}}}}}},series:[{{data:{htemps},type:"line",smooth:true,symbol:"none",lineStyle:{{color:"#f59e0b",width:2}},areaStyle:{{color:"rgba(245,158,11,0.1)"}}}}]}});
  var c2=echarts.init(document.getElementById("c2"));
  c2.setOption({{grid:{{left:50,right:20,top:20,bottom:30}},tooltip:{{trigger:"axis"}},xAxis:{{data:{ddays},axisLabel:{{color:"#94a3b8"}}}},yAxis:{{name:"C",axisLabel:{{color:"#94a3b8"}},splitLine:{{lineStyle:{{color:"#334155"}}}}}},series:[{{name:"High",data:{dhi},type:"line",smooth:true,symbol:"none",lineStyle:{{color:"#ef4444",width:2}}}},{{name:"Low",data:{dlo},type:"line",smooth:true,symbol:"none",lineStyle:{{color:"#3b82f6",width:2}}}}]}});
}}
initWx();
</script></body></html>"""

@app.route("/")
def index():
    return build_home()
@app.route("/system")
def system():
    return build_system()
@app.route("/weather")
def weather():
    return build_weather()
@app.route("/ping")
def ping():
    return "pong"

@app.route("/api/current")
def api_current():
    s=query_all("SELECT * FROM sensor_data s1 WHERE id IN (SELECT MAX(id) FROM sensor_data GROUP BY device)")
    t=query_all("SELECT device,online,last_seen FROM device_status")
    return jsonify({"sensors":s,"status":t})

@app.route("/api/history")
def api_history():
    # 24h window, 5-min aggregated
    rows=query_all("SELECT printf('%02d:%02d',cast(strftime('%H',timestamp) as integer),(cast(strftime('%M',timestamp) as integer)/5)*5) as ts,round(avg(lux),1) as lux FROM sensor_data WHERE device='esp32-outdoor' AND lux IS NOT NULL AND timestamp>=datetime('now','localtime','-24 hours') GROUP BY ts ORDER BY MIN(timestamp)")
    return jsonify([{"timestamp":r["ts"],"lux":r["lux"]} for r in rows])

@app.route("/api/pi_metrics")
def api_pi_metrics():
    field=request.args.get("field","cpu_temp"); limit=min(int(request.args.get("limit",288)),500)
    rows=query_all("SELECT printf('%02d:%02d',cast(strftime('%H',timestamp) as integer),(cast(strftime('%M',timestamp) as integer)/5)*5) as ts,round(avg("+field+"),1) as val FROM sensor_data WHERE device='pi-system' AND timestamp>=datetime('now','localtime','-24 hours') GROUP BY ts ORDER BY MIN(timestamp) LIMIT ?", (limit,))
    if field == "mem_used":
        mt,mu,mf = pi_memory()
        total_mb = mt if mt else 8192
        result = []
        for r in rows:
            v = r["val"]
            result.append({"timestamp":r["ts"],field:round(v/total_mb*100,1) if v is not None else None})
        return jsonify(result)
    return jsonify([{"timestamp":r["ts"],field:r["val"]} for r in rows])

@app.route("/api/esp_rssi")
def api_esp_rssi():
    rows=query_all("SELECT printf('%02d:%02d',cast(strftime('%H',timestamp) as integer),(cast(strftime('%M',timestamp) as integer)/5)*5) as ts,round(avg(rssi),1) as rssi FROM sensor_data WHERE device='esp32-outdoor' AND rssi IS NOT NULL AND timestamp>=datetime('now','localtime','-24 hours') GROUP BY ts ORDER BY MIN(timestamp)")
    return jsonify([{"timestamp":r["ts"],"rssi":r["rssi"]} for r in rows])

@app.route("/api/bbb_cpu")
def api_bbb_cpu():
    rows=query_all("SELECT printf('%02d:%02d',cast(strftime('%H',timestamp) as integer),(cast(strftime('%M',timestamp) as integer)/5)*5) as ts,round(avg(cpu_usage),1) as cpu_usage FROM sensor_data WHERE device='bbb-indoor' AND cpu_usage IS NOT NULL AND timestamp>=datetime('now','localtime','-24 hours') GROUP BY ts ORDER BY MIN(timestamp)")
    return jsonify([{"timestamp":r["ts"],"cpu_usage":r["cpu_usage"]} for r in rows])

if __name__ == "__main__": app.run(host="0.0.0.0", port=5000, debug=False)
