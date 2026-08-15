#!/bin/bash
# 摄像头直播守门: 仅 04:30~18:00 运行 ustreamer, 其余时间退出 (节电)
# 夜间退出码为 0 (正常退出), 不触发 systemd Restart 重试
HM=$(date +%H%M)
if [ "$HM" -lt 430 ] || [ "$HM" -ge 1800 ]; then
  exit 0
fi
exec /usr/bin/ustreamer --device=/dev/video0 --host=0.0.0.0 --port=8080 \
  --resolution=1280x720 --format=MJPEG --desired-fps=15 \
  --static=/home/pi/camera_web
