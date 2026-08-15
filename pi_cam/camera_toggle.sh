#!/bin/bash
# 摄像头画面开关 — 在 Pi 屏幕上打开/关闭摄像头画面窗口
if pgrep -f "chromium.*--app=http://127.0.0.1:8080" >/dev/null; then
  pkill -f "chromium.*--app=http://127.0.0.1:8080"
else
  sudo -n systemctl start camera-stream
  chromium --app=http://127.0.0.1:8080/ \
    --user-data-dir=$HOME/.config/chromium-cam \
    --ozone-platform=wayland --window-size=1296,780 \
    --no-first-run --noerrdialogs --password-store=basic >/dev/null 2>&1 &
fi
