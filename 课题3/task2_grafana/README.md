# 課題3 項目2 — Visualization (instructor-hosted Grafana)

The instructor runs the Grafana + IoTDB stack. You do **not** install anything —
you just log in and build panels.

- Grafana: **http://150.65.230.59:3000**
- Example dashboard URL: `http://150.65.230.59:3000/d/adqgh75/s2410431`
  (each student has their own dashboard named after their id — open/create the
  one for **your** student number, e.g. `.../s2410431`).
- The **IoTDB data source is already configured** by the instructor, so just
  pick it when adding a panel.

## What to build

| Panel | Spec | Series in IoTDB | Aggregation by |
|-------|------|------------------|----------------|
| 2(a) | 課題2-1a raw | `root.i483.<S>.<SENSOR>.<dtype>` | none (raw) |
| 2(b) | 課題2-1c rolling average **only** | rolling-avg measurement | upstream (課題2-1c) |
| 2(c) | 課題3-1a analytics | `root.i483.<S>.analytics.<SENSOR>_<agg>_<dtype>` | **Flink** (項目1) |
| 2(d) | 課題2-1a via IoTDB aggregation | `root.i483.<S>.<SENSOR>.<dtype>` + `GROUP BY` | **IoTDB** (server-side) |

Use the queries in `iotdb_queries.sql` (replace `s2410431` and `SCD41/co2`).

Steps:

1. Open your dashboard (or **New dashboard → Add panel**).
2. Set the data source to the existing **IoTDB** source.
3. 2(a): plot the raw measurement, no GROUP BY.
4. 2(b): plot ONLY the rolling-average measurement from 課題2-1c.
5. 2(c): one panel, three queries (min / max / avg) so the band shows.
6. 2(d): same raw measurement as 2(a) but `GROUP BY ([$__from,$__to), 30s, 5m)`
   so IoTDB does the 5-min/30-s average itself (mirrors the Flink job).

## Does the analytics data (2c) already appear?

The instructor's infrastructure likely ingests **all** `i483-...` topics into
IoTDB automatically — including the analytics topics your Flink job (項目1)
produces. So first just **check IoTDB** for
`root.i483.<S>.analytics.<SENSOR>_avg_<dtype>`:

```sql
SHOW TIMESERIES root.i483.<S>.analytics.**
```

- If it exists → query it directly in panel 2(c). No bridge needed.
- If it does **not** → run `kafka_to_iotdb.py` (set `INGEST_ANALYTICS=True`,
  `INGEST_RAW=False`) to land your analytics topics into IoTDB yourself.

```bash
pip install kafka-python apache-iotdb
# edit the CONFIG block (STUDENT, KAFKA_BOOTSTRAP, IOTDB_HOST=150.65.230.59 ...)
python kafka_to_iotdb.py
```

> Note: the IoTDB host for the bridge is the instructor's server
> (`150.65.230.59`), and you need its IoTDB port/credentials. If the instructor
> already ingests everything, you can ignore the bridge entirely.
