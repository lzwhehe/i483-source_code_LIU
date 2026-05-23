"""
============================================================================
  Task 1.2 - SCD41 CO2 / Temperature / Humidity Sensor Read Program
============================================================================
"""

from machine import I2C, Pin
import time

SDA_PIN  = 5
SCL_PIN  = 6
I2C_FREQ = 100_000
SCD41_ADDR = 0x62
SAMPLE_COUNT = 3

CMD_START_PERIODIC      = 0x21B1
CMD_READ_MEASUREMENT    = 0xEC05
CMD_STOP_PERIODIC       = 0x3F86
CMD_GET_DATA_READY      = 0xE4B8
CMD_REINIT              = 0x3646
CMD_GET_SERIAL_NUMBER   = 0x3682

def crc8(data):
    crc = 0xFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = ((crc << 1) ^ 0x31) & 0xFF if crc & 0x80 else (crc << 1) & 0xFF
    return crc

def send_command(i2c, cmd):
    i2c.writeto(SCD41_ADDR, bytes([(cmd >> 8) & 0xFF, cmd & 0xFF]))

def send_command_and_read(i2c, cmd, num_bytes, delay_ms):
    send_command(i2c, cmd)
    time.sleep_ms(delay_ms)
    return i2c.readfrom(SCD41_ADDR, num_bytes)

def scd41_get_serial(i2c):
    raw = send_command_and_read(i2c, CMD_GET_SERIAL_NUMBER, 9, 1)
    for i in range(0, 9, 3):
        if crc8(raw[i:i+2]) != raw[i+2]:
            raise OSError("Serial number CRC verification failed")
    serial = (raw[0] << 40) | (raw[1] << 32) | \
             (raw[3] << 24) | (raw[4] << 16) | \
             (raw[6] <<  8) |  raw[7]
    return serial

def scd41_data_ready(i2c):
    raw = send_command_and_read(i2c, CMD_GET_DATA_READY, 3, 1)
    if crc8(raw[0:2]) != raw[2]:
        raise OSError("data_ready CRC verification failed")
    status = ((raw[0] & 0x07) << 8) | raw[1]
    return status != 0

def scd41_read_measurement(i2c):
    raw = send_command_and_read(i2c, CMD_READ_MEASUREMENT, 9, 1)
    for i in range(0, 9, 3):
        if crc8(raw[i:i+2]) != raw[i+2]:
            raise OSError(f"Measurement CRC verification failed (byte {i})")
    raw_co2  = (raw[0] << 8) | raw[1]
    raw_temp = (raw[3] << 8) | raw[4]
    raw_rh   = (raw[6] << 8) | raw[7]
    co2_ppm     = raw_co2
    temp_c      = -45.0 + 175.0 * raw_temp / 65535.0
    humidity_rh = 100.0 * raw_rh / 65535.0
    return co2_ppm, temp_c, humidity_rh

def main():
    print("=" * 60)
    print("  Task 1.2 - SCD41 Environmental Data Acquisition")
    print("=" * 60)
    
    i2c = I2C(0, scl=Pin(SCL_PIN), sda=Pin(SDA_PIN), freq=I2C_FREQ)
    print(f"  I2C ready: SDA=GPIO{SDA_PIN}, SCL=GPIO{SCL_PIN}, "
          f"freq={I2C_FREQ // 1000}kHz")
    
    devices = i2c.scan()
    if SCD41_ADDR not in devices:
        print(f"  [ERROR] SCD41 not found at 0x{SCD41_ADDR:02X}")
        return
    print(f"  SCD41 detected at 0x{SCD41_ADDR:02X}")
    
    try:
        send_command(i2c, CMD_STOP_PERIODIC)
        time.sleep_ms(500)
    except OSError:
        pass
    
    send_command(i2c, CMD_REINIT)
    time.sleep_ms(30)
    
    serial = scd41_get_serial(i2c)
    print(f"  SCD41 serial number: 0x{serial:012X}")
    print()
    
    print("  Starting periodic measurement (1 sample / 5s)")
    send_command(i2c, CMD_START_PERIODIC)
    print()
    
    print("-" * 60)
    print(f"  {'#':>3} | {'CO2 (ppm)':>10} | {'Temp (degC)':>12} | {'RH (%)':>7}")
    print("-" * 60)
    
    try:
        for i in range(1, SAMPLE_COUNT + 1):
            time.sleep(5)
            for _ in range(20):
                if scd41_data_ready(i2c):
                    break
                time.sleep_ms(100)
            else:
                print(f"  {i:>3} | data not ready, skipped")
                continue
            co2, temp, rh = scd41_read_measurement(i2c)
            print(f"  {i:>3} | {co2:>10.0f} | {temp:>12.2f} | {rh:>7.2f}")
        
        print("-" * 60)
        print(f"  Acquisition complete: {SAMPLE_COUNT} samples")
    finally:
        send_command(i2c, CMD_STOP_PERIODIC)
        time.sleep_ms(500)
        print()
        print("  Periodic measurement stopped")
    print("=" * 60)

main()