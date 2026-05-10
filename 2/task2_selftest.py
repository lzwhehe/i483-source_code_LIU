"""
============================================================================
  Task 2 - Hardware Self-Test for All 4 Sensors
  
  Purpose: Verify that each sensor is functional at the hardware level.
           This is essential for the project report to demonstrate that
           any anomalies in measured values (e.g., SCD41 returning 0 ppm
           during warm-up) are not caused by hardware faults.
  
  Tests performed:
    - I2C bus scan (verify all 4 expected addresses respond)
    - SCD41:  built-in factory self-test (datasheet 3.9.4) + serial number
    - DPS310: read PRODUCT_ID register (datasheet 8.7), expect 0x10
    - BH1750: power-on response test
    - RPR-0521rs: read MANUFACT_ID register (datasheet 6.5), expect 0xE0
============================================================================
"""

from machine import I2C, Pin
import time

# --- Configuration (must match main program) ---
SDA_PIN  = 5
SCL_PIN  = 6
I2C_FREQ = 100_000

ADDR_BH1750 = 0x23
ADDR_RPR    = 0x38
ADDR_SCD41  = 0x62
ADDR_DPS310 = 0x77


# ============================================================================
#  Sensirion CRC-8 (used for SCD41 communication validation)
# ============================================================================
def crc8(data):
    crc = 0xFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = ((crc << 1) ^ 0x31) & 0xFF if crc & 0x80 else (crc << 1) & 0xFF
    return crc


# ============================================================================
#  Test 1: I2C bus scan
# ============================================================================
def test_i2c_scan(i2c):
    print("[Test 1] I2C bus scan")
    devices = i2c.scan()
    print(f"  Detected addresses: {[hex(a) for a in devices]}")
    
    expected = {
        ADDR_BH1750: "BH1750",
        ADDR_RPR:    "RPR-0521rs",
        ADDR_SCD41:  "SCD41",
        ADDR_DPS310: "DPS310",
    }
    
    all_ok = True
    for addr, name in expected.items():
        if addr in devices:
            print(f"    [OK]   0x{addr:02X}  {name}")
        else:
            print(f"    [FAIL] 0x{addr:02X}  {name}  -- not detected")
            all_ok = False
    
    return all_ok


# ============================================================================
#  Test 2: BH1750 - Power On response
# ============================================================================
def test_bh1750(i2c):
    print()
    print("[Test 2] BH1750 power-on response")
    try:
        # BH1750 has no ID register; verify by sending Power On command
        i2c.writeto(ADDR_BH1750, bytes([0x01]))   # Power On
        time.sleep_ms(10)
        i2c.writeto(ADDR_BH1750, bytes([0x10]))   # Continuous H-Res mode
        time.sleep_ms(180)
        # Try reading 2 bytes - if it succeeds, the sensor is functional
        data = i2c.readfrom(ADDR_BH1750, 2)
        raw = (data[0] << 8) | data[1]
        lux = raw / 1.2
        print(f"    [OK]   Initial reading: raw=0x{raw:04X}, "
              f"illuminance={lux:.1f} lux")
        # Power down
        i2c.writeto(ADDR_BH1750, bytes([0x00]))
        return True
    except Exception as e:
        print(f"    [FAIL] {e}")
        return False


# ============================================================================
#  Test 3: RPR-0521rs - Read MANUFACT_ID + PART_ID
# ============================================================================
def test_rpr0521(i2c):
    print()
    print("[Test 3] RPR-0521rs identification registers")
    try:
        manufact_id = i2c.readfrom_mem(ADDR_RPR, 0x92, 1)[0]
        system_ctrl = i2c.readfrom_mem(ADDR_RPR, 0x40, 1)[0]
        part_id = system_ctrl & 0x3F
        
        print(f"    MANUFACT_ID (0x92) = 0x{manufact_id:02X} (expected: 0xE0)")
        print(f"    PART_ID     (0x40) = 0x{part_id:02X}   (expected: 0x0A)")
        
        if manufact_id == 0xE0 and part_id == 0x0A:
            print("    [OK]   Identification registers match expected values")
            return True
        else:
            print("    [FAIL] Identification mismatch")
            return False
    except Exception as e:
        print(f"    [FAIL] {e}")
        return False


# ============================================================================
#  Test 4: DPS310 - Read PRODUCT_ID
# ============================================================================
def test_dps310(i2c):
    print()
    print("[Test 4] DPS310 PRODUCT_ID register")
    try:
        product_id = i2c.readfrom_mem(ADDR_DPS310, 0x0D, 1)[0]
        print(f"    PRODUCT_ID (0x0D) = 0x{product_id:02X} (expected: 0x10)")
        
        if product_id == 0x10:
            print("    [OK]   PRODUCT_ID matches DPS310 specification")
            return True
        else:
            print("    [FAIL] PRODUCT_ID mismatch")
            return False
    except Exception as e:
        print(f"    [FAIL] {e}")
        return False


# ============================================================================
#  Test 5: SCD41 - Read serial number + run factory self-test
#  This is the most thorough check - it exercises every internal subsystem.
# ============================================================================
def test_scd41(i2c):
    print()
    print("[Test 5] SCD41 serial number and built-in self-test")
    
    # First, force-stop any ongoing periodic measurement
    try:
        i2c.writeto(ADDR_SCD41, bytes([0x3F, 0x86]))   # stop_periodic
        time.sleep_ms(500)
    except OSError:
        pass
    
    # --- 5a: Read 48-bit serial number (command 0x3682) ---
    try:
        i2c.writeto(ADDR_SCD41, bytes([0x36, 0x82]))   # get_serial_number
        time.sleep_ms(2)
        raw = i2c.readfrom(ADDR_SCD41, 9)
        
        # Verify all 3 CRC bytes
        for i in range(0, 9, 3):
            if crc8(raw[i:i+2]) != raw[i+2]:
                print(f"    [FAIL] Serial number CRC verification failed")
                return False
        
        serial = ((raw[0] << 40) | (raw[1] << 32) |
                  (raw[3] << 24) | (raw[4] << 16) |
                  (raw[6] <<  8) |  raw[7])
        print(f"    Serial number: 0x{serial:012X}  [OK]")
    except Exception as e:
        print(f"    [FAIL] Could not read serial number: {e}")
        return False
    
    # --- 5b: Run perform_self_test (command 0x3639) ---
    # Per datasheet 3.9.4: this exercises the NDIR optical system, ADC,
    # I2C interface, and temperature/humidity sensors. Returns 0x0000 on pass.
    print("    Running built-in self-test (takes ~10 seconds) ...")
    try:
        i2c.writeto(ADDR_SCD41, bytes([0x36, 0x39]))   # perform_self_test
        time.sleep_ms(10000)   # Datasheet specifies 10000ms execution time
        raw = i2c.readfrom(ADDR_SCD41, 3)
        
        # Verify CRC
        if crc8(raw[0:2]) != raw[2]:
            print(f"    [FAIL] Self-test response CRC verification failed")
            return False
        
        result = (raw[0] << 8) | raw[1]
        print(f"    Self-test result: 0x{result:04X}")
        
        if result == 0x0000:
            print("    [OK]   SCD41 hardware self-test PASSED")
            print("           (NDIR optics, ADC, I2C, T/RH sensors all functional)")
            return True
        else:
            print(f"    [FAIL] SCD41 self-test FAILED (non-zero result)")
            print(f"           Hardware fault detected - sensor may be defective")
            return False
    except Exception as e:
        print(f"    [FAIL] Self-test command error: {e}")
        return False


# ============================================================================
#  Main
# ============================================================================
def main():
    print("=" * 70)
    print("  Task 2 - Sensor Hardware Self-Test")
    print("=" * 70)
    print()
    
    i2c = I2C(0, scl=Pin(SCL_PIN), sda=Pin(SDA_PIN), freq=I2C_FREQ)
    
    results = {}
    results["I2C scan"]      = test_i2c_scan(i2c)
    results["BH1750"]        = test_bh1750(i2c)
    results["RPR-0521rs"]    = test_rpr0521(i2c)
    results["DPS310"]        = test_dps310(i2c)
    results["SCD41"]         = test_scd41(i2c)
    
    # --- Summary ---
    print()
    print("=" * 70)
    print("  Self-Test Summary")
    print("=" * 70)
    for name, passed in results.items():
        status = "PASS" if passed else "FAIL"
        print(f"    [{status}]  {name}")
    
    all_passed = all(results.values())
    print()
    if all_passed:
        print("  RESULT: All hardware checks passed.")
        print("  All 4 sensors are functioning correctly at the hardware level.")
        print("  The system is ready for data acquisition (Task 2 main program).")
    else:
        failed = [n for n, p in results.items() if not p]
        print(f"  RESULT: {len(failed)} test(s) failed: {', '.join(failed)}")
    print("=" * 70)


main()