-- Kadai 3 Task 2 Grafana / IoTDB query templates
-- Student: s2410431

-- Check all available time series first if a panel has no data:
SHOW TIMESERIES root.devdb.i483.sensors.s2410431.**;

-- 2(a) Raw Kadai 2 Task 1a data
-- Panel title: 2(a) Raw SCD41 CO2
SELECT co2
FROM root.devdb.i483.sensors.s2410431.SCD41
WHERE time >= $__from AND time <= $__to;

-- 2(b) Rolling Average from Kadai 2 Task 1c
-- Source Kafka topic: i483-sensors-s2410431-BH1750_avg-illumination
-- Panel title: 2(b) BH1750 Rolling Average
SELECT illumination
FROM root.devdb.i483.sensors.s2410431.BH1750_avg
WHERE time >= $__from AND time <= $__to;

-- 2(c) Kadai 3 Task 1 Flink analytics
-- Source Kafka topics:
--   i483-sensors-s2410431-analytics-s2410431_SCD41_min-co2
--   i483-sensors-s2410431-analytics-s2410431_SCD41_max-co2
--   i483-sensors-s2410431-analytics-s2410431_SCD41_avg-co2
-- Panel title: 2(c) Flink Analytics SCD41 CO2
SELECT SCD41_min_co2, SCD41_max_co2, SCD41_avg_co2
FROM root.devdb.i483.sensors.s2410431.analytics
WHERE time >= $__from AND time <= $__to;

-- 2(d) IoTDB aggregation over raw data
-- Same 5-minute window and 30-second step as Task 1.
-- Panel title: 2(d) IoTDB Aggregation SCD41 CO2
SELECT MIN_VALUE(co2), MAX_VALUE(co2), AVG(co2)
FROM root.devdb.i483.sensors.s2410431.SCD41
GROUP BY ([$__from, $__to), 30s, 5m);

-- 2(e) Comparison notes for the report:
-- - 2(b) is computed by the Kadai 2 Python processor before Grafana.
-- - 2(c) is computed by Flink and then stored as analytics time series.
-- - 2(d) is computed by IoTDB at query time from raw data.
-- - Flink analytics and IoTDB aggregation should be similar when they use the
--   same raw data, window size, and time range.
