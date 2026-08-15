================================================================
  home_monitor 项目 - 设备拓扑与连接指南
================================================================

日期: 2026-07-21

----------------------------------------------------------------
  网络拓扑
----------------------------------------------------------------

 本地PC (192.168.3.100, Windows)
    │
    └── WiFi ─── 路由器 (192.168.3.1)
                    │
         ┌──────────┼──────────┐
         │          │          │
    树莓派5      ESP32-S3
   wlan0:        WiFi IP:
   192.168.3.36  192.168.3.39
         │                        (当前通过mpremote操作)
         │ USB ───┐
         │        │
       eth1     /dev/ttyACM0 (BBB串口控制台)
    192.168.7.1  │
         │     /dev/ttyACM1 (ESP32 mpremote)
      AM3358 BBB │
      usb0:      │
      192.168.7.2│
      eth0:      │
      192.168.   │
    .10.2────────┘── 网线 ── Pi eth0: 192.168.10.1

----------------------------------------------------------------
  设备清单
----------------------------------------------------------------

[A] 树莓派 5
  角色: 跳板机 / 数据网关
  OS:   Debian (Linux 6.18.34+rpt-rpi-2712, aarch64)
  网络:
    wlan0: 192.168.3.36/24  (WiFi, 主通道)
    eth0:  192.168.10.1/30  (网线直连 BBB)
    eth1:  192.168.7.1/30   (USB gadget 连接 BBB)
  SSH:  ssh pi5  (已配密钥, 用户 pi)
  ESP32: /dev/ttyACM1 (mpremote)
  BBB 串口: /dev/ttyACM0 (115200, 8N1)

[B] AM3358 (BeagleBone Black)
  角色: 主控 / 数据处理
  OS:   Debian 13 Trixie (Kernel 5.10.168-ti-r84, armv7l)
  用户: debian / 123456
  网络:
    usb0: 192.168.7.2/30  (USB gadget, 通 Pi eth1)
    eth0: 192.168.10.2/30 (网线直连, 通 Pi eth0)
  访问方式:
    - SSH via USB:  ssh debian@192.168.7.2 (已配密钥, 免密)
    - SSH via 网线: ssh debian@192.168.10.2
    - 串口控制台:  /dev/ttyACM0 on Pi (115200)
  网络管理: systemd-networkd
    /etc/systemd/network/eth0.network  (静态 192.168.10.2/30)
    /etc/systemd/network/usb0.network  (静态 192.168.7.2/30)

[C] ESP32-S3 (微雪 Waveshare)
  角色: 户外传感器节点 (5传感器)
  芯片: ESP32-S3, 240MHz, 8MB PSRAM, 16MB Flash
  WiFi: 192.168.3.39 (STA, SSID: HUAWEI-FI18J2)
  连接: 直连PC USB COM5 (mpremote), 或通过 Pi USB /dev/ttyACM1
  固件: main.py v4.0 (MQTT, 5传感器, 2s上报, NTP对时+断网缓存补传)
  传感器:
    - BH1750 光照    (I2C: SDA=GPIO4, SCL=GPIO17,  addr 0x23, ADDR=LOW)
    - BMP280 气压温度 (I2C: SDA=GPIO38, SCL=GPIO39, addr 0x76)
    - SHT30  温湿度   (I2C: SDA=GPIO41, SCL=GPIO42, addr 0x44)
    - ADS1115 ADC    (I2C: SDA=GPIO43, SCL=GPIO44, addr 0x48, A0+A1)
  数据上报: MQTT home/sensors → Pi5 Mosquitto:1883 (每2秒, 断网缓存补传)
  备份固件: main.py.bak (MQTT旧版, BH1750 only)
            main.py.bak2 (UDP旧版, BH1750 only)
            main.py.udp.bak (UDP更早版)
  运行时文件: spool.jsonl (v4.0 断网缓存, 仅断网时出现)
  注: flash 已清理 (2026-08-09 删除约30个 tmp_*.py 一次性测试脚本)

[D] 树莓派 (第二台, 摄像头节点, 2026-08-15 接入)
  角色: USB 摄像头内网直播
  OS:   Debian 13 Trixie (aarch64), labwc + lightdm
  WiFi: 192.168.3.41, 账户 pi (已装同一把 ed25519 公钥, 免密)
  屏幕: 微雪 3.5inch HDMI LCD (E) 640x480, 触控走 USB-C 免驱
        (0eef:0005 WaveShare WS170120, hid-multitouch);
        I2C 触控尝试失败 (芯片不上总线), 详见 CHANGELOG 2026-08-15
  摄像头: MagicView-UVC800 (UVC 免驱, /dev/video0)
  直播: ustreamer → MJPEG http://192.168.3.41:8080 (720p, 多客户端)
        systemd camera-stream.service 托管 (已 enable 开机自启)
        udev 规则 99-camera-stream.rules: 插入自动启动, 拔出自动停止
        桌面「摄像头」图标双击 = 本机屏幕弹窗看画面, 再击关闭
        (~/camera_toggle.sh → chromium --app 127.0.0.1:8080)
  延时摄影 (2026-08-15, 花园月季生长记录):
        camera-timelapse.timer 每 10 分钟抓一帧 (ustreamer /snapshot,
        不占摄像头), 存 ~/timelapse/YYYY-MM-DD_HHMMSS.jpg, latest.jpg
        软链指向最新; Persistent=true 断电恢复后补拍
  代码: 仓库 pi_cam/ (service / toggle / udev规则 / camera_web页面 /
        timelapse_snap.sh + camera-timelapse.{service,timer};
        camera_stream.py 为 v1 单客户端版, 已被 ustreamer 取代, 留档)

----------------------------------------------------------------
  常用命令
----------------------------------------------------------------

  # 跳板机 (从本地 Windows)
  ssh pi5

  # BBB via USB
  ssh pi5 "ssh debian@192.168.7.2"

  # BBB via 网线
  ssh pi5 "ssh debian@192.168.10.2"

  # ESP32 操作
  ssh pi5 "python3 -m mpremote connect /dev/ttyACM1 fs ls"
  ssh pi5 "python3 -m mpremote connect /dev/ttyACM1 fs cat main.py"

  # ESP32 也可直连 PC (COM5), 本地刷机:
  #   /c/Windows/py.exe -m mpremote connect COM5 fs cp main.py :main.py
  #   (raw repl 偶发进入失败, 重试即可)

  # Pi 上无 sqlite3 CLI, DB 操作用 python3 -c 或 scp 脚本执行

----------------------------------------------------------------
  已完成配置
----------------------------------------------------------------

  [x] Pi → BBB SSH 密钥认证 (免密)
  [x] Pi eth0 ↔ BBB eth0 网线直连 (192.168.10.0/30)
  [x] BBB eth0 静态IP持久化 (systemd-networkd)
  [x] ESP32 固件读取与备份
  [x] RustDesk 1.4.9 远控 (2026-08-10): rustdesk.service 自启;
      Wayland 抓屏走 pipewire + portal-wlr (config 已固定 HDMI-A-1,
      免弹选择器); ID/密码见本机记录, 勿入仓库



================================================================

================================================================
  Dashboard v7.0 - Web仪表盘 (2026-07-22)
================================================================

URL: http://192.168.3.36:5000

三页结构:
  / (Home)     - 光照/T/H/P/ADC卡片 + 6条24h time轴曲线 + 设备状态
  /system      - Pi5/ESP32/BBB系统信息 + 5条24h time轴趋势图
  /weather     - Open-Meteo ECMWF天气 + 24h温度曲线 + 5天预报

API端点:
  GET /ping                  - 连通性测试
  GET /api/current           - 所有设备最新数据和在线状态
  GET /api/history           - ESP32光照24h历史(5分钟聚合)
  GET /api/sensor_history?field=<name> - 通用传感器24h历史(temp/hum/pres/rssi/adc etc)
  GET /api/pi_metrics        - Pi系统指标24h历史
  GET /api/esp_rssi          - ESP32 WiFi RSSI 24h历史 (500错误待修复)
  GET /api/bbb_cpu           - BBB CPU占用率 24h历史 (500错误待修复)

数据流:
  ESP32 --(WiFi/MQTT:2s)--> Mosquitto:1883 --> mqtt_collector.py v4.0 --> SQLite (17列)
  BBB   --(MQTT:10s)-------> Mosquitto:1883 --> mqtt_collector.py --> SQLite
  Pi5   --(内部proc/sys:10s)--> mqtt_collector.py --> SQLite
  Flask dashboard.py v7.0 --> SQLite --> HTML + ECharts(time轴,6曲线)

数据库:
  sensor_data: 24h历史, 5分钟聚合, GROUP BY ts
  device_status: 设备在线状态, 45s超时判定离线

备忘:
  * Open-Meteo API 从Pi直连被GFW阻断, dashboard.service需代理
  * PowerShell SSH引号转义: 复杂命令先scp脚本再远程执行
  * SQL别名不与列名同名: 用ts代替timestamp
  * 本地dashboard.py必须与Pi保持一致, scp确认方向


================================================================
  pi_display 天气显示屏 (2026-08-02 上线)
================================================================

硬件: 微雪 1024x600 HDMI 触摸屏 (HDMI-A-1, 触控已映射 labwc rc.xml)
系统: labwc + lightdm autologin pi, Chromium kiosk

页面: pi_display/weather.html  三页, 手动滑动/圆点切换 (无自动轮播)
  P1 概览: 时钟/城市/大温度/天气摘要/AQI/高温降雨提醒
           + 今日温度曲线(大卡, 0~24时, 日出日落虚线+当前时刻点)
           + 明日温度曲线(小卡) + 10日预报  (v6.8)
  P3 室外 (v7.0): ESP32 实时温度/湿度/气压/光照大卡 + 24h温度/7天温度/
           24h光照曲线 + 传感器状态 + ADC电压; 数据来自本机 dashboard
           (:5000 /api/current + /api/outdoor), 实时卡 2s 轮询 (v7.2,
           曾 30s 导致手电测试感知延迟 ~20s), 曲线 10 分钟, 离线变灰
  P2 详情 (4列x3行): 平均 | 体感 | 风(左数据+右罗盘, 占2格)
                     紫外线 | 日出(弧线) | 月相(左数据+右月图, 占2格)
                     湿度 | 气压(表盘) | 降水 | 能见度
数据: Open-Meteo 预报+空气质量 API (Pi 直连可达), 30分钟刷新, 失败显示缓存
      月相为本地天文算法; AQI 按 HJ 633-2012 国标由 PM2.5/PM10 估算
主题: 白天/夜晚自动切换, 夜间星空背景

Pi 上的位置:  /home/pi/home_monitor/pi_display/weather.html
开机自启:     ~/.config/labwc/autostart
桌面图标:     ~/Desktop/天气显示.desktop  (双击唤出)
临时退出:     Alt+F4  或  ssh pi@192.168.3.36 "pkill chromium"
永久关自启:   注释 autostart 里的 chromium 行

Chromium 启动参数 (v6.2 踩坑后定稿, 缺一不可):
  --user-data-dir=/home/pi/.config/chromium-kiosk
      专用 profile! 默认 profile 的 Local State 固化了 device_scale_factor
      0.75, 曾导致全页渲染成 75% ("字体变小"), 专用干净 profile 根治
  --force-device-scale-factor=1     防止 DPR 漂移
  --disable-pinch                   禁止触屏双指缩放
  --kiosk --noerrdialogs --disable-infobars --no-first-run
  --disable-session-crashed-bubble --ozone-platform=wayland

运维手册: pi_display/DEPLOY.md
  (scp 更新页面 / grim 远程截图 / #p2 调试页 / CDP 远程量 innerWidth,DPR)

----------------------------------------------------------------
  2026-08-02 工作区变更
----------------------------------------------------------------
  [x] D:\Work 清理: 删除约110个一次性补丁脚本和 dashboard .bak 备份
  [x] home_monitor/ 初始化 git 仓库 (版本历史今后由 git 承担)
  [x] Traryia 本机 ed25519 密钥直连 pi@192.168.3.36
      (README 旧述 "ssh pi5 别名" 的配置已不存在, 直接用 IP)
  [x] 天气显示屏 v6.2 上线 (设计迭代见 CHANGELOG 2026-08-02 各条目)


================================================================
  经验总结 (2026-08-02)
================================================================

[版本控制]
  * git 第一天上手就救场: 被否决的布局用 git show <id>:<file> 秒级找回
  * 不再手动留 .bak; 改文件前先 commit, 工作区只留当前一份
  * .gitattributes 强制 LF: 文件要 scp 到 Linux 运行, 防 Windows CRLF 混入

[kiosk / 显示调试]
  * kiosk 浏览器必须用独立 --user-data-dir, 不与桌面浏览共用 profile
    (默认 profile 可能固化历史缩放 -> 整页渲染 75%, 表现为"字体变小")
  * 先量再改: --remote-debugging-port=9222 + ssh -L 转发 + CDP
    Runtime.evaluate 直接读 innerWidth/devicePixelRatio, 不靠猜
  * grim 截图 = 合成器 buffer = 屏幕真相, 以其为准
  * chromium 单例会吞掉第二次启动的参数和 URL, 多开调试用独立 profile
  * JS/CSS 修不了渲染管线问题 (DPR/合成器), 别在页面里做缩放抵消
  * websocket 连 CDP 需 suppress_origin=True 或 --remote-allow-origins

[UI 设计 (用户标准)]
  * 数值粗体 (600/700), 子标签粗体白字, 标题带灰色小图标
  * 一卡一模块, 宽卡用"左数据行+右图形"并排填满, 不上下堆叠
  * 页数宁少勿多, 绝不自动轮播 (除非用户明确要求)
  * 1024x600 参考值: 主数值 42-46px, 轮盘 130px+, 卡片 240px 宽

[工作区卫生]
  * 一次性补丁脚本 (scp 到设备执行的) 用完即删, 不堆积在根目录
  * 删除前确认效果已在设备上生效; 项目历史由 git+CHANGELOG 承担

[SSH / 部署]
  * 密码仅用于首次装公钥, 之后全部走密钥, 密码不落盘
  * 页面类交付流程: 本地改 -> 浏览器预览验证 -> scp -> 实机 grim 截图
    确认 -> git commit, 一步不验不往下走
