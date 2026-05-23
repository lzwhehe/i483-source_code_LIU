"""
Task 2 - 1a + 1d
MQTT Publisher: 每 15 秒发布传感器数据
LED Control:    订阅 CO2 阈值结果，超过 700ppm 时 LED 闪烁
"""

import asyncio
import network
import time
from machine import I2C, Pin
from umqtt.robust import MQTTClient

# ===== 配置 =====
WIFI_SSID   = "JAISTALL"
WIFI_PASS   = ""
MQTT_BROKER = "150.65.230.59"
MQTT_PORT   = 1883
STUDENT_ID  = "s2410431"
CLIENT_ID   = f"esp32-{STUDENT_ID}"

PUBLISH_INTERVAL = 15   # seconds
LED_PIN          = 2    # ESP32 内置 LED（如不亮请改为实际 GPIO 号）

SDA_PIN  = 5
SCL_PIN  = 6
I2C_FREQ = 100_000

# ===== MQTT Topics =====
BASE   = f"i483/sensors/{STUDENT_ID}"
TOPIC_TEMP     = f"{BASE}/SCD41/temperature"
TOPIC_HUMIDITY = f"{BASE}/SCD41/humidity"
TOPIC_CO2      = f"{BASE}/SCD41/co2"
TOPIC_ILLUM    = f"{BASE}/BH1750/illumination"
TOPIC_IR       = f"{BASE}/RPR0521/infrared_illumination"
TOPIC_PRESSURE = f"{BASE}/DPS310/air_pressure"
TOPIC_LED_SUB  = f"i483/actuators/{STUDENT_ID}/co2_threshold_crossed"

# ===== Global =====
led_blink = False


# ===== BH1750 =====
ADDR_BH1750       = 0x23
BH1750_POWER_ON   = 0x01
BH1750_CONT_H_RES = 0x10

def bh1750_init(i2c):
    i2c.writeto(ADDR_BH1750, bytes([BH1750_POWER_ON]))
    time.sleep_ms(10)
    i2c.writeto(ADDR_BH1750, bytes([BH1750_CONT_H_RES]))
    time.sleep_ms(180)

def bh1750_read(i2c):
    data = i2c.readfrom(ADDR_BH1750, 2)
    raw = (data[0] << 8) | data[1]
    return raw / 1.2


# ===== RPR-0521rs =====
ADDR_RPR               = 0x38
RPR_REG_MODE_CONTROL   = 0x41
RPR_REG_ALS_PS_CONTROL = 0x42
RPR_REG_ALS_DATA0_LSB  = 0x46
RPR_MODE_CONTROL_VAL   = 0x86
RPR_ALS_PS_CONTROL_VAL = 0x00

def rpr_init(i2c):
    i2c.writeto_mem(ADDR_RPR, RPR_REG_MODE_CONTROL,   bytes([RPR_MODE_CONTROL_VAL]))
    i2c.writeto_mem(ADDR_RPR, RPR_REG_ALS_PS_CONTROL, bytes([RPR_ALS_PS_CONTROL_VAL]))
    time.sleep_ms(150)

def rpr_read(i2c):
    raw = i2c.readfrom_mem(ADDR_RPR, RPR_REG_ALS_DATA0_LSB, 4)
    data0 = raw[0] | (raw[1] << 8)
    data1 = raw[2] | (raw[3] << 8)
    if data0 == 0:
        return 0.0
    ratio = data1 / data0
    if   ratio < 0.595: lux = 1.682 * data0 - 1.877 * data1
    elif ratio < 1.015: lux = 0.644 * data0 - 0.132 * data1
    elif ratio < 1.352: lux = 0.756 * data0 - 0.243 * data1
    elif ratio < 3.053: lux = 0.766 * data0 - 0.250 * data1
    else:               lux = 0.0
    return max(0.0, lux)


# ===== SCD41 =====
ADDR_SCD41              = 0x62
SCD41_CMD_START_PERIODIC   = 0x21B1
SCD41_CMD_READ_MEASUREMENT = 0xEC05
SCD41_CMD_STOP_PERIODIC    = 0x3F86
SCD41_CMD_GET_DATA_READY   = 0xE4B8
SCD41_CMD_REINIT           = 0x3646

def scd41_crc8(data):
    crc = 0xFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = ((crc << 1) ^ 0x31) & 0xFF if crc & 0x80 else (crc << 1) & 0xFF
    return crc

def scd41_send_cmd(i2c, cmd):
    i2c.writeto(ADDR_SCD41, bytes([(cmd >> 8) & 0xFF, cmd & 0xFF]))

def scd41_send_cmd_read(i2c, cmd, n, delay_ms):
    scd41_send_cmd(i2c, cmd)
    time.sleep_ms(delay_ms)
    return i2c.readfrom(ADDR_SCD41, n)

def scd41_init(i2c):
    try:
        scd41_send_cmd(i2c, SCD41_CMD_STOP_PERIODIC)
        time.sleep_ms(500)
    except OSError:
        pass
    scd41_send_cmd(i2c, SCD41_CMD_REINIT)
    time.sleep_ms(30)
    scd41_send_cmd(i2c, SCD41_CMD_START_PERIODIC)

def scd41_data_ready(i2c):
    raw = scd41_send_cmd_read(i2c, SCD41_CMD_GET_DATA_READY, 3, 1)
    if scd41_crc8(raw[0:2]) != raw[2]:
        return False
    return ((raw[0] & 0x07) << 8) | raw[1] != 0

def scd41_read(i2c):
    if not scd41_data_ready(i2c):
        return None
    raw = scd41_send_cmd_read(i2c, SCD41_CMD_READ_MEASUREMENT, 9, 1)
    for i in range(0, 9, 3):
        if scd41_crc8(raw[i:i+2]) != raw[i+2]:
            return None
    raw_co2  = (raw[0] << 8) | raw[1]
    raw_temp = (raw[3] << 8) | raw[4]
    raw_rh   = (raw[6] << 8) | raw[7]
    return (float(raw_co2),
            -45.0 + 175.0 * raw_temp / 65535.0,
            100.0 * raw_rh / 65535.0)

def scd41_stop(i2c):
    scd41_send_cmd(i2c, SCD41_CMD_STOP_PERIODIC)
    time.sleep_ms(500)


# ===== DPS310 =====
ADDR_DPS310          = 0x77
DPS310_REG_PRS_B2    = 0x00
DPS310_REG_TMP_B2    = 0x03
DPS310_REG_PRS_CFG   = 0x06
DPS310_REG_TMP_CFG   = 0x07
DPS310_REG_MEAS_CFG  = 0x08
DPS310_REG_CFG_REG   = 0x09
DPS310_REG_COEF      = 0x10
DPS310_REG_COEF_SRCE = 0x28
DPS310_KP_16X        = 253952
DPS310_KT_16X        = 253952

def dps310_read_raw_24(i2c, reg):
    raw = i2c.readfrom_mem(ADDR_DPS310, reg, 3)
    val = (raw[0] << 16) | (raw[1] << 8) | raw[2]
    if val & 0x800000:
        val |= 0xFF000000
        val -= 0x100000000
    return val

def dps310_read_coefs(i2c):
    raw = i2c.readfrom_mem(ADDR_DPS310, DPS310_REG_COEF, 18)
    c0  = (raw[0] << 4) | (raw[1] >> 4)
    c1  = ((raw[1] & 0x0F) << 8) | raw[2]
    c00 = (raw[3] << 12) | (raw[4] << 4) | (raw[5] >> 4)
    c10 = ((raw[5] & 0x0F) << 16) | (raw[6] << 8) | raw[7]
    c01 = (raw[8]  << 8) | raw[9]
    c11 = (raw[10] << 8) | raw[11]
    c20 = (raw[12] << 8) | raw[13]
    c21 = (raw[14] << 8) | raw[15]
    c30 = (raw[16] << 8) | raw[17]
    def s(v, b): return v - (1 << b) if v & (1 << (b-1)) else v
    return (s(c0,12), s(c1,12), s(c00,20), s(c10,20),
            s(c01,16), s(c11,16), s(c20,16), s(c21,16), s(c30,16))

def dps310_init(i2c):
    src  = i2c.readfrom_mem(ADDR_DPS310, DPS310_REG_COEF_SRCE, 1)[0]
    coefs = dps310_read_coefs(i2c)
    i2c.writeto_mem(ADDR_DPS310, DPS310_REG_PRS_CFG,  bytes([0x04]))
    i2c.writeto_mem(ADDR_DPS310, DPS310_REG_TMP_CFG,  bytes([(src & 0x80) | 0x04]))
    i2c.writeto_mem(ADDR_DPS310, DPS310_REG_CFG_REG,  bytes([0x0C]))
    i2c.writeto_mem(ADDR_DPS310, DPS310_REG_MEAS_CFG, bytes([0x07]))
    time.sleep_ms(100)
    return coefs

def dps310_read(i2c, coefs):
    c0,c1,c00,c10,c01,c11,c20,c21,c30 = coefs
    prs = dps310_read_raw_24(i2c, DPS310_REG_PRS_B2) / DPS310_KP_16X
    tmp = dps310_read_raw_24(i2c, DPS310_REG_TMP_B2) / DPS310_KT_16X
    temp_c = c0 * 0.5 + c1 * tmp
    pressure_pa = (c00 +
                   prs * (c10 + prs * (c20 + prs * c30)) +
                   tmp * c01 + tmp * prs * (c11 + prs * c21))
    return (pressure_pa, temp_c)


# ===== Wi-Fi =====
def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(False)
    time.sleep(0.5)
    wlan.active(True)
    time.sleep(0.5)
    if wlan.isconnected():
        print(f"[WiFi] Already connected: {wlan.ifconfig()}")
        return True
    print(f"[WiFi] Connecting to {WIFI_SSID} ...")
    wlan.connect(WIFI_SSID, WIFI_PASS)
    for _ in range(20):
        if wlan.isconnected():
            break
        time.sleep(1)
    if wlan.isconnected():
        print(f"[WiFi] Connected: {wlan.ifconfig()}")
        return True
    print("[WiFi] Connection failed!")
    return False


# ===== MQTT callback =====
def mqtt_callback(topic, msg):
    global led_blink
    t = topic.decode() if isinstance(topic, bytes) else topic
    m = msg.decode()   if isinstance(msg,   bytes) else msg
    print(f"[MQTT IN] {t} = {m}")
    if t == TOPIC_LED_SUB:
        led_blink = (m.strip() == "yes")


# ===== Async tasks =====
async def led_task(led):
    while True:
        if led_blink:
            led.value(1)
            await asyncio.sleep(0.5)
            led.value(0)
            await asyncio.sleep(0.5)
        else:
            led.value(0)
            await asyncio.sleep(0.1)


async def poll_mqtt_task(client):
    while True:
        try:
            client.check_msg()
        except Exception as e:
            print(f"[MQTT poll error] {e}")
            try:
                client.reconnect()
            except Exception:
                pass
        await asyncio.sleep(0.1)


async def sensor_publish_task(i2c, client, dps310_coefs):
    scd41_cache = (None, None, None)

    while True:
        t_start = time.ticks_ms()
        print("[SENSOR] Reading ...")

        # BH1750
        try:
            lux = bh1750_read(i2c)
            client.publish(TOPIC_ILLUM, f"{lux:.2f}".encode())
            print(f"  illumination        = {lux:.2f} lux")
        except Exception as e:
            print(f"  BH1750 error: {e}")

        # RPR0521
        try:
            ir = rpr_read(i2c)
            client.publish(TOPIC_IR, f"{ir:.2f}".encode())
            print(f"  infrared_illumination = {ir:.2f} lux")
        except Exception as e:
            print(f"  RPR0521 error: {e}")

        # DPS310
        try:
            pa, _ = dps310_read(i2c, dps310_coefs)
            hpa   = pa / 100.0
            client.publish(TOPIC_PRESSURE, f"{hpa:.2f}".encode())
            print(f"  air_pressure        = {hpa:.2f} hPa")
        except Exception as e:
            print(f"  DPS310 error: {e}")

        # SCD41
        try:
            result = scd41_read(i2c)
            if result is not None:
                scd41_cache = result
        except Exception as e:
            print(f"  SCD41 error: {e}")

        co2, temp, rh = scd41_cache
        if co2 is not None:
            client.publish(TOPIC_CO2,      f"{co2:.2f}".encode())
            client.publish(TOPIC_TEMP,     f"{temp:.2f}".encode())
            client.publish(TOPIC_HUMIDITY, f"{rh:.2f}".encode())
            print(f"  co2={co2:.2f} ppm  temp={temp:.2f} C  humidity={rh:.2f} %")

        elapsed  = time.ticks_diff(time.ticks_ms(), t_start)
        wait_ms  = max(0, PUBLISH_INTERVAL * 1000 - elapsed)
        await asyncio.sleep_ms(wait_ms)


# ===== Entry point =====
async def main():
    if not connect_wifi():
        print("WiFi failed, aborting.")
        return

    i2c = I2C(0, scl=Pin(SCL_PIN), sda=Pin(SDA_PIN), freq=I2C_FREQ)

    print("[INIT] Sensors ...")
    bh1750_init(i2c)
    rpr_init(i2c)
    dps310_coefs = dps310_init(i2c)
    scd41_init(i2c)
    print("[INIT] Waiting 5s for SCD41 first measurement ...")
    await asyncio.sleep(5)

    client = MQTTClient(CLIENT_ID, MQTT_BROKER, port=MQTT_PORT, keepalive=60)
    client.set_callback(mqtt_callback)
    client.connect()
    client.subscribe(TOPIC_LED_SUB.encode())
    print(f"[MQTT] Connected to {MQTT_BROKER}:{MQTT_PORT}")
    print(f"[MQTT] Subscribed: {TOPIC_LED_SUB}")

    led = Pin(LED_PIN, Pin.OUT)

    await asyncio.gather(
        sensor_publish_task(i2c, client, dps310_coefs),
        poll_mqtt_task(client),
        led_task(led),
    )


asyncio.run(main())
