"""
============================================================================
  Task 1.3 - RPR-0521rs Illuminance Sensor Read Program
  
  Hardware: M5Stamp C3U (MicroPython) + RPR-0521rs (5-pin breakout board)
  Wiring:   SDA -> GPIO5 (G5)
            SCL -> GPIO6 (G6)
            3.3V -> 3V3 (must NOT use 5V)
            GND  -> GND
            INT  -> not connected (proximity interrupt not used)
  Address:  0x38 (fixed I2C address of RPR-0521rs)
  
  Datasheet reference: ROHM RPR-0521RS Datasheet
  https://fscdn.rohm.com/en/products/databook/datasheet/ic/sensor/light/rpr-0521rs-e.pdf
  
  Program flow:
    1. Initialize I2C
    2. Read MANUFACT_ID + PART_ID to verify the sensor
    3. Write MODE_CONTROL  (0x41 = 0x86): enable ALS, 100ms measurement time
    4. Write ALS_PS_CONTROL (0x42 = 0x00): ALS gain x1
    5. Wait 150ms for first measurement
    6. Loop 15 times, once per second:
         a. Read 4 bytes (DATA0_L, DATA0_H, DATA1_L, DATA1_H)
         b. Combine into two 16-bit raw values (little-endian!)
         c. Apply the datasheet's piecewise lux formula
         d. Print result
    7. Write MODE_CONTROL (0x41 = 0x00) to stop measurement

  RPR-0521rs uses two photodiodes: DATA0 (visible light, ~550nm) and
  DATA1 (infrared, ~880nm). The ratio DATA1/DATA0 is used to identify
  the type of light source, and the lux value is computed using a
  5-segment piecewise linear formula (datasheet Table 12).
============================================================================
"""

from machine import I2C, Pin
import time

# ============================================================================
#  Configuration
# ============================================================================
SDA_PIN  = 5
SCL_PIN  = 6
I2C_FREQ = 100_000

RPR_ADDR = 0x38

SAMPLE_COUNT    = 15      # Task requirement: 15 samples
SAMPLE_INTERVAL = 1.0     # 1 sample per second

# ============================================================================
#  Register addresses (datasheet Table 7)
# ============================================================================
REG_SYSTEM_CONTROL  = 0x40   # PartID + SW reset
REG_MODE_CONTROL    = 0x41   # ALS/PS enable, measurement time
REG_ALS_PS_CONTROL  = 0x42   # ALS gain, LED current
REG_ALS_DATA0_LSB   = 0x46   # ALS DATA0 low byte (visible channel)
REG_MANUFACT_ID     = 0x92   # Manufacturer ID, fixed at 0xE0

# ============================================================================
#  Configuration values
# ============================================================================
# MODE_CONTROL (0x41)
#   bit 7   (ALS_EN)    = 1  -> ALS measurement enabled
#   bit 6   (PS_EN)     = 0  -> PS measurement disabled (proximity not needed)
#   bits 5-4 (PS_PULSE) = 00 -> default LED pulse count
#   bits 3-0 (MEAS_TIME)= 0110 = 6 -> ALS=100ms, PS=100ms
# Combined: 0b 1000 0110 = 0x86
MODE_CONTROL_VAL = 0x86

# ALS_PS_CONTROL (0x42)
#   bits 7-6 (DATA0_GAIN) = 00 -> x1
#   bits 5-4 (DATA1_GAIN) = 00 -> x1
#   bits 3-0 (LED_CURRENT)= 0000
# Combined: 0x00 (lowest gain, suitable for bright environments)
ALS_PS_CONTROL_VAL = 0x00

# ============================================================================
#  Low-level I2C helpers
# ============================================================================
def write_reg(i2c, reg, value):
    """Write a single 8-bit register"""
    i2c.writeto_mem(RPR_ADDR, reg, bytes([value]))

def read_reg(i2c, reg, n=1):
    """Read n consecutive bytes starting at reg
    (RPR-0521rs supports register address auto-increment)"""
    return i2c.readfrom_mem(RPR_ADDR, reg, n)

# ============================================================================
#  Lux conversion (datasheet Table 12, Section 9.4)
#  Valid only for: measurement time = 100ms, ALS gain = x1
# ============================================================================
def calculate_lux(data0, data1):
    """
    Convert DATA0 and DATA1 raw values to lux using the
    ROHM-recommended piecewise linear formula.
    """
    # Handle edge case
    if data0 == 0:
        return 0.0
    
    ratio = data1 / data0
    
    # 5-segment formula from datasheet Table 12
    if ratio < 0.595:
        lux = 1.682 * data0 - 1.877 * data1
    elif ratio < 1.015:
        lux = 0.644 * data0 - 0.132 * data1
    elif ratio < 1.352:
        lux = 0.756 * data0 - 0.243 * data1
    elif ratio < 3.053:
        lux = 0.766 * data0 - 0.250 * data1
    else:
        lux = 0.0
    
    # Avoid negative results from rounding errors in low-light conditions
    return max(0.0, lux)

# ============================================================================
#  Main program
# ============================================================================
def main():
    print("=" * 60)
    print("  Task 1.3 - RPR-0521rs Illuminance Acquisition")
    print("=" * 60)
    
    # Step 1: I2C initialization
    i2c = I2C(0, scl=Pin(SCL_PIN), sda=Pin(SDA_PIN), freq=I2C_FREQ)
    print(f"  I2C: SDA=GPIO{SDA_PIN}, SCL=GPIO{SCL_PIN}, "
          f"freq={I2C_FREQ // 1000}kHz")
    
    # Step 2: Verify sensor identity
    manufact_id = read_reg(i2c, REG_MANUFACT_ID)[0]
    part_id     = read_reg(i2c, REG_SYSTEM_CONTROL)[0] & 0x3F
    print(f"  MANUFACT_ID = 0x{manufact_id:02X} (expected 0xE0)")
    print(f"  PART_ID     = 0x{part_id:02X}   (expected 0x0A)")
    
    if manufact_id != 0xE0 or part_id != 0x0A:
        print("  [ERROR] Not an RPR-0521rs, aborting")
        return
    
    # Step 3: Configure the sensor
    print()
    print("  Sensor configuration:")
    print(f"    MODE_CONTROL    (0x41) = 0x{MODE_CONTROL_VAL:02X}  "
          f"(ALS enabled, 100ms measurement time)")
    print(f"    ALS_PS_CONTROL  (0x42) = 0x{ALS_PS_CONTROL_VAL:02X}  "
          f"(gain x1)")
    
    write_reg(i2c, REG_MODE_CONTROL,   MODE_CONTROL_VAL)
    write_reg(i2c, REG_ALS_PS_CONTROL, ALS_PS_CONTROL_VAL)
    
    # Wait for the first measurement to complete
    time.sleep_ms(150)
    
    # Step 4: Acquisition loop
    print()
    print("-" * 60)
    print(f"  {'#':>3} | {'DATA0':>6} | {'DATA1':>6} | {'ratio':>6} | "
          f"{'lux':>9}")
    print("-" * 60)
    
    try:
        for i in range(1, SAMPLE_COUNT + 1):
            # Read 4 bytes: DATA0_L, DATA0_H, DATA1_L, DATA1_H
            raw = read_reg(i2c, REG_ALS_DATA0_LSB, 4)
            
            # Note: RPR-0521rs uses little-endian byte order
            data0 = raw[0] | (raw[1] << 8)
            data1 = raw[2] | (raw[3] << 8)
            
            ratio = data1 / data0 if data0 > 0 else 0.0
            lux = calculate_lux(data0, data1)
            
            print(f"  {i:>3} | {data0:>6} | {data1:>6} | {ratio:>6.3f} | "
                  f"{lux:>9.2f}")
            
            time.sleep(SAMPLE_INTERVAL)
        
        print("-" * 60)
        print(f"  Acquisition complete: {SAMPLE_COUNT} samples")
    
    finally:
        # Step 5: Stop measurement
        write_reg(i2c, REG_MODE_CONTROL, 0x00)
        print()
        print("  ALS measurement stopped")
    
    print("=" * 60)


main()