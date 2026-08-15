#!/bin/bash
# 摄像头直播开关 — 桌面图标调用 (再点一次停止)
if systemctl is-active --quiet camera-stream; then
  sudo -n systemctl stop camera-stream
else
  sudo -n systemctl start camera-stream
fi
