"""
I483 課題3 項目2 helper — land Kafka topics into Apache IoTDB so Grafana can
plot them.

Why this exists:
  - 2(a) raw 課題2-1a series and 2(c) 課題3-1a analytics series live in Kafka.
  - Grafana's IoTDB datasource reads time series from IoTDB.
  => This consumer subscribes to the relevant topics and writes each String
     value as a point in IoTDB.

If your 課題2 already stores raw data in IoTDB (項目2c/2d), you only need this
for the NEW analytics topics produced in 課題3 項目1. Set RAW=False in that case.

IoTDB path layout (one measurement per series):
  raw      : root.i483.<STUDENT>.<SENSOR>.<DATA_TYPE>
  analytics: root.i483.<STUDENT>.analytics.<SENSOR>_<agg>_<DATA_TYPE>
"""

import re
import time

from kafka import KafkaConsumer
from iotdb.Session import Session

# --------------------------- CONFIG (edit me) ------------------------------ #
STUDENT = "s2410431"
KAFKA_BOOTSTRAP = "150.65.230.59:9092"
IOTDB_HOST = "127.0.0.1"
IOTDB_PORT = 6667
IOTDB_USER = "root"
IOTDB_PASSWORD = "root"

INGEST_RAW = True        # also store the raw 課題2-1a topics (for panel 2a/2d)
INGEST_ANALYTICS = True  # store the 課題3-1a analytics topics (for panel 2c)
# --------------------------------------------------------------------------- #

RAW_RE = re.compile(rf"^i483-sensors-{STUDENT}-(?P<sensor>[^-]+)-(?P<dtype>[^-]+)$")
ANALYTICS_RE = re.compile(
    rf"^i483-sensors-{STUDENT}-analytics-{STUDENT}_(?P<sensor>[^_]+)_"
    rf"(?P<agg>min|max|avg)-(?P<dtype>.+)$"
)


def device_and_measurement(topic: str):
    """Map a topic name to (iotdb_device_path, measurement)."""
    m = ANALYTICS_RE.match(topic)
    if m:
        dev = f"root.i483.{STUDENT}.analytics"
        meas = f"{m['sensor']}_{m['agg']}_{m['dtype']}"
        return dev, meas
    m = RAW_RE.match(topic)
    if m and m["sensor"] != "analytics":
        dev = f"root.i483.{STUDENT}.{m['sensor']}"
        meas = m["dtype"]
        return dev, meas
    return None, None


def subscribe_pattern():
    pats = []
    if INGEST_RAW:
        pats.append(rf"i483-sensors-{STUDENT}-[A-Z0-9]+-[a-z_]+")
    if INGEST_ANALYTICS:
        pats.append(rf"i483-sensors-{STUDENT}-analytics-.*")
    return "(" + ")|(".join(pats) + ")"


def main():
    session = Session(IOTDB_HOST, IOTDB_PORT, IOTDB_USER, IOTDB_PASSWORD)
    session.open(False)

    consumer = KafkaConsumer(
        bootstrap_servers=KAFKA_BOOTSTRAP,
        group_id=f"{STUDENT}-iotdb-sink",
        auto_offset_reset="latest",
        value_deserializer=lambda b: b.decode("utf-8", errors="ignore"),
    )
    consumer.subscribe(pattern=subscribe_pattern())
    print("subscribed:", subscribe_pattern())

    try:
        for msg in consumer:
            dev, meas = device_and_measurement(msg.topic)
            if dev is None:
                continue
            try:
                value = float(msg.value)
            except (TypeError, ValueError):
                continue
            ts = msg.timestamp if msg.timestamp and msg.timestamp > 0 else int(time.time() * 1000)
            # insert one float point
            session.insert_record(dev, ts, [meas], ["DOUBLE"], [value])
    finally:
        consumer.close()
        session.close()


if __name__ == "__main__":
    main()
