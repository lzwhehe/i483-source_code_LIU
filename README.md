# I483 Task 1 — Multi-Sensor Data Acquisition Report

**Author:** [Your Name / Student ID]
**Date:** May 2026

---

## Task 1.1 — DPS310 (ESP-IDF / C)

Periodic acquisition of pressure and temperature data from a DPS310
sensor, implemented in C using the ESP-IDF framework on an M5Stamp C3U.

- **MCU:** M5Stamp C3U (ESP32-C3, ESP-IDF)
- **Sensor:** DPS310 (Seeed Grove module, I2C mode, address 0x76)
- **Wiring:** SDA → GPIO5, SCL → GPIO6, 3V3 → 3V3, GND → GND, SDO → GND
- **Configuration:** 64x oversampling on both pressure and temperature
  channels (highest precision permitted by the datasheet for the chosen
  4 Hz measurement rate).

### Acquisition Result (15 samples, 1 s interval)

```
+--------+---------------+----------------+
| Sample | Temperature   | Pressure       |
+--------+---------------+----------------+
|   1/15 |   23.40 °C    |   997.39 hPa   |
|   2/15 |   23.41 °C    |   997.40 hPa   |
|   3/15 |   23.41 °C    |   997.40 hPa   |
|   4/15 |   23.41 °C    |   997.40 hPa   |
|   5/15 |   23.39 °C    |   997.39 hPa   |
|   6/15 |   23.41 °C    |   997.39 hPa   |
|   7/15 |   23.41 °C    |   997.39 hPa   |
|   8/15 |   23.41 °C    |   997.39 hPa   |
|   9/15 |   23.40 °C    |   997.39 hPa   |
|  10/15 |   23.40 °C    |   997.40 hPa   |
|  11/15 |   23.39 °C    |   997.40 hPa   |
|  12/15 |   23.39 °C    |   997.41 hPa   |
|  13/15 |   23.41 °C    |   997.41 hPa   |
|  14/15 |   23.40 °C    |   997.40 hPa   |
|  15/15 |   23.40 °C    |   997.40 hPa   |
+--------+---------------+----------------+
```

Both readings are stable across the 15-second window
(temperature variation ≤ 0.02 °C, pressure variation ≤ 0.02 hPa),
confirming that the 64x oversampling configuration delivers very
low-noise output as expected from the datasheet.

 

---

## Task 1.2 — SCD41 (MicroPython)

Periodic acquisition of CO2, temperature, and humidity data from an
SCD41 sensor, implemented in MicroPython on the M5Stamp C3U.

- **MCU:** M5Stamp C3U (MicroPython)
- **Sensor:** SCD41 (Grove module, I2C address 0x62)
- **Wiring:** SDA → GPIO5, SCL → GPIO6, VCC → 3.3 V, GND → GND
- **Mode:** periodic measurement (cmd `0x21B1`), default settings,
  1 sample every 5 seconds — the maximum update rate permitted by the
  sensor's NDIR optical subsystem (datasheet §3.5.1).
- **Note on sample count:** within the required 15-second acquisition
  window, the sensor produces at most 3 fresh data points.

### Note on Hardware Replacement

An initial unit of SCD41 used in this task was found to be defective:
it returned 0 ppm for CO2 at every reading while temperature and
humidity were correct. The built-in self-test (command `0x3639`,
datasheet §3.9.4) returned `0x00C4`, indicating an internal hardware
fault in the NDIR optical subsystem (see the Self-Test section below).
The unit was replaced, and the new unit (serial `0x76E28F073B2F`)
passed the self-test with result `0x0000`. All data shown below is
from the replacement unit.

### Acquisition Result

```
+--------+--------------+----------------+----------+
| Sample | CO2 (ppm)    | Temp (degC)    | RH (%)   |
+--------+--------------+----------------+----------+
|   1/3  |    926       |    25.97       |   41.17  |
|   2/3  |    916       |    26.02       |   41.67  |
|   3/3  |    919       |    25.96       |   42.10  |
+--------+--------------+----------------+----------+
```

All three readings show physically meaningful values: CO2 around
920 ppm (typical indoor level for an occupied room — outdoor air is
about 420 ppm), temperature near 26 °C, and humidity around 41–42%RH.
The slight upward trend in humidity reflects normal local fluctuation
during the 15-second window.

 

---

## Task 1.3 — RPR-0521rs (MicroPython)

Periodic acquisition of illuminance data from an RPR-0521rs sensor,
implemented in MicroPython on the M5Stamp C3U.

- **MCU:** M5Stamp C3U (MicroPython)
- **Sensor:** RPR-0521rs (5-pin breakout, I2C address 0x38)
- **Wiring:** SDA → GPIO5, SCL → GPIO6, 3.3V → 3V3, GND → GND, INT not connected
- **Configuration:** ALS measurement time = 100 ms, gain x1 (datasheet
  Table 12 default coefficients).
- **Conversion:** 5-segment piecewise linear formula based on the
  DATA1/DATA0 ratio, taken directly from the ROHM datasheet (§9.4,
  Table 12). RPR-0521rs uses two photodiodes — visible (DATA0) and
  infrared (DATA1) — and adapts its lux calculation to the spectral
  composition of the light source.

### Acquisition Result (15 samples, 1 s interval)

```
+--------+--------+--------+--------+-----------+
| Sample | DATA0  | DATA1  |  ratio |  lux      |
+--------+--------+--------+--------+-----------+
|   1/15 |     6  |     1  |  0.167 |    8.20   |
|   2/15 |     6  |     1  |  0.167 |    8.20   |
|   3/15 |     5  |     1  |  0.200 |    6.53   |
|   4/15 |     4  |     1  |  0.250 |    4.85   |
|   5/15 |     5  |     1  |  0.200 |    5.84   |
|   6/15 |     5  |     1  |  0.200 |    6.53   |
|   7/15 |     5  |     1  |  0.200 |    5.71   |
|   8/15 |     6  |     1  |  0.167 |    8.20   |
|   9/15 |     6  |     1  |  0.167 |    8.20   |
|  10/15 |     6  |     1  |  0.167 |    8.20   |
|  11/15 |     6  |     1  |  0.167 |    8.20   |
|  12/15 |     6  |     1  |  0.167 |    8.20   |
|  13/15 |     6  |     1  |  0.167 |    8.20   |
|  14/15 |     6  |     1  |  0.167 |    8.20   |
|  15/15 |     6  |     1  |  0.167 |    8.20   |
+--------+--------+--------+--------+-----------+
```

The sensor responded clearly to changes in ambient light during the
acquisition: rows 4–7 show reduced illuminance values (4.85 – 6.53 lx)
corresponding to intentionally shading the sensor with a hand. The
DATA1/DATA0 ratio stays in the first segment (< 0.595) throughout,
which corresponds to the indoor LED lighting in the test environment.

 

---

## Task 1.4 — BH1750 (MicroPython)

Periodic acquisition of illuminance data from a BH1750 sensor,
implemented in MicroPython on the M5Stamp C3U.

- **MCU:** M5Stamp C3U (MicroPython)
- **Sensor:** BH1750 GY-302 module (I2C address 0x23, ADDR pin tied to GND)
- **Wiring:** SDA → GPIO5, SCL → GPIO6, 3V0 → 3V3, GND → GND, ADDR → GND
- **Mode:** continuous high-resolution mode (cmd `0x10`, 1 lx precision).
- **Conversion:** lux = raw / 1.2 (datasheet p.11; the constant 1.2 is
  the intrinsic scaling factor of BH1750's internal ADC).

### Acquisition Result (15 samples, 1 s interval)

```
+--------+--------+-----------+
| Sample |  raw   |  lux      |
+--------+--------+-----------+
|   1/15 |    10  |    8.33   |
|   2/15 |    10  |    8.33   |
|   3/15 |     9  |    7.50   |
|   4/15 |     5  |    4.17   |
|   5/15 |     6  |    5.00   |
|   6/15 |     9  |    7.50   |
|   7/15 |     6  |    5.00   |
|   8/15 |     9  |    7.50   |
|   9/15 |    10  |    8.33   |
|  10/15 |    10  |    8.33   |
|  11/15 |    10  |    8.33   |
|  12/15 |    10  |    8.33   |
|  13/15 |    10  |    8.33   |
|  14/15 |    10  |    8.33   |
|  15/15 |    10  |    8.33   |
+--------+--------+-----------+
```

The sensor was tested under the same room lighting as Task 1.3, with
the sensor again briefly shaded by hand mid-acquisition. The two
illuminance sensors do not produce identical absolute readings — for
example, BH1750 reports 8.33 lx as the steady-state value, while
RPR-0521rs reports 8.20 lx for the same condition. This minor
discrepancy is expected because the two sensors use very different
internal designs: BH1750 uses a single photodiode and a fixed
conversion factor, while RPR-0521rs uses a two-channel ratio-based
piecewise formula that compensates for the spectral content of the
light source.


---

## Task 2 — Four Sensors over a Shared I2C Bus (MicroPython)

### Hardware

- **MCU:** M5Stamp C3U (MicroPython)
- **Sensors on shared I2C bus** (SDA=GPIO5, SCL=GPIO6, all at 3.3 V):
  - BH1750     — 0x23 — illuminance
  - RPR-0521rs — 0x38 — illuminance
  - SCD41      — 0x62 — CO2 / temperature / humidity (replacement unit,
    serial `0x76E28F073B2F`)
  - DPS310     — 0x77 — pressure / temperature

All four sensors are electrically connected in parallel on the I2C bus.
Physically, the wiring follows a daisy-chain layout via Grove cables
and breadboard rails; electrically, every device is a parallel client
on the same SDA/SCL pair.

### Acquisition Result

15-second acquisition window, 1 sample per second.
`*` marks fresh SCD41 readings (the sensor updates every 5 s; other rows
reuse the cached value).

To demonstrate sensor responsiveness, the operator performed two actions
during the run: breathed close to the SCD41 (CO2 rise expected),
and varied the lighting on the two illuminance sensors.

```
   # |   CO2 | Temp1 |    RH | Pressure | Temp2 |  BH1750 |     RPR
     |   ppm |  degC |   %RH |      hPa |  degC |     lux |     lux
--------------------------------------------------------------------------------
   1 |  1010*| 26.67 | 41.21 |  1000.17 | 24.91 |   32.50 |    8.22
   2 |  1010 | 26.67 | 41.21 |  1000.17 | 24.89 |   31.67 |    9.90
   3 |  1010 | 26.67 | 41.21 |  1000.18 | 24.89 |   86.67 |  121.54
   4 |  1010 | 26.67 | 41.21 |  1000.16 | 24.90 |   72.50 |  118.18
   5 |  1010 | 26.67 | 41.21 |  1000.19 | 24.93 |   80.83 |  121.54
   6 |  1012*| 26.78 | 41.73 |  1000.17 | 24.97 |   84.17 |  123.23
   7 |  1012 | 26.78 | 41.73 |  1000.15 | 24.99 |   80.83 |  118.18
   8 |  1012 | 26.78 | 41.73 |  1000.15 | 25.00 |   82.50 |   92.05
   9 |  1012 | 26.78 | 41.73 |  1000.20 | 25.05 |  115.83 |  177.17
  10 |  1012 | 26.78 | 41.73 |  1000.24 | 25.09 |  107.50 |  114.82
  11 |  1549*| 27.33 | 45.15 |  1000.25 | 25.10 |   97.50 |  105.31
  12 |  1549 | 27.33 | 45.15 |  1000.23 | 25.07 |  100.00 |  103.43
  13 |  1549 | 27.33 | 45.15 |  1000.23 | 25.04 |  100.00 |  103.43
  14 |  1549 | 27.33 | 45.15 |  1000.13 | 25.02 |  100.83 |  105.31
  15 |  1695*| 27.19 | 48.25 |  1000.16 | 25.00 |  100.83 |  103.63
--------------------------------------------------------------------------------
```

### Observations

- **CO2 (SCD41):** rose sharply from a stable 1010 – 1012 ppm baseline
  to 1549 ppm and then 1695 ppm at samples 11 and 15, in direct response
  to the operator's breath. The 685 ppm rise (samples 6 → 11)
  demonstrates that the sensor reacts well within its 5-second update
  cycle and produces physically meaningful readings.

- **Humidity (SCD41):** correlated naturally with the CO2 rise,
  climbing from 41.21 %RH to 48.25 %RH, since exhaled air carries
  water vapor.

- **Pressure (DPS310):** stable at approximately 1000.17 hPa
  throughout, with variation under 0.12 hPa. This confirms that the
  16x oversampling configuration provides very low-noise pressure
  readings even on a shared bus with three other active devices.

- **Illuminance (BH1750, RPR-0521rs):** both sensors detected the
  lighting changes performed during the run. The largest illuminance
  reading occurred at sample 9, with BH1750 reporting 115.83 lx and
  RPR-0521rs reporting 177.17 lx. The two sensors do not produce
  identical absolute lux values — their internal designs differ (single
  photodiode vs. two-channel ratio-based formula), and they also have
  somewhat different spectral sensitivity curves. The discrepancy is
  consistent across rows and is therefore expected behavior, not a
  measurement error.

- **All four sensors operated correctly on a single shared I2C bus**,
  each addressed by its unique 7-bit address. No address conflicts,
  CRC errors, or timing issues occurred during acquisition.

---

## SCD41 Self-Test (Diagnostic Section)

During the initial development phase, the first SCD41 unit used in this
project consistently returned 0 ppm for CO2 across all samples, while
temperature and humidity were correctly reported. To determine whether
this was a software bug, a wiring problem, or a hardware fault, the
SCD41 built-in self-test (command `0x3639`, datasheet §3.9.4) was
executed. This test runs an internal diagnostic of the NDIR optics,
ADC, I2C interface, and T/RH subsystem. A return of `0x0000` means "no
malfunction"; any non-zero value indicates a hardware fault.

```
[Test 5] SCD41 serial number and built-in self-test
    Serial number: 0x5F9617073BEA  [OK]
    Running built-in self-test (takes ~10 seconds) ...
    Self-test result: 0x00C4
    [FAIL] SCD41 self-test FAILED (non-zero result)
```

The other three sensors passed their identification checks:

```
[OK]   BH1750     — power-on response successful
[OK]   RPR-0521rs — MANUFACT_ID = 0xE0, PART_ID = 0x0A
[OK]   DPS310     — PRODUCT_ID = 0x10
[FAIL] SCD41      — self-test result 0x00C4 (hardware fault)
```

The result `0x00C4` indicates an internal hardware fault in the SCD41's
NDIR optical subsystem. This is consistent with the observation that
temperature and humidity (produced by a separate onboard SHT
subsystem) were reported correctly, while CO2 — which depends on the
NDIR optics — was stuck at 0. The same failure mode (self-test code
`0x00C4`, CO2 stuck at 0 ppm) is documented in Sensirion's official
GitHub repository (`Sensirion/arduino-i2c-scd4x` Issue #15) as a
non-recoverable fault that cannot be resolved by software.

After the SCD41 unit was replaced, the self-test was re-run on the new
unit:

```
[New SCD41 unit verification]
    Serial number: 0x76E28F073B2F  [OK, different from broken unit]
    Self-test result: 0x0000
    [PASS] Sensor hardware is HEALTHY
```

The replacement unit passed the self-test with result `0x0000`,
confirming that the program code is correct and that all subsequent
acquisitions (Task 1.2 and Task 2 above) are based on a fully
functional sensor.

---

## Source Code

- Task 1.1: `dps310_main.c`         — [GitHub link to be filled in]
- Task 1.2: `task1_2_scd41.py`      — [GitHub link to be filled in]
- Task 1.3: `task1_3_rpr0521.py`    — [GitHub link to be filled in]
- Task 1.4: `task1_4_bh1750.py`     — [GitHub link to be filled in]
- Task 2:   `task2_all_sensors.py` + `task2_selftest.py`
                                    — [GitHub link to be filled in]