"""
============================================================================
  Task 2 - Simultaneous Data Acquisition from 4 Sensors
  
  Hardware: M5Stamp C3U (MicroPython)
  Sensors:  BH1750 (0x23) + RPR-0521rs (0x38) + SCD41 (0x62) + DPS310 (0x77)
  
  Wiring (all sensors connected in parallel on the I2C bus):
    SDA  -> GPIO5 (G5)
    SCL  -> GPIO6 (G6)
    VCC  -> 3V3
    GND  -> GND
  
  Note: BH1750's ADDR pin must be tied to GND to prevent address ambiguity
        between 0x23 and 0x5C.
  
  Program flow:
    1. Initialize all 4 sensors with high-precision configuration
    2. Wait ~5 seconds for SCD41 to complete its first measurement
    3. Sample once per second, 15 samples total
    4. Output as a formatted table
  
  Output format (per row):
    [#] | CO2 | Temp(SCD41) | RH | Pressure | Temp(DPS310) | BH1750_lux | RPR_lux

  Important:
    - SCD41 has a hardware limit of 1 measurement per 5 seconds.
      During 1Hz sampling, most rows reuse the cached value.
      Fresh SCD41 readings are marked with '*'.
    - DPS310 uses 16x oversampling for highest precision
    - BH1750 uses high-resolution mode (1 lx)
    - RPR-0521rs uses 100ms measurement time, gain x1
============================================================================
"""

from machine import I2C, Pin
import time

# ============================================================================
#  Global configuration
# ============================================================================
SDA_PIN  = 5
SCL_PIN  = 6
I2C_FREQ = 100_000

SAMPLE_COUNT    = 15      # Task requirement: 15 seconds
SAMPLE_INTERVAL = 1.0     # Sample every second

# I2C addresses
ADDR_BH1750 = 0x23
ADDR_RPR    = 0x38
ADDR_SCD41  = 0x62
ADDR_DPS310 = 0x77


# ============================================================================
# ============================================================================
# Section 1: BH1750 driver
# ============================================================================
# ============================================================================

# Commands (BH1750 uses 1-byte commands directly, no register addressing)
BH1750_POWER_ON     = 0x01
BH1750_CONT_H_RES   = 0x10   # Continuous high-resolution mode, 1 lx precision

def bh1750_init(i2c):
    """Initialize BH1750: power on and start continuous high-res measurement"""
    i2c.writeto(ADDR_BH1750, bytes([BH1750_POWER_ON]))
    time.sleep_ms(10)
    i2c.writeto(ADDR_BH1750, bytes([BH1750_CONT_H_RES]))
    time.sleep_ms(180)   # First measurement takes up to 180ms

def bh1750_read(i2c):
    """Read BH1750 illuminance (lux)"""
    data = i2c.readfrom(ADDR_BH1750, 2)
    raw = (data[0] << 8) | data[1]    # Big-endian
    return raw / 1.2                   # Conversion factor per datasheet


# ============================================================================
# ============================================================================
# Section 2: RPR-0521rs driver
# ============================================================================
# ============================================================================

# Registers
RPR_REG_MODE_CONTROL    = 0x41
RPR_REG_ALS_PS_CONTROL  = 0x42
RPR_REG_ALS_DATA0_LSB   = 0x46

# Configuration values
RPR_MODE_CONTROL_VAL    = 0x86  # ALS_EN=1, measurement time = 100ms
RPR_ALS_PS_CONTROL_VAL  = 0x00  # Gain x1 (suitable for bright environments)

def rpr_init(i2c):
    """Initialize RPR-0521rs"""
    i2c.writeto_mem(ADDR_RPR, RPR_REG_MODE_CONTROL,   bytes([RPR_MODE_CONTROL_VAL]))
    i2c.writeto_mem(ADDR_RPR, RPR_REG_ALS_PS_CONTROL, bytes([RPR_ALS_PS_CONTROL_VAL]))
    time.sleep_ms(150)

def rpr_read(i2c):
    """Read RPR-0521rs illuminance (lux) using the datasheet's piecewise formula"""
    raw = i2c.readfrom_mem(ADDR_RPR, RPR_REG_ALS_DATA0_LSB, 4)
    # Little-endian!
    data0 = raw[0] | (raw[1] << 8)
    data1 = raw[2] | (raw[3] << 8)
    
    if data0 == 0:
        return 0.0
    
    ratio = data1 / data0
    # 5-segment piecewise formula from datasheet Table 12
    if   ratio < 0.595: lux = 1.682 * data0 - 1.877 * data1
    elif ratio < 1.015: lux = 0.644 * data0 - 0.132 * data1
    elif ratio < 1.352: lux = 0.756 * data0 - 0.243 * data1
    elif ratio < 3.053: lux = 0.766 * data0 - 0.250 * data1
    else:               lux = 0.0
    
    return max(0.0, lux)


# ============================================================================
# ============================================================================
# Section 3: SCD41 driver
# ============================================================================
# ============================================================================

# Commands
SCD41_CMD_START_PERIODIC    = 0x21B1
SCD41_CMD_READ_MEASUREMENT  = 0xEC05
SCD41_CMD_STOP_PERIODIC     = 0x3F86
SCD41_CMD_GET_DATA_READY    = 0xE4B8
SCD41_CMD_REINIT            = 0x3646

def scd41_crc8(data):
    """Sensirion CRC-8 (polynomial 0x31, initial value 0xFF)"""
    crc = 0xFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = ((crc << 1) ^ 0x31) & 0xFF if crc & 0x80 else (crc << 1) & 0xFF
    return crc

def scd41_send_cmd(i2c, cmd):
    """Send a 2-byte command"""
    i2c.writeto(ADDR_SCD41, bytes([(cmd >> 8) & 0xFF, cmd & 0xFF]))

def scd41_send_cmd_read(i2c, cmd, n, delay_ms):
    """Send command, wait, then read response bytes"""
    scd41_send_cmd(i2c, cmd)
    time.sleep_ms(delay_ms)
    return i2c.readfrom(ADDR_SCD41, n)

def scd41_init(i2c):
    """Initialize SCD41"""
    # Force stop (in case a previous session left it running)
    try:
        scd41_send_cmd(i2c, SCD41_CMD_STOP_PERIODIC)
        time.sleep_ms(500)
    except OSError:
        pass
    
    # Soft reset
    scd41_send_cmd(i2c, SCD41_CMD_REINIT)
    time.sleep_ms(30)
    
    # Start periodic measurement (5 seconds per cycle)
    scd41_send_cmd(i2c, SCD41_CMD_START_PERIODIC)

def scd41_data_ready(i2c):
    """Check if a new measurement is ready"""
    raw = scd41_send_cmd_read(i2c, SCD41_CMD_GET_DATA_READY, 3, 1)
    if scd41_crc8(raw[0:2]) != raw[2]:
        return False
    status = ((raw[0] & 0x07) << 8) | raw[1]
    return status != 0

def scd41_read(i2c):
    """Read SCD41 measurement, returns (CO2_ppm, temp_C, humidity_RH) or None"""
    if not scd41_data_ready(i2c):
        return None
    
    raw = scd41_send_cmd_read(i2c, SCD41_CMD_READ_MEASUREMENT, 9, 1)
    
    # Verify all 3 CRC bytes
    for i in range(0, 9, 3):
        if scd41_crc8(raw[i:i+2]) != raw[i+2]:
            return None
    
    raw_co2  = (raw[0] << 8) | raw[1]
    raw_temp = (raw[3] << 8) | raw[4]
    raw_rh   = (raw[6] << 8) | raw[7]
    
    co2  = raw_co2
    temp = -45.0 + 175.0 * raw_temp / 65535.0
    rh   = 100.0 * raw_rh / 65535.0
    
    return (co2, temp, rh)

def scd41_stop(i2c):
    """Stop periodic measurement"""
    scd41_send_cmd(i2c, SCD41_CMD_STOP_PERIODIC)
    time.sleep_ms(500)


# ============================================================================
# ============================================================================
# Section 4: DPS310 driver
# ============================================================================
# ============================================================================

# Registers
DPS310_REG_PRS_B2       = 0x00   # Pressure raw value (3 bytes)
DPS310_REG_TMP_B2       = 0x03   # Temperature raw value (3 bytes)
DPS310_REG_PRS_CFG      = 0x06   # Pressure configuration
DPS310_REG_TMP_CFG      = 0x07   # Temperature configuration
DPS310_REG_MEAS_CFG     = 0x08   # Measurement mode
DPS310_REG_CFG_REG      = 0x09   # General configuration
DPS310_REG_COEF         = 0x10   # Calibration coefficients (18 bytes, 0x10~0x21)
DPS310_REG_COEF_SRCE    = 0x28   # Temperature coefficient source

# Configuration values (highest precision: 16x oversampling)
DPS310_PM_RATE_1HZ      = 0 << 4
DPS310_PM_PRC_16        = 0x04   # 16x oversampling, ~13.6ms measurement time
DPS310_TMP_RATE_1HZ     = 0 << 4
DPS310_TMP_PRC_16       = 0x04
DPS310_TMP_EXT_MEMS     = 1 << 7

DPS310_MEAS_CTRL_BACKGROUND = 0x07  # Background continuous: pressure + temperature

# Scaling factors for 16x oversampling (datasheet Table 9)
DPS310_KP_16X = 253952
DPS310_KT_16X = 253952

def dps310_read_raw_24(i2c, reg):
    """Read 24-bit signed raw value (big-endian)"""
    raw = i2c.readfrom_mem(ADDR_DPS310, reg, 3)
    val = (raw[0] << 16) | (raw[1] << 8) | raw[2]
    # Sign-extend 24-bit to 32-bit
    if val & 0x800000:
        val |= 0xFF000000
        val -= 0x100000000
    return val

def dps310_read_coefs(i2c):
    """Read 18 bytes of calibration coefficients and parse into c0~c30"""
    raw = i2c.readfrom_mem(ADDR_DPS310, DPS310_REG_COEF, 18)
    
    # Datasheet Section 8.11: coefficients start at 0x10, with mixed bit-widths
    c0  = (raw[0] << 4) | (raw[1] >> 4)
    c1  = ((raw[1] & 0x0F) << 8) | raw[2]
    c00 = (raw[3] << 12) | (raw[4] << 4) | (raw[5] >> 4)
    c10 = ((raw[5] & 0x0F) << 16) | (raw[6] << 8) | raw[7]
    c01 = (raw[8]  << 8) | raw[9]
    c11 = (raw[10] << 8) | raw[11]
    c20 = (raw[12] << 8) | raw[13]
    c21 = (raw[14] << 8) | raw[15]
    c30 = (raw[16] << 8) | raw[17]
    
    # Convert unsigned to signed based on each field's bit width
    def to_signed(val, bits):
        return val - (1 << bits) if val & (1 << (bits-1)) else val
    
    c0  = to_signed(c0,  12)
    c1  = to_signed(c1,  12)
    c00 = to_signed(c00, 20)
    c10 = to_signed(c10, 20)
    c01 = to_signed(c01, 16)
    c11 = to_signed(c11, 16)
    c20 = to_signed(c20, 16)
    c21 = to_signed(c21, 16)
    c30 = to_signed(c30, 16)
    
    return (c0, c1, c00, c10, c01, c11, c20, c21, c30)

def dps310_init(i2c):
    """Initialize DPS310, return calibration coefficients"""
    # Read temperature source bit (used in TMP_CFG)
    tmp_coef_src = i2c.readfrom_mem(ADDR_DPS310, DPS310_REG_COEF_SRCE, 1)[0]
    tmp_src_bit  = (tmp_coef_src & 0x80)  # Bit 7 indicates ASIC/MEMS source
    
    # Read calibration coefficients
    coefs = dps310_read_coefs(i2c)
    
    # Configure pressure: 1Hz, 16x oversampling
    i2c.writeto_mem(ADDR_DPS310, DPS310_REG_PRS_CFG,
                    bytes([DPS310_PM_RATE_1HZ | DPS310_PM_PRC_16]))
    
    # Configure temperature: 1Hz, 16x oversampling, with matching source bit
    i2c.writeto_mem(ADDR_DPS310, DPS310_REG_TMP_CFG,
                    bytes([tmp_src_bit | DPS310_TMP_RATE_1HZ | DPS310_TMP_PRC_16]))
    
    # 16x oversampling requires P/T_SHIFT enabled (CFG_REG bits 2/3)
    i2c.writeto_mem(ADDR_DPS310, DPS310_REG_CFG_REG, bytes([0x0C]))
    
    # Start background continuous measurement
    i2c.writeto_mem(ADDR_DPS310, DPS310_REG_MEAS_CFG,
                    bytes([DPS310_MEAS_CTRL_BACKGROUND]))
    
    # Wait for first measurement to complete
    time.sleep_ms(100)
    
    return coefs

def dps310_read(i2c, coefs):
    """
    Read DPS310 pressure (Pa) and temperature (degC)
    Uses the compensation formula from datasheet Section 4.9.1
    """
    c0, c1, c00, c10, c01, c11, c20, c21, c30 = coefs
    
    # Read raw values
    raw_prs = dps310_read_raw_24(i2c, DPS310_REG_PRS_B2)
    raw_tmp = dps310_read_raw_24(i2c, DPS310_REG_TMP_B2)
    
    # Scale raw values
    prs_scaled = raw_prs / DPS310_KP_16X
    tmp_scaled = raw_tmp / DPS310_KT_16X
    
    # Compensation formula (datasheet 4.9.1)
    temp_c = c0 * 0.5 + c1 * tmp_scaled
    
    pressure_pa = (c00 + 
                   prs_scaled * (c10 + prs_scaled * (c20 + prs_scaled * c30)) +
                   tmp_scaled * c01 +
                   tmp_scaled * prs_scaled * (c11 + prs_scaled * c21))
    
    return (pressure_pa, temp_c)


# ============================================================================
# ============================================================================
# Section 5: Main program
# ============================================================================
# ============================================================================

def main():
    print("=" * 80)
    print("  Task 2 - Simultaneous data acquisition from 4 sensors")
    print("  (15 seconds total, 1 sample per second)")
    print("=" * 80)
    
    # --- Initialize I2C ---
    i2c = I2C(0, scl=Pin(SCL_PIN), sda=Pin(SDA_PIN), freq=I2C_FREQ)
    
    # --- Verify all 4 sensors are present ---
    devices = i2c.scan()
    expected = [ADDR_BH1750, ADDR_RPR, ADDR_SCD41, ADDR_DPS310]
    for addr in expected:
        if addr not in devices:
            print(f"[ERROR] Sensor at 0x{addr:02X} not found, aborting")
            return
    print(f"  All 4 sensors detected: {[hex(a) for a in devices]}")
    
    # --- Initialize all 4 sensors ---
    print()
    print("  Initializing sensors ...")
    
    print("    BH1750     ... ", end="")
    bh1750_init(i2c)
    print("OK")
    
    print("    RPR-0521rs ... ", end="")
    rpr_init(i2c)
    print("OK")
    
    print("    DPS310     ... ", end="")
    dps310_coefs = dps310_init(i2c)
    print("OK")
    
    print("    SCD41      ... ", end="")
    scd41_init(i2c)
    print("OK")
    
    # --- Wait for SCD41 warm-up (first measurement takes ~5 seconds) ---
    print()
    print("  Waiting for SCD41 first measurement (5 seconds) ...")
    time.sleep(5)
    
    # Cache for SCD41 data (it only updates every 5 seconds)
    scd41_cache = (None, None, None)
    
    # --- Table header ---
    print()
    print("=" * 80)
    print(f"  {'#':>2} | {'CO2':>5} | {'Temp1':>5} | {'RH':>5} | "
          f"{'Pressure':>8} | {'Temp2':>5} | {'BH1750':>7} | {'RPR':>7}")
    print(f"  {' ':>2} | {'ppm':>5} | {'degC':>5} | {'%RH':>5} | "
          f"{'hPa':>8} | {'degC':>5} | {'lux':>7} | {'lux':>7}")
    print("-" * 80)
    
    # --- Main acquisition loop ---
    try:
        for i in range(1, SAMPLE_COUNT + 1):
            t_start = time.ticks_ms()
            
            # Read BH1750
            try:
                bh_lux = bh1750_read(i2c)
            except Exception as e:
                bh_lux = None
            
            # Read RPR-0521rs
            try:
                rpr_lux = rpr_read(i2c)
            except Exception as e:
                rpr_lux = None
            
            # Read DPS310
            try:
                pressure_pa, dps_temp = dps310_read(i2c, dps310_coefs)
                pressure_hpa = pressure_pa / 100.0
            except Exception as e:
                pressure_hpa, dps_temp = None, None
            
            # Read SCD41 (only updates every 5s, use cache otherwise)
            try:
                result = scd41_read(i2c)
                if result is not None:
                    scd41_cache = result
                    new_data = True
                else:
                    new_data = False
            except Exception as e:
                new_data = False
            
            co2, scd_temp, scd_rh = scd41_cache
            
            # Mark fresh SCD41 readings with '*'
            mark = "*" if new_data else " "
            
            # Helper to format values, showing 'n/a' if None
            def fmt(val, fmt_str, default="  n/a"):
                if val is None:
                    return default
                return fmt_str.format(val)
            
            print(f"  {i:>2} | "
                  f"{fmt(co2, '{:>5.0f}')}{mark}| "
                  f"{fmt(scd_temp, '{:>5.2f}')} | "
                  f"{fmt(scd_rh, '{:>5.2f}')} | "
                  f"{fmt(pressure_hpa, '{:>8.2f}')} | "
                  f"{fmt(dps_temp, '{:>5.2f}')} | "
                  f"{fmt(bh_lux, '{:>7.2f}')} | "
                  f"{fmt(rpr_lux, '{:>7.2f}')}")
            
            # Sleep precisely (subtracting time spent reading sensors)
            elapsed = time.ticks_diff(time.ticks_ms(), t_start)
            sleep_ms = max(0, int(SAMPLE_INTERVAL * 1000) - elapsed)
            time.sleep_ms(sleep_ms)
        
        print("-" * 80)
        print(f"  Acquisition complete.")
        print(f"  '*' marks fresh SCD41 readings; "
              f"unmarked rows reuse the cached value (5s update rate).")
        
    finally:
        # --- Cleanup: stop SCD41 periodic measurement ---
        print()
        print("  Stopping SCD41 periodic measurement ...")
        try:
            scd41_stop(i2c)
        except:
            pass
        print("  Done.")
    
    print("=" * 80)


# Run
main()