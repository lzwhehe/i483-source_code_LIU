"""
============================================================================
  Task 1.4 - BH1750 Illuminance Sensor Read Program
  
  Hardware: M5Stamp C3U (MicroPython) + BH1750 GY-302 module
  Wiring:   SDA  -> GPIO5 (G5)
            SCL  -> GPIO6 (G6)
            3V0  -> 3V3 (bypass the onboard LDO; chip Vcc directly)
            GND  -> GND
            ADDR -> GND (fix the I2C address at 0x23)
            VIN  -> not connected (we power via 3V0 instead)
  Address:  0x23 (when ADDR is tied to GND)
            0x5C (when ADDR is tied to VCC)
  
  Datasheet reference: ROHM BH1750FVI Datasheet
  https://www.rohm.com/datasheet/BH1750FVI/bh1750fvi-e
  
  Program flow:
    1. Initialize I2C
    2. Send Power On command (0x01)                         -- DS p.5
    3. Send continuous high-resolution mode command (0x10,
       1 lx precision)                                       -- DS p.10
    4. Wait 180 ms for first measurement
       (datasheet specifies max 180ms)
    5. Loop 15 times, once per second:
         a. Read 2 bytes (big-endian!)
         b. Apply conversion formula: lux = raw / 1.2        -- DS p.11
         c. Print result
    6. Send Power Down command (0x00) to put sensor in idle

  BH1750 uses 1-byte commands (no register addressing) and a
  fixed conversion factor of 1.2, which is the ADC's intrinsic
  scaling factor specified in the datasheet.
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

BH1750_ADDR = 0x23

SAMPLE_COUNT    = 15      # Task requirement: 15 samples
SAMPLE_INTERVAL = 1.0     # 1 sample per second

# ============================================================================
#  BH1750 commands (datasheet p.5 "Instruction Set Architecture")
#  BH1750 uses direct 1-byte commands, not register addressing
# ============================================================================
CMD_POWER_DOWN          = 0x00   # Power down (low-power idle)
CMD_POWER_ON            = 0x01   # Power on (waiting for measurement command)
CMD_RESET               = 0x07   # Soft reset (only valid after Power On)

# Continuous measurement modes (configure once, sensor keeps measuring)
CMD_CONT_H_RES          = 0x10   # Continuous high-res 1 lx, 120ms typ / 180ms max
CMD_CONT_H_RES2         = 0x11   # Continuous high-res-2 0.5 lx
CMD_CONT_L_RES          = 0x13   # Continuous low-res 4 lx, 16ms typ / 24ms max

# One-time measurement modes (auto-power-down after measurement)
CMD_ONESHOT_H_RES       = 0x20   # One-shot high-res
CMD_ONESHOT_H_RES2      = 0x21   # One-shot high-res-2
CMD_ONESHOT_L_RES       = 0x23   # One-shot low-res

# We use: continuous high-resolution (1 lx precision, suitable for the task)
MEASUREMENT_MODE = CMD_CONT_H_RES

# Datasheet specifies: high-res mode typ 120ms / max 180ms
# Use the max value for safety
MEASUREMENT_TIME_MS = 180

# ============================================================================
#  Low-level I2C helpers
# ============================================================================
def send_command(i2c, cmd):
    """Send a 1-byte command"""
    i2c.writeto(BH1750_ADDR, bytes([cmd]))

def read_raw(i2c):
    """Read 2 bytes of raw measurement data (big-endian: MSB first)"""
    data = i2c.readfrom(BH1750_ADDR, 2)
    return (data[0] << 8) | data[1]

# ============================================================================
#  Lux conversion (datasheet p.11)
#  
#  For H-Resolution Mode (1 lx mode):
#      lux = raw / 1.2
#  
#  The constant 1.2 is the intrinsic scaling factor of BH1750's internal ADC,
#  as specified in the datasheet.
# ============================================================================
def calculate_lux(raw):
    """Convert raw value to lux"""
    return raw / 1.2

# ============================================================================
#  Main program
# ============================================================================
def main():
    print("=" * 60)
    print("  Task 1.4 - BH1750 Illuminance Acquisition")
    print("=" * 60)
    
    # Step 1: I2C initialization
    i2c = I2C(0, scl=Pin(SCL_PIN), sda=Pin(SDA_PIN), freq=I2C_FREQ)
    print(f"  I2C: SDA=GPIO{SDA_PIN}, SCL=GPIO{SCL_PIN}, "
          f"freq={I2C_FREQ // 1000}kHz")
    print(f"  Address: 0x{BH1750_ADDR:02X}")
    
    # Step 2: Power On
    send_command(i2c, CMD_POWER_ON)
    time.sleep_ms(10)
    print(f"  Sent command: 0x{CMD_POWER_ON:02X} (Power On)")
    
    # Step 3: Start continuous measurement mode
    send_command(i2c, MEASUREMENT_MODE)
    print(f"  Sent command: 0x{MEASUREMENT_MODE:02X} "
          f"(continuous high-res mode, 1 lx precision)")
    
    # Step 4: Wait for first measurement to complete
    print(f"  Waiting for first measurement ({MEASUREMENT_TIME_MS}ms) ...")
    time.sleep_ms(MEASUREMENT_TIME_MS)
    
    # Step 5: Acquisition loop
    print()
    print("-" * 60)
    print(f"  {'#':>3} | {'raw':>6} | {'lux':>10}")
    print("-" * 60)
    
    try:
        for i in range(1, SAMPLE_COUNT + 1):
            raw = read_raw(i2c)
            lux = calculate_lux(raw)
            print(f"  {i:>3} | {raw:>6} | {lux:>10.2f}")
            time.sleep(SAMPLE_INTERVAL)
        
        print("-" * 60)
        print(f"  Acquisition complete: {SAMPLE_COUNT} samples")
    
    finally:
        # Step 6: Power Down
        send_command(i2c, CMD_POWER_DOWN)
        print()
        print(f"  Sent command: 0x{CMD_POWER_DOWN:02X} (Power Down)")
    
    print("=" * 60)


main()