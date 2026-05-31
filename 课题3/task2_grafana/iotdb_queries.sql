-- I483 課題3 項目2 — example IoTDB queries for Grafana panels
-- Replace s2410431 with your STUDENT id and SCD41/co2 with your sensor/data_type.
-- In Grafana's IoTDB datasource, $__from / $__to are bound to the dashboard
-- time range (epoch ms). Use them so panels follow the time picker.

-- =====================================================================
-- 2(a)  RAW 課題2-1a time series (no aggregation, plot every point)
-- =====================================================================
SELECT co2
FROM root.i483.s2410431.SCD41
WHERE time >= $__from AND time <= $__to;

-- =====================================================================
-- 2(b)  課題2-1c ROLLING AVERAGE series (already computed upstream,
--        stored as its own measurement). Plot it as-is, no re-aggregation.
--        Adjust the path/measurement to wherever your 課題2-1c writes it.
-- =====================================================================
SELECT co2_rolling_avg
FROM root.i483.s2410431.SCD41
WHERE time >= $__from AND time <= $__to;

-- =====================================================================
-- 2(c)  課題3-1a analytics (Flink min/max/avg). Plot the three series
--        on one panel by adding three queries (min, max, avg).
-- =====================================================================
SELECT SCD41_avg_co2, SCD41_min_co2, SCD41_max_co2
FROM root.i483.s2410431.analytics
WHERE time >= $__from AND time <= $__to;

-- =====================================================================
-- 2(d)  課題2-1a data aggregated by IoTDB on the SERVER side.
--        Mirror the Flink job: 30 s step, 5 min window -> use a 5-min
--        sliding aggregation, emitted every 30 s.
--        Syntax: GROUP BY ([start, end), every, window)
-- =====================================================================
SELECT AVG(co2), MIN_VALUE(co2), MAX_VALUE(co2)
FROM root.i483.s2410431.SCD41
GROUP BY ([$__from, $__to), 30s, 5m);

-- Simpler tumbling 30 s average (if you just want server-side downsampling):
-- SELECT AVG(co2) FROM root.i483.s2410431.SCD41
-- GROUP BY ([$__from, $__to), 30s);
