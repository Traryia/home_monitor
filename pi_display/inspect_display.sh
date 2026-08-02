#!/bin/bash
# Read-only inspection: Pi5 external display + desktop environment
# No system changes are made by this script.

echo "===== OS ====="
uname -a
grep PRETTY /etc/os-release
echo

echo "===== DRM connectors ====="
for d in /sys/class/drm/card*-*; do
  [ -e "$d/status" ] || continue
  name=$(basename "$d")
  status=$(cat "$d/status" 2>/dev/null)
  echo "$name: $status"
  if [ "$status" = "connected" ]; then
    echo "  modes (EDID):"
    head -15 "$d/modes" 2>/dev/null | sed 's/^/    /'
  fi
done
echo

echo "===== cmdline ====="
cat /boot/firmware/cmdline.txt 2>/dev/null || cat /boot/cmdline.txt 2>/dev/null
echo

echo "===== config.txt display lines ====="
grep -Ei 'hdmi|display|rotate|dtoverlay|kms' /boot/firmware/config.txt 2>/dev/null
echo

echo "===== desktop processes ====="
ps -eo comm | grep -Ei 'wayfire|labwc|Xorg|weston|lxpanel|lightdm|greetd|gdm|cage' | sort -u
echo "-- (empty = no desktop running) --"
echo

echo "===== boot target / autologin ====="
systemctl get-default
raspi-config nonint get_autologin 2>/dev/null
raspi-config nonint get_boot_cli 2>/dev/null
echo

echo "===== browsers / wayland tools ====="
for b in chromium chromium-browser firefox wlr-randr kmsprint modetest cage seatd; do
  p=$(command -v "$b" 2>/dev/null) && echo "$b -> $p"
done
dpkg -l 2>/dev/null | grep -Ei 'chromium|labwc|wayfire|weston|xserver-xorg' | awk '{print $2, $3}'
echo

echo "===== sessions ====="
who
loginctl list-sessions --no-legend 2>/dev/null
echo

echo "===== DRI / backlight ====="
ls /dev/dri/ 2>/dev/null
ls /sys/class/backlight/ 2>/dev/null
echo

echo "===== open-meteo reachability ====="
curl -s -o /dev/null -w "open-meteo HTTP %{http_code} in %{time_total}s\n" --max-time 10 \
  "https://api.open-meteo.com/v1/forecast?latitude=31.23&longitude=121.47&current=temperature_2m" \
  || echo "open-meteo UNREACHABLE"
echo

echo "===== dashboard service ====="
systemctl is-active dashboard.service 2>/dev/null
systemctl show dashboard.service -p Environment 2>/dev/null
echo

echo "===== autostart locations ====="
ls -la "$HOME/.config/labwc/" 2>/dev/null
ls -la "$HOME/.config/wayfire.ini" 2>/dev/null
ls -la "$HOME/.config/autostart/" 2>/dev/null
ls /etc/xdg/autostart/ 2>/dev/null | head -20
echo

echo "===== memory ====="
free -h | head -2
echo
echo "INSPECT_DONE"
