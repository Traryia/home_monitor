#!/bin/bash
# 月季生长延时记录: 每 10 分钟抓一帧, 仅白天 04:30~18:00 (摄像头无夜视)
# 走 ustreamer /snapshot 接口, 不独占摄像头 (直播/本机画面不受影响)
HM=$(date +%H%M)
[ "$HM" -ge 430 ] && [ "$HM" -lt 1800 ] || exit 0
DIR=/home/pi/timelapse
mkdir -p "$DIR"
F="$DIR/$(date +%Y-%m-%d_%H%M%S).jpg"
if curl -sf --max-time 10 http://127.0.0.1:8080/snapshot -o "$F" && [ -s "$F" ]; then
  # 摄像头侧装, 无损旋转 90° 转正 (jpegtran -rotate 270 = 逆时针90°)
  jpegtran -rotate 270 -perfect -outfile "$F" "$F" 2>/dev/null || true
else
  rm -f "$F"
  echo "snapshot failed $(date -Is)" >&2
  exit 1
fi
