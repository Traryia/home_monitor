#!/bin/bash
# 月季生长延时记录: 每 10 分钟抓一帧
# 走 ustreamer /snapshot 接口, 不独占摄像头 (直播/本机画面不受影响)
DIR=/home/pi/timelapse
mkdir -p "$DIR"
F="$DIR/$(date +%Y-%m-%d_%H%M%S).jpg"
if curl -sf --max-time 10 http://127.0.0.1:8080/snapshot -o "$F" && [ -s "$F" ]; then
  :
else
  rm -f "$F"
  echo "snapshot failed $(date -Is)" >&2
  exit 1
fi
