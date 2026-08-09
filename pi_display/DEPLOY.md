# pi_display 天气显示屏

树莓派5 外接微雪 1024x600 HDMI 触摸屏，Chromium kiosk 全屏显示 `weather.html`。

## 文件

- `weather.html` — 天气页面（Open-Meteo 预报 + 空气质量，客户端每 30 分钟拉取）
- `kiosk_control.py` — kiosk 控制服务（127.0.0.1:8977，仅供页面按钮调用）：
  `/close` 关闭 Chromium（页面按钮两段确认）、`/minimize` 最小化（wtype 注入 A-F9 → labwc Iconify）
- `wx_launch.sh` — 幂等启动器（已在运行则先杀再起）：autostart、桌面图标、ssh 手动唤出统一入口
- `wx_*.png` — 各版本效果截图（最新定稿: `wx_v69.png` P1 / `wx_v68_p2.png` P2 / `wx_v71_p3.png` P3, Pi 实机 grim）

## 部署（PC → Pi）

```bash
scp weather.html pi@192.168.3.36:/home/pi/home_monitor/pi_display/weather.html
```

页面有 6 小时自动整页重载，平时改完 scp 上去最多 6 小时生效；
立即生效需在 Pi 上重启 Chromium（或 `pkill chromium`，autostart 不自动拉起，
手动重启命令见下）。

## Pi 上的配置

- 页面位置: `/home/pi/home_monitor/pi_display/weather.html`
- 开机自启: `~/.config/labwc/autostart` → kiosk_control.py + wx_launch.sh（labwc 会话，autologin pi）
- 手动启动（ssh 中）:

```bash
export XDG_RUNTIME_DIR=/run/user/1000 WAYLAND_DISPLAY=wayland-0
nohup /home/pi/home_monitor/pi_display/wx_launch.sh >/tmp/chromium.log 2>&1 &
```

- `--user-data-dir=~/.config/chromium-kiosk`: kiosk 专用 profile。2026-08-02 发现
  默认 profile 的 Local State 固化了 device_scale_factor 0.75（浏览过别的网站所致），
  页面所有 px 内容渲染为 75%（"字体变小"）；专用干净 profile 根治且与桌面浏览隔离
- `--force-device-scale-factor=1`: 保险，防止 DPR 漂移
- `--disable-pinch`: 禁止触屏双指缩放
- 截图调试另一页: URL 加 `#p1`/`#p2`/`#p3`（页内需对应 go(n)），或临时 `--remote-debugging-port=9222`
  + `ssh -L 9222:127.0.0.1:9222` 后用 CDP Runtime.evaluate 查 innerWidth/devicePixelRatio
  （websocket 客户端需 suppress_origin）
- 注意: chromium 单例模式会忽略第二次启动的参数和 URL，调试多开需 --user-data-dir 隔离
- 屏幕截图验证: `grim /tmp/shot.png`（同上的环境变量）
- 无 DPMS 熄屏配置，屏幕常亮；页面自身带 Wake Lock 兜底

## 退出 / 唤出 / 最小化

- 页面左上角有「—」最小化 和「×」关闭按钮（v6.9+，经 kiosk_control.py 执行）：
  - 最小化：单击，窗口 Iconify 到底部任务栏，点任务栏「新吴区天气」或桌面图标可恢复
  - 关闭：两段确认（第一次点变红「确认关闭」，3 秒内再点执行），防止触屏误触
- 键盘: Alt+F4 关闭，Alt+F9 最小化（rc.xml 键绑 Iconify），或 `ssh pi@192.168.3.36 "pkill chromium"`
- 唤出: 重启自动拉起（autostart）；或双击桌面图标「天气显示」；或 ssh 手动启动（见上）。
  桌面图标和 ssh 启动统一走 `wx_launch.sh`（幂等：已在运行则先杀再起）
- 永久关闭自启: `sed -i 's|^chromium|#chromium|;s|^python3|#python3|;s|^/home|#/home|' ~/.config/labwc/autostart`
- labwc 改配置后生效: `LABWC_PID=$(pgrep -x labwc|head -1) labwc --reconfigure`
  （0.9.x 需要 LABWC_PID 环境变量）

## 数据源

- 预报: api.open-meteo.com（WMO 天气码 → 中文 + SVG 图标）
- 空气: air-quality-api.open-meteo.com（PM2.5/PM10 按 HJ 633-2012 国标折点算 CN AQI）
- Pi 直连两个 API 均可达（2026-08-02 实测 HTTP 200）
