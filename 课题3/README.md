# I483 Kadai 3

Author: LIU ZHUOWEN / s2410431

## Contents

- `task1_flink/`: Stream analytics with Apache Flink / PyFlink.
  It reads the raw sensor Kafka topics, computes min / max / avg every 30
  seconds over the latest 5 minutes, and publishes the results to the required
  analytics Kafka topics.
- `task2_grafana/`: Notes and IoTDB queries for the Grafana visualization tasks.

## Task 1 Quick Start

```powershell
cd task1_flink
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\setup_env.ps1
.\run_task1.ps1
```

To verify that analytics messages are written back to Kafka:

```powershell
.\verify_analytics_topics.ps1 --seconds 120
```
