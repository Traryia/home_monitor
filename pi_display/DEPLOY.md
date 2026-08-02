# pi_display 天气显示屏

树莓派5 外接微雪 1024x600 HDMI 触摸屏，Chromium kiosk 全屏显示 `weather.html`。

## 文件

- `weather.html` — 天气页面（Open-Meteo 预报 + 空气质量，客户端每 30 分钟拉取）
- `wx_shot_v*.png` — 各版本效果截图（v3 为 Pi 实机 grim 截图）

## 部署（PC → Pi）

```bash
scp weather.html pi@192.168.3.36:/home/pi/home_monitor/pi_display/weather.html
```

页面有 6 小时自动整页重载，平时改完 scp 上去最多 6 小时生效；
立即生效需在 Pi 上重启 Chromium（或 `pkill chromium`，autostart 不自动拉起，
手动重启命令见下）。

## Pi 上的配置

- 页面位置: `/home/pi/home_monitor/pi_display/weather.html`
- 开机自启: `~/.config/labwc/autostart` → chromium --kiosk（labwc 会话，autologin pi）
- 手动启动（ssh 中）:

```bash
export XDG_RUNTIME_DIR=/run/user/1000 WAYLAND_DISPLAY=wayland-0
nohup chromium --user-data-dir=/home/pi/.config/chromium-kiosk --kiosk --disable-pinch \
  --force-device-scale-factor=1 --noerrdialogs --disable-infobars --no-first-run \
  --disable-session-crashed-bubble --ozone-platform=wayland \
  file:///home/pi/home_monitor/pi_display/weather.html >/tmp/chromium.log 2>&1 &
```

- `--user-data-dir=~/.config/chromium-kiosk`: kiosk 专用 profile。2026-08-02 发现
  默认 profile 的 Local State 固化了 device_scale_factor 0.75（浏览过别的网站所致），
  页面所有 px 内容渲染为 75%（"字体变小"）；专用干净 profile 根治且与桌面浏览隔离
- `--force-device-scale-factor=1`: 保险，防止 DPR 漂移
- `--disable-pinch`: 禁止触屏双指缩放
- 截图调试另一页: URL 加 `#p2`（页内需 go(1)），或临时 `--remote-debugging-port=9222`
  + `ssh -L 9222:127.0.0.1:9222` 后用 CDP Runtime.evaluate 查 innerWidth/devicePixelRatio
  （websocket 客户端需 suppress_origin）
- 注意: chromium 单例模式会忽略第二次启动的参数和 URL，调试多开需 --user-data-dir 隔离
- 屏幕截图验证: `grim /tmp/shot.png`（同上的环境变量）
- 无 DPMS 熄屏配置，屏幕常亮；页面自身带 Wake Lock 兜底

## 退出 / 唤出

- 临时退出: 键盘 Alt+F4，或 `ssh pi@192.168.3.36 "pkill chromium"`
- 唤出: 重启自动拉起（autostart）；或双击桌面图标「天气显示」
  (`~/Desktop/天气显示.desktop`, 2026-08-02 创建)；或 ssh 手动启动命令（见上）
- 永久关闭自启: `sed -i 's|^chromium|#chromium|' ~/.config/labwc/autostart`

## 数据源

- 预报: api.open-meteo.com（WMO 天气码 → 中文 + SVG 图标）
- 空气: air-quality-api.open-meteo.com（PM2.5/PM10 按 HJ 633-2012 国标折点算 CN AQI）
- Pi 直连两个 API 均可达（2026-08-02 实测 HTTP 200）
