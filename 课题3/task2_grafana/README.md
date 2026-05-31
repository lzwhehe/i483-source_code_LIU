# Kadai 3 Task 2 - Grafana Visualization

Grafana URL:

```text
http://150.65.230.59:3000/d/adqgh75/s2410431?orgId=1&from=now-6h&to=now&timezone=browser
```

Task 2 is a visualization task. The data path is:

```text
Kafka topics -> IoTDB time series -> Grafana panels
```

Your Task 1 Flink job must keep running so the analytics topics continue to
receive `min / max / avg` values.

## Panels To Create

Create or edit the dashboard `s2410431` and add these panels.

### 2(a) Raw time series from Kadai 2 Task 1a

Example sensor: SCD41 CO2.

Panel title:

```text
2(a) Raw SCD41 CO2
```

Query:

```sql
SELECT co2
FROM root.devdb.i483.sensors.s2410431.SCD41
WHERE time >= $__from AND time <= $__to;
```

This shows the original raw values sent by the ESP32.

### 2(b) Rolling Average from Kadai 2 Task 1c

Your Kadai 2 processor publishes:

```text
i483-sensors-s2410431-BH1750_avg-illumination
```

The usual IoTDB path for that topic is:

```text
root.devdb.i483.sensors.s2410431.BH1750_avg.illumination
```

Panel title:

```text
2(b) BH1750 Rolling Average
```

Query:

```sql
SELECT illumination
FROM root.devdb.i483.sensors.s2410431.BH1750_avg
WHERE time >= $__from AND time <= $__to;
```

This panel should show only the rolling average series, not the raw BH1750 data.

### 2(c) Kadai 3 Task 1 Flink Analytics

This visualizes the values produced by `task1_flink`.

Panel title:

```text
2(c) Flink Analytics SCD41 CO2
```

Query:

```sql
SELECT SCD41_min_co2, SCD41_max_co2, SCD41_avg_co2
FROM root.devdb.i483.sensors.s2410431.analytics
WHERE time >= $__from AND time <= $__to;
```

This shows the Flink-computed minimum, maximum, and average for the latest
5-minute window, emitted every 30 seconds.

### 2(d) IoTDB Aggregation

This uses IoTDB aggregation directly on the raw data, so it can be compared
against the Flink analytics result.

Panel title:

```text
2(d) IoTDB Aggregation SCD41 CO2
```

Query:

```sql
SELECT MIN_VALUE(co2), MAX_VALUE(co2), AVG(co2)
FROM root.devdb.i483.sensors.s2410431.SCD41
GROUP BY ([$__from, $__to), 30s, 5m);
```

This mirrors the Task 1 requirement: every 30 seconds, use the latest 5 minutes.

## Grafana Click Steps

1. Open the dashboard URL.
2. Click `Add` / `Add visualization` / `Add panel`.
3. Choose the IoTDB data source.
4. Use `SQL: Full Customized`.
5. Fill Grafana's `SELECT`, `FROM`, `WHERE`, and `CONTROL` boxes separately.
   Do not paste the whole SQL statement into one box.
6. Click the refresh button or open `Query inspector` after changing a query.
7. Set visualization type to `Time series`.
8. Set the panel title.
9. Click `Apply`.
10. Repeat for all four panels.
11. Click the dashboard save icon.

Important notes from the lecture slides:

- Always click `Apply` and save the dashboard.
- Query changes may need the refresh button or `Query inspector` to run.
- Time conditions should follow the dashboard time picker.
- For custom time aggregation, use Grafana variables `$__from` and `$__to`
  with two underscores.

## Grafana Box Inputs

Use these values in the IoTDB query editor.

### 2(a)

```text
SELECT: co2
FROM: root.devdb.i483.sensors.s2410431.SCD41
WHERE: time >= $__from AND time <= $__to
CONTROL:
```

### 2(b)

```text
SELECT: illumination
FROM: root.devdb.i483.sensors.s2410431.BH1750_avg
WHERE: time >= $__from AND time <= $__to
CONTROL:
```

### 2(c)

```text
SELECT: SCD41_min_co2, SCD41_max_co2, SCD41_avg_co2
FROM: root.devdb.i483.sensors.s2410431.analytics
WHERE: time >= $__from AND time <= $__to
CONTROL:
```

### 2(d)

```text
SELECT: MIN_VALUE(co2), MAX_VALUE(co2), AVG(co2)
FROM: root.devdb.i483.sensors.s2410431.SCD41
WHERE:
CONTROL: GROUP BY ([$__from, $__to), 30s, 5m)
```

For a quick connection test:

```text
SELECT: co2
FROM: root.devdb.i483.sensors.s2410431.SCD41
WHERE:
CONTROL: LIMIT 10
```

## If A Query Returns No Data

First check whether the time series exists:

```sql
SHOW TIMESERIES root.devdb.i483.sensors.s2410431.**
```

For Task 2(c), check analytics specifically:

```sql
SHOW TIMESERIES root.devdb.i483.sensors.s2410431.analytics.**
```

If analytics series do not exist in IoTDB, run `kafka_to_iotdb.py` to bridge
your Kafka analytics topics into IoTDB. If they already exist, no bridge is
needed.
