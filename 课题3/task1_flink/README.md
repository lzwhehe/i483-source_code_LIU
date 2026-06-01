# Kadai 3 Task 1 - Stream Analytics with PyFlink

Author: LIU ZHUOWEN / s2410431

This job computes `min / max / avg` for every primary sensor and follows the
supplementary Kadai 3 instructions from the lecture slides:

```text
input  Kafka topic: i483-allsensors
output Kafka topic: i483-fvtt
input  value format: original_topic,timestamp,value
output value format: analytics_topic,value
```

Example output message written to `i483-fvtt`:

```text
i483-sensors-s2410431-analytics-s2410431_SCD41_avg-co2,488.600
```

The instructor's Kafka-IoTDB connector can then map this `topic,value` message
into IoTDB for Grafana visualization.

## What It Does

- Reads `i483-allsensors`.
- Validates each record so malformed messages are ignored instead of crashing
  the Flink job.
- Processes every valid student sensor record seen in `i483-allsensors` by
  default. The output topic keeps the student id from the input topic, so
  another student's data is written under that student's analytics topic.
- Your primary sensor topics are:
  - `SCD41/co2`
  - `SCD41/temperature`
  - `SCD41/humidity`
  - `BH1750/illumination`
  - `RPR0521/infrared_illumination`
  - `DPS310/air_pressure`
- Uses a sliding processing-time window:
  - window size: 5 minutes
  - slide: 30 seconds
- Writes three results per sensor stream:
  - min
  - max
  - avg

## Setup

On Windows PowerShell:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\setup_env.ps1
```

The setup script creates `.venv`, installs dependencies, downloads JDK 11, and
downloads the Flink Kafka connector JAR.

## Run

```powershell
.\run_task1.ps1
```

This is a streaming job, so it keeps running until you press `Ctrl + C`.

## Verify Output

Open a second PowerShell window while the Flink job is running. The verification
script filters `i483-fvtt` and prints this student's analytics messages:

```powershell
.\verify_analytics_topics.ps1 --seconds 120
```

To read older `i483-fvtt` messages too:

```powershell
.\verify_analytics_topics.ps1 --seconds 30 --from-beginning
```

You should see messages such as:

```text
i483-sensors-s2410431-analytics-s2410431_SCD41_avg-co2 | value=488.600
```

## Source Files

- `analytics_job.py`: PyFlink streaming job.
- `config.py`: student id, Kafka broker, sensors, window settings.
- `verify_analytics_topics.py`: reads back matching analytics messages from
  `i483-fvtt`.
