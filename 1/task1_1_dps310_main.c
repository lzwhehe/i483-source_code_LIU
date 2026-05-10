/*
 * ============================================================================
 *  Task 1.1 - DPS310 Pressure & Temperature Sensor Read Program
 *
 *  Hardware: M5Stamp C3U + DPS310 (Seeed Grove module, I2C mode)
 *  Wiring:   SDI(SDA) -> GPIO5
 *            CSK(SCL) -> GPIO6
 *            3V3      -> 3V3
 *            GND      -> GND
 *            SDO      -> GND
 *  Address:  0x76 (since SDO is tied to GND)
 *
 *  Datasheet reference: Infineon DPS310 Datasheet v1.2
 *  https://www.infineon.com/dgdl/Infineon-DPS310-DataSheet-v01_02-EN.pdf
 *
 *  Program flow (cross-referenced to datasheet sections):
 *    1. Initialize I2C
 *    2. Read Product ID (register 0x0D, expected 0x10)         -- DS §7.6
 *    3. Wait for sensor & coefficient ready
 *       (MEAS_CFG register 0x08, bits 6/7)                     -- DS §7.6
 *    4. Read 18 bytes of calibration coefficients
 *       (registers 0x10~0x21)                                  -- DS §8.11
 *    5. Configure pressure measurement (PRS_CFG = 0x06)        -- DS §7.5
 *    6. Configure temperature measurement (TMP_CFG = 0x07)     -- DS §7.5
 *    7. Configure bit-shift (CFG_REG = 0x09; required when
 *       oversampling > 8x)                                     -- DS §4.9.3
 *    8. Start continuous measurement mode
 *       (MEAS_CFG = 0x08, MEAS_CTRL = 0b111)                   -- DS §7.4
 *    9. Loop 15 times: read raw values, apply compensation
 *       formula, print result                                  -- DS §4.9.1
 * ============================================================================
 */

#include <stdio.h>
#include <stdint.h>
#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "driver/i2c_master.h"
#include "esp_log.h"

// ============================================================================
//  Configuration constants
// ============================================================================
#define I2C_PORT        I2C_NUM_0
#define I2C_SDA_GPIO    5           // M5Stamp C3U pin G5
#define I2C_SCL_GPIO    6           // M5Stamp C3U pin G6
#define I2C_FREQ_HZ     400000      // I2C speed 400 kHz (DPS310 supports up to
                                    // 3.4 MHz; 400 kHz is a safe choice)

#define DPS310_ADDR     0x76        // SDO tied to GND -> address fixed at 0x76
                                    // (datasheet §7.2)

#define SAMPLE_COUNT        15      // Task requirement: 15 samples
#define SAMPLE_INTERVAL_MS  1000    // 1 sample per second

// ============================================================================
//  DPS310 register addresses (from datasheet §7.1, Register Map)
// ============================================================================
#define REG_PSR_B2      0x00    // Pressure ADC, byte 2 (MSB)
#define REG_PSR_B1      0x01    // Pressure ADC, byte 1
#define REG_PSR_B0      0x02    // Pressure ADC, byte 0 (LSB)
#define REG_TMP_B2      0x03    // Temperature ADC, byte 2 (MSB)
#define REG_TMP_B1      0x04    // Temperature ADC, byte 1
#define REG_TMP_B0      0x05    // Temperature ADC, byte 0 (LSB)
#define REG_PRS_CFG     0x06    // Pressure config: rate + oversampling
#define REG_TMP_CFG     0x07    // Temperature config: rate + oversampling + source
#define REG_MEAS_CFG    0x08    // Measurement mode + sensor-ready flags
#define REG_CFG_REG     0x09    // Interrupt / FIFO / bit-shift config
#define REG_PRODUCT_ID  0x0D    // Product ID (must read as 0x10)
#define REG_COEF_BASE   0x10    // Calibration coefficient start
                                // (18 bytes total)

// ============================================================================
//  Compression scaling factors kP, kT (datasheet §4.9.3, Table 9)
//  These are the "divisors" used in the compensation formula.
//  The value depends on the chosen oversampling rate.
//  We use 64x oversampling, so the scale factor is 1040384.
// ============================================================================
//  Oversampling   1   ->    524288
//  Oversampling   2   ->   1572864
//  Oversampling   4   ->   3670016
//  Oversampling   8   ->   7864320
//  Oversampling  16   ->    253952  (smaller values when >8x because of the
//                                    internal BIT-shift mechanism)
//  Oversampling  32   ->    516096
//  Oversampling  64   ->   1040384  <-- our setting
//  Oversampling 128   ->   2088960
#define KP_64_TIMES     1040384.0f   // Pressure scale factor at 64x oversampling
#define KT_64_TIMES     1040384.0f   // Temperature scale factor at 64x oversampling

static const char *TAG = "DPS310";

// I2C bus and device handles (ESP-IDF v5+ new driver API)
static i2c_master_bus_handle_t s_bus_handle;
static i2c_master_dev_handle_t s_dev_handle;

// DPS310 calibration coefficients (decoded from the 18-byte read).
// All are signed integers, with bit widths ranging from 12 to 20 bits
// (datasheet §8.11).
static int32_t c0, c1;
static int32_t c00, c10;
static int32_t c01, c11, c20, c21, c30;

// ============================================================================
//  Low-level I2C helpers: read/write DPS310 registers
// ============================================================================

/* Write a single byte to the specified register */
static esp_err_t dps310_write_reg(uint8_t reg, uint8_t val)
{
    uint8_t buf[2] = { reg, val };
    return i2c_master_transmit(s_dev_handle, buf, 2, 100);
}

/* Read N consecutive bytes starting from the specified register */
static esp_err_t dps310_read_regs(uint8_t reg, uint8_t *data, size_t len)
{
    return i2c_master_transmit_receive(s_dev_handle, &reg, 1, data, len, 100);
}

/* Read a single register */
static esp_err_t dps310_read_reg(uint8_t reg, uint8_t *val)
{
    return dps310_read_regs(reg, val, 1);
}

// ============================================================================
//  Helper: interpret an unsigned integer as a signed integer of the given
//  bit-width (two's complement).
//
//  Reason: DPS310's calibration coefficients are signed, but the registers
//  read out as unsigned bytes. Sign extension based on the field width
//  (12 / 16 / 20 bits) is required.
//
//  Example: 0xFFF read as a 12-bit value is actually -1, not 4095.
// ============================================================================
static int32_t two_complement(uint32_t value, uint8_t bits)
{
    if (value & (1U << (bits - 1))) {                  // MSB == 1 -> negative
        return (int32_t)(value - (1U << bits));         // subtract 2^bits
    }
    return (int32_t)value;
}

// ============================================================================
//  Step 4: Read and decode the 18-byte calibration coefficient block
//          (datasheet §8.11, Table 18)
//
//  The register layout is tightly packed and the coefficients have variable
//  bit widths, so the bytes must be re-assembled bit-by-bit:
//
//    c0:  12 bits  (from 0x10[7:0] + 0x11[7:4])
//    c1:  12 bits  (from 0x11[3:0] + 0x12[7:0])
//    c00: 20 bits  (from 0x13[7:0] + 0x14[7:0] + 0x15[7:4])
//    c10: 20 bits  (from 0x15[3:0] + 0x16[7:0] + 0x17[7:0])
//    c01: 16 bits  (0x18 + 0x19)
//    c11: 16 bits  (0x1A + 0x1B)
//    c20: 16 bits  (0x1C + 0x1D)
//    c21: 16 bits  (0x1E + 0x1F)
//    c30: 16 bits  (0x20 + 0x21)
// ============================================================================
static esp_err_t dps310_read_coefficients(void)
{
    uint8_t coef[18];
    esp_err_t ret = dps310_read_regs(REG_COEF_BASE, coef, 18);
    if (ret != ESP_OK) return ret;

    // c0: 12-bit signed
    uint32_t raw_c0 = ((uint32_t)coef[0] << 4) | (coef[1] >> 4);
    c0 = two_complement(raw_c0, 12);

    // c1: 12-bit signed
    uint32_t raw_c1 = (((uint32_t)coef[1] & 0x0F) << 8) | coef[2];
    c1 = two_complement(raw_c1, 12);

    // c00: 20-bit signed
    uint32_t raw_c00 = ((uint32_t)coef[3] << 12) | ((uint32_t)coef[4] << 4) | (coef[5] >> 4);
    c00 = two_complement(raw_c00, 20);

    // c10: 20-bit signed
    uint32_t raw_c10 = (((uint32_t)coef[5] & 0x0F) << 16) | ((uint32_t)coef[6] << 8) | coef[7];
    c10 = two_complement(raw_c10, 20);

    // c01, c11, c20, c21, c30: all 16-bit signed
    c01 = two_complement(((uint32_t)coef[8]  << 8) | coef[9],  16);
    c11 = two_complement(((uint32_t)coef[10] << 8) | coef[11], 16);
    c20 = two_complement(((uint32_t)coef[12] << 8) | coef[13], 16);
    c21 = two_complement(((uint32_t)coef[14] << 8) | coef[15], 16);
    c30 = two_complement(((uint32_t)coef[16] << 8) | coef[17], 16);

    ESP_LOGI(TAG, "Calibration coefficients loaded:");
    ESP_LOGI(TAG, "  c0=%ld  c1=%ld", (long)c0, (long)c1);
    ESP_LOGI(TAG, "  c00=%ld  c10=%ld", (long)c00, (long)c10);
    ESP_LOGI(TAG, "  c01=%ld  c11=%ld  c20=%ld  c21=%ld  c30=%ld",
             (long)c01, (long)c11, (long)c20, (long)c21, (long)c30);
    return ESP_OK;
}

// ============================================================================
//  Step 9: Read raw ADC values, apply the compensation formula, and produce
//          the true temperature and pressure readings.
//
//  Compensation formulas come from datasheet §4.9.1:
//
//    T_raw_sc           = T_raw / kT
//    T_compensated [°C] = c0 * 0.5 + c1 * T_raw_sc
//
//    P_raw_sc           = P_raw / kP
//    P_compensated [Pa] = c00 + P_raw_sc * (c10 + P_raw_sc * (c20 + P_raw_sc * c30))
//                       + T_raw_sc * c01
//                       + T_raw_sc * P_raw_sc * (c11 + P_raw_sc * c21)
// ============================================================================
static esp_err_t dps310_read_measurement(float *temp_c, float *pres_hpa)
{
    uint8_t raw[6];
    // One transaction reads 6 bytes: 3 pressure bytes + 3 temperature bytes
    esp_err_t ret = dps310_read_regs(REG_PSR_B2, raw, 6);
    if (ret != ESP_OK) return ret;

    // Re-assemble 24-bit signed ADC values
    uint32_t raw_psr = ((uint32_t)raw[0] << 16) | ((uint32_t)raw[1] << 8) | raw[2];
    uint32_t raw_tmp = ((uint32_t)raw[3] << 16) | ((uint32_t)raw[4] << 8) | raw[5];
    int32_t psr_raw = two_complement(raw_psr, 24);
    int32_t tmp_raw = two_complement(raw_tmp, 24);

    // Apply scaling
    float t_scaled = (float)tmp_raw / KT_64_TIMES;
    float p_scaled = (float)psr_raw / KP_64_TIMES;

    // Temperature compensation (units: °C)
    *temp_c = (float)c0 * 0.5f + (float)c1 * t_scaled;

    // Pressure compensation (units: Pa)
    float p_pa = (float)c00
                + p_scaled * ((float)c10 + p_scaled * ((float)c20 + p_scaled * (float)c30))
                + t_scaled * (float)c01
                + t_scaled * p_scaled * ((float)c11 + p_scaled * (float)c21);

    *pres_hpa = p_pa / 100.0f;   // Convert Pa to hPa (1 hPa = 100 Pa)
    return ESP_OK;
}

// ============================================================================
//  Main
// ============================================================================
void app_main(void)
{
    vTaskDelay(pdMS_TO_TICKS(500));    // Allow power supply to settle

    ESP_LOGI(TAG, "=== DPS310 Pressure & Temperature Sensor (Task 1.1) ===");

    // ----- Step 1: Initialize the I2C bus and add DPS310 as a device -----
    i2c_master_bus_config_t bus_cfg = {
        .clk_source = I2C_CLK_SRC_DEFAULT,
        .i2c_port = I2C_PORT,
        .scl_io_num = I2C_SCL_GPIO,
        .sda_io_num = I2C_SDA_GPIO,
        .glitch_ignore_cnt = 7,
        .flags.enable_internal_pullup = true,
    };
    ESP_ERROR_CHECK(i2c_new_master_bus(&bus_cfg, &s_bus_handle));

    i2c_device_config_t dev_cfg = {
        .dev_addr_length = I2C_ADDR_BIT_LEN_7,
        .device_address = DPS310_ADDR,
        .scl_speed_hz = I2C_FREQ_HZ,
    };
    ESP_ERROR_CHECK(i2c_master_bus_add_device(s_bus_handle, &dev_cfg, &s_dev_handle));
    ESP_LOGI(TAG, "I2C ready: SDA=GPIO%d, SCL=GPIO%d, addr=0x%02X",
             I2C_SDA_GPIO, I2C_SCL_GPIO, DPS310_ADDR);

    // ----- Step 2: Read Product ID to verify the chip (datasheet §7.6) -----
    uint8_t product_id = 0;
    ESP_ERROR_CHECK(dps310_read_reg(REG_PRODUCT_ID, &product_id));
    ESP_LOGI(TAG, "Product ID = 0x%02X (expected 0x10)", product_id);
    if (product_id != 0x10) {
        ESP_LOGE(TAG, "Product ID mismatch! Check wiring.");
        return;
    }

    // ----- Step 3: Wait for SENSOR_RDY and COEF_RDY -----
    // (datasheet §7.6, MEAS_CFG bits 6 and 7)
    // After power-on, the sensor and its calibration coefficients take
    // about 40 ms to become ready.
    ESP_LOGI(TAG, "Waiting for sensor & coefficients ready...");
    for (int i = 0; i < 100; i++) {
        uint8_t meas_cfg = 0;
        dps310_read_reg(REG_MEAS_CFG, &meas_cfg);
        if ((meas_cfg & 0xC0) == 0xC0) {       // bit6=COEF_RDY, bit7=SENSOR_RDY
            ESP_LOGI(TAG, "Sensor ready (MEAS_CFG=0x%02X)", meas_cfg);
            break;
        }
        vTaskDelay(pdMS_TO_TICKS(10));
    }

    // ----- Step 4: Read calibration coefficients -----
    ESP_ERROR_CHECK(dps310_read_coefficients());

    // ----- Step 5: Configure pressure measurement, PRS_CFG = 0x26 -----
    // (datasheet §7.5)
    //   bits[6:4] PM_RATE = 010   -> 4 measurements per second
    //   bits[3:0] PM_PRC  = 0110  -> 64x oversampling (high precision)
    //   combined: 0010 0110 = 0x26
    ESP_ERROR_CHECK(dps310_write_reg(REG_PRS_CFG, 0x26));

    // ----- Step 6: Configure temperature measurement, TMP_CFG = 0xA6 -----
    // (datasheet §7.5)
    //   bit[7]    TMP_EXT  = 1    -> use external MEMS temperature sensor
    //                                (this matches the calibration source)
    //   bits[6:4] TMP_RATE = 010  -> 4 measurements per second
    //   bits[3:0] TMP_PRC  = 0110 -> 64x oversampling
    //   combined: 1010 0110 = 0xA6
    ESP_ERROR_CHECK(dps310_write_reg(REG_TMP_CFG, 0xA6));

    // ----- Step 7: Configure bit-shift (datasheet §4.9.3) -----
    // When oversampling > 8x, P_SHIFT and T_SHIFT must be set to 1,
    // otherwise the data alignment is wrong.
    // CFG_REG bit3=T_SHIFT=1, bit2=P_SHIFT=1 -> 0x0C
    ESP_ERROR_CHECK(dps310_write_reg(REG_CFG_REG, 0x0C));

    // ----- Step 8: Start continuous measurement, MEAS_CFG = 0x07 -----
    // (datasheet §7.4, Table 12)
    //   MEAS_CTRL[2:0] = 111 -> continuous pressure + temperature measurement
    ESP_ERROR_CHECK(dps310_write_reg(REG_MEAS_CFG, 0x07));
    ESP_LOGI(TAG, "Continuous measurement started.");

    // The first measurement needs some time to complete (rate 4 Hz -> ~250 ms)
    vTaskDelay(pdMS_TO_TICKS(500));

    // ----- Step 9: Acquisition loop, 15 samples -----
    ESP_LOGI(TAG, "");
    ESP_LOGI(TAG, "=== Start sampling (%d samples, %d ms interval) ===",
             SAMPLE_COUNT, SAMPLE_INTERVAL_MS);
    printf("\n");
    printf("+--------+---------------+----------------+\n");
    printf("| Sample | Temperature   | Pressure       |\n");
    printf("+--------+---------------+----------------+\n");

    for (int i = 1; i <= SAMPLE_COUNT; i++) {
        float temp_c, pres_hpa;
        if (dps310_read_measurement(&temp_c, &pres_hpa) == ESP_OK) {
            printf("|  %3d/%2d| %8.2f °C   | %9.2f hPa  |\n",
                   i, SAMPLE_COUNT, temp_c, pres_hpa);
        } else {
            printf("|  %3d/%2d| READ ERROR    | READ ERROR     |\n", i, SAMPLE_COUNT);
        }
        vTaskDelay(pdMS_TO_TICKS(SAMPLE_INTERVAL_MS));
    }

    printf("+--------+---------------+----------------+\n");
    ESP_LOGI(TAG, "=== Sampling complete. ===");

    // Idle loop to keep app_main alive
    while (1) {
        vTaskDelay(pdMS_TO_TICKS(10000));
    }
}