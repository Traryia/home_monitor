#!/bin/bash
# 天气显示屏启动器 (幂等): 已在运行则先杀再起
# 用途: labwc autostart / 桌面图标「天气显示」/ ssh 手动唤出
# 最小化后点桌面图标 = 重启恢复 (labwc 无任务栏, 最小化窗口无法直接点回)
pkill -f "chromium.*chromium-kiosk" 2>/dev/null
sleep 1
exec chromium --user-data-dir=/home/pi/.config/chromium-kiosk --kiosk --disable-pinch \
  --force-device-scale-factor=1 --noerrdialogs --disable-infobars --no-first-run \
  --disable-session-crashed-bubble --ozone-platform=wayland \
  file:///home/pi/home_monitor/pi_display/weather.html
