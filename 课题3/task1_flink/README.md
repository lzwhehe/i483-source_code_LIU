# 課題3 項目1 — Stream Analytics (Apache Flink / PyFlink)

Computes **min / max / avg** for every primary sensor and republishes them to
the analytics topics defined by the assignment.

## What it does

| Spec item | Covered by |
|-----------|-----------|
| 1(a) one sensor, min/max/avg every 30 s over the last 5 min | one entry in `config.SENSORS` |
| 1(b) apply to **all** primary sensors (課題2 項目2a) | the full `config.SENSORS` list |

- Window = sliding event-time window, **size 5 min, slide 30 s** → a fresh
  min/max/avg every 30 s, each covering the most recent 5 minutes.
- Payload format = **String** (the numeric value, formatted to `VALUE_DECIMALS`).
- Topics follow the spec exactly:
  - input  `i483-sensors-<STUDENT>-<SENSOR>-<DATA_TYPE>`
  - output `i483-sensors-<STUDENT>-analytics-<STUDENT>_<SENSOR>_<min|max|avg>-<DATA_TYPE>`

## 1. Configure

Edit **`config.py`** only:

- `STUDENT` — your id with a leading lowercase `s` (e.g. `s1234567`).
- `KAFKA_BOOTSTRAP` — the I483 Kafka broker `host:port`.
- `SENSORS` — list every `(SENSOR, data_type)` you operate. Keep one for 1(a),
  list all of them for 1(b).

`SENSOR` is **uppercase** (SCD41, BH1750…); `data_type` is **lowercase**
(temperature, humidity, co2, air_pressure, illumination, infrared_illumination).

## 2. Install

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt        # apache-flink 1.18.x (bundles PyFlink)
```

On Windows PowerShell, this repository also includes a setup script that creates
the virtual environment, downloads a local JDK 11, and downloads the Flink Kafka
connector JAR used by `analytics_job.py`:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\setup_env.ps1
```

PyFlink 1.18 already bundles the Kafka connector JAR
(`flink-sql-connector-kafka`). If your Flink build does not, download the
matching `flink-sql-connector-kafka-<ver>.jar` and add it with
`env.add_jars("file:///abs/path/flink-sql-connector-kafka-....jar")` at the top
of `main()`.

## 3. Run

Local (mini-cluster, simplest for the demo):

```bash
python analytics_job.py
```

On Windows PowerShell after running `setup_env.ps1`:

```powershell
.\run_task1.ps1
```

On an existing Flink cluster:

```bash
$FLINK_HOME/bin/flink run -py analytics_job.py -pyfs config.py
```

## 4. Verify the output topics

```bash
# list the analytics topics that appeared
kafka-topics.sh --bootstrap-server <BROKER> --list | grep "analytics"

# watch one statistic stream
kafka-console-consumer.sh --bootstrap-server <BROKER> \
  --topic i483-sensors-<STUDENT>-analytics-<STUDENT>_SCD41_avg-co2
```

You should see a new value roughly every 30 s on each `min`/`max`/`avg` topic.

## 5. Submission (提出方法 項目1)

The assignment asks you to **email the instructor how to obtain the source
code**. Put this folder in your course git repo and send the clone URL, e.g.:

```
git clone <your-repo-url>
cd <repo>/task1_flink
# configure config.py, then: python analytics_job.py
```

## Notes / design choices

- Event time comes from the **Kafka record timestamp**, with a 5 s
  out-of-orderness watermark, so late sensor messages are still counted.
- One independent source→window→sink branch is built per `(sensor, data_type)`.
  This keeps each statistic on a fixed output topic (no dynamic topic routing)
  and makes 1(a)→1(b) purely a config change.
- Apache Beam is also allowed by the spec for 1(a)/1(b); this PyFlink version is
  the reference implementation.
