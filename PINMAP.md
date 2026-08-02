================================================================
  PINMAP — home_monitor 项目全设备引脚定义
================================================================

日期: 2026-07-21

----------------------------------------------------------------
  [A] Raspberry Pi 5 Model B (8GB)
----------------------------------------------------------------

角色: MQTT Broker + 数据中枢 + Web 服务器
IP:   192.168.3.36 (WiFi), 192.168.7.1 (USB), 192.168.10.1 (网线)
OS:   Debian Linux 6.18.34+rpt-rpi-2712, aarch64

=== GPIO 排针 J8 (40-pin) ===

           3V3  (1)  (2)  5V
         GPIO2  (3)  (4)  5V
         GPIO3  (5)  (6)  GND
         GPIO4  (7)  (8)  GPIO14
           GND  (9)  (10) GPIO15
        GPIO17  (11) (12) GPIO18
        GPIO27  (13) (14) GND
        GPIO22  (15) (16) GPIO23
           3V3  (17) (18) GPIO24
        GPIO10  (19) (20) GND
         GPIO9  (21) (22) GPIO25
        GPIO11  (23) (24) GPIO8
           GND  (25) (26) GPIO7
        GPIO0*  (27) (28) GPIO1*   (*ID EEPROM专用)
         GPIO5  (29) (30) GND
         GPIO6  (31) (32) GPIO12
        GPIO13  (33) (34) GND
        GPIO19  (35) (36) GPIO16
        GPIO26  (37) (38) GPIO20
           GND  (39) (40) GPIO21

I2C-1 总线: GPIO2=SDA(pin3), GPIO3=SCL(pin5)  [板载 1.8k上拉到 3.3V]

=== 本项目 Pi5 连接状态 ===
pins 3+5:  I2C-1 空闲可用
USB:       连接 ESP32 (/dev/ttyACM1) + AM3358 (/dev/ttyACM0)
eth0:      网线直连 AM3358 (192.168.10.1/30)
eth1:      USB gadget → AM3358 usb0 (192.168.7.1/30)
wlan0:     WiFi (192.168.3.36/24)

---  pinout Pi5 结束  ---

----------------------------------------------------------------
  [B] ESP32-S3 — 微雪 (Waveshare) 开发板
----------------------------------------------------------------

角色: 户外传感器节点 (WiFi STA)
芯片: ESP32-S3, 240MHz, 8MB PSRAM, 16MB Flash
IP:   192.168.3.39 (DHCP, WiFi SSID: HUAWEI-FI18J2)
连接: 通过 Pi5 USB → /dev/ttyACM1 (mpremote)
固件: main.py v10 (MQTT, BH1750, WS2812)

=== P1 左侧排针 (22 pins) ===

 1: 3V3    2: 3V3    3: RST    4: IO4     5: IO5
 6: IO6    7: IO7    8: IO15   9: IO16   10: IO17
11: IO18   12: IO8   13: IO3   14: IO46  15: IO9
16: IO10   17: IO11  18: IO12  19: IO13  20: IO14
21: 5V     22: GND

=== P2 右侧排针 (22 pins) ===

 1: GND    2: IO43(TX)  3: IO44(RX)  4: IO1     5: IO2
 6: IO42   7: IO41      8: IO40       9: IO39   10: IO38
11: IO37   12: IO36    13: IO35      14: IO0    15: IO45
16: IO48   17: IO47    18: IO21      19: IO20  20: IO19
21: GND    22: GND

=== 关键功能引脚 ===
I2C (推荐):   IO21=SDA(P2.18), IO20=SCL(P2.19)  [板载上拉]
UART0:       IO43=TX(P2.2),   IO44=RX(P2.3)
ADC1:        IO4-IO7(P1.4-7), IO8-IO10(P1.12-16)
WS2812 LED:  IO38 (P2.10)  — 本项目已使用
BOOT 按钮:   IO0  (P2.14)  — 低电平进入下载模式

=== 本项目 ESP32 实际接线 ===
BH1750 (0x23): SDA=IO43(P2.2), SCL=IO44(P2.3)  ← 非标准位置!
  注意: IO43/44 是 UART0, 没有板载 I2C 上拉电阻
  计划迁移至 IO21(SDA)+IO20(SCL) 以获得稳定 I2C 信号
WS2812:        IO38(P2.10)
待接传感器:    SHT30 (I2C, 推荐 IO21+IO20)

---  pinout ESP32 结束  ---

----------------------------------------------------------------
  [C] AM3358 BeagleBone Black
----------------------------------------------------------------

角色: 室内传感器节点
芯片: TI AM3358 (Cortex-A8, 1GHz), 512MB DDR3, 4GB eMMC
IP:   192.168.7.2 (USB), 192.168.10.2 (网线)
OS:   Debian 13 Trixie, Kernel 5.10.168-ti-r84
连接: USB gadget → Pi5 eth1 (192.168.7.0/30)
      网线直连 → Pi5 eth0 (192.168.10.0/30)
      串口控制台 → Pi5 /dev/ttyACM0 (115200 8N1)

=== P9 排针 (46 pins, 靠近电源口) ===

 1: GND      2: GND      3: 3.3V    4: 3.3V    5: VDD_5V
 6: VDD_5V   7: SYS_5V   8: SYS_5V  9: PWR_BUT 10: RST
11: UART4_RX 12: GPIO60  13: GPIO31 14: EHRPWM1A
15: GPIO48   16: EHRPWM1B 17: I2C1_SCL 18: I2C1_SDA
19: I2C2_SCL 20: I2C2_SDA 21: SPI0_D0 22: SPI0_SCLK
23: GPIO49   24: GPIO15  25: GPIO117 26: GPIO14
27: GPIO115  28: SPI1_CS0 29: SPI1_D0 30: SPI1_D1
31: SPI1_SCLK 32: VDD_ADC 33: AIN4   34: GNDA_ADC
35: AIN6     36: AIN5    37: AIN2    38: AIN3
39: AIN0     40: AIN1    41: CLKOUT2 42: GPIO7
43: GND      44: GND     45: GND     46: GND

=== P8 排针 (46 pins, 远离电源口) ===

 1: GND      2: GND      3: GPIO38  4: GPIO39
 5: GPIO34   6: GPIO35   7: GPIO66  8: GPIO67
 9: GPIO69   10: GPIO68  11: GPIO45 12: GPIO44
13: GPIO23   14: GPIO26  15: GPIO47 16: GPIO46
17: GPIO27   18: GPIO65  19: GPIO22 20: GPIO63
21: GPIO62   22: GPIO37  23: GPIO36 24: GPIO33
25: GPIO32   26: GPIO61  27: GPIO86 28: GPIO88
29: GPIO87   30: GPIO89  31: UART5_CTS 32: VDD_ADC
33: AIN4     34: GNDA_ADC 35: AIN6  36: AIN5
37: AIN2     38: AIN3    39: AIN0   40: AIN1
41: GPIO20   42: GPIO7   43: GND    44: GND
45: GND      46: GND

=== I2C 总线映射 ===
/dev/i2c-0: SCL=P9.17, SDA=P9.18  [I2C1, 已挂 EEPROM]
/dev/i2c-2: SCL=P9.19, SDA=P9.20  [I2C2, 空闲 ★推荐接传感器]

=== ADC 通道 ===
AIN0=P9.39, AIN1=P9.40, AIN2=P9.37, AIN3=P9.38
AIN4=P9.33, AIN5=P9.36, AIN6=P9.35
量程: 0-1.8V (板载分压), 12-bit

=== 本项目 AM3358 状态 ===
已用: USB gadget (usb0 192.168.7.2), 网线 (eth0 192.168.10.2)
待接传感器: SHT30 (I2C: /dev/i2c-2, P9.19=SCL, P9.20=SDA)
            CCS811 CO2 (I2C: 同总线)
骨架脚本: /home/debian/indoor_sensor.py (MQTT→Pi5)

---  pinout AM3358 结束  ---



================================================================
  2026-07-22 实际接线更新 (Actual Wiring)
================================================================

ESP32 5传感器实际接线:
  BH1750 (0x23): SDA=GPIO4(P1.4),  SCL=GPIO17(P1.10)
  BMP280 (0x76): SDA=GPIO38(P2.10), SCL=GPIO39(P2.9)
  SHT30  (0x44): SDA=GPIO41(P2.7),  SCL=GPIO42(P2.6)
  ADS1115(0x48): SDA=GPIO43(P2.2),  SCL=GPIO44(P2.3) [A0,A1通道]

关键约束:
  * GPIO19/20 是 USB_D-/USB_D+, USB CDC激活时不可用于I2C
  * GPIO43/44 是 UART0, 用作I2C时与串口冲突, 使用SoftI2C+50kHz慢速
  * 所有I2C总线使用 SoftI2C(sda=OPEN_DRAIN+PULL_UP, scl=OPEN_DRAIN+PULL_UP)
  * WS2812 LED 使用 GPIO38, 与 BMP280 SDA 共享 (当前未启用LED)
