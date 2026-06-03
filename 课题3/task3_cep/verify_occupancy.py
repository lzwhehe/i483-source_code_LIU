"""Read this student's Task 3 occupancy messages back from i483-fvtt."""

import argparse
import datetime as dt
import time

from kafka import KafkaConsumer

import config


EXPECTED_TOPICS = {
    config.output_topic("occupancy"),
    config.output_topic("occupancy_score"),
    config.output_topic("occupancy_reason_code"),
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seconds", type=int, default=120)
    parser.add_argument("--from-beginning", action="store_true")
    args = parser.parse_args()

    consumer = KafkaConsumer(
        config.FVTT_TOPIC,
        bootstrap_servers=config.KAFKA_BOOTSTRAP,
        group_id=f"{config.STUDENT}-verify-occupancy-{int(time.time())}",
        auto_offset_reset="earliest" if args.from_beginning else "latest",
        enable_auto_commit=False,
        value_deserializer=lambda b: b.decode("utf-8", errors="replace"),
        consumer_timeout_ms=1000,
    )

    deadline = time.monotonic() + args.seconds
    count = 0
    try:
        while time.monotonic() < deadline:
            for message in consumer:
                if "," not in message.value:
                    continue
                topic, value = [part.strip() for part in message.value.split(",", 1)]
                if topic not in EXPECTED_TOPICS:
                    continue
                count += 1
                ts = dt.datetime.fromtimestamp(
                    message.timestamp / 1000, tz=dt.timezone.utc
                ).astimezone()
                print(f"{ts:%Y-%m-%d %H:%M:%S} | {topic} | value={value}")
                if time.monotonic() >= deadline:
                    break
    finally:
        consumer.close()

    print(f"Received {count} occupancy message(s).")


if __name__ == "__main__":
    main()
