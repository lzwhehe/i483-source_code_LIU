"""
Read back Task 1 analytics results from Kafka.

Run this in a second terminal while analytics_job.py is running:
  python verify_analytics_topics.py
"""

from __future__ import annotations

import argparse
import datetime as dt
import time

from kafka import KafkaConsumer

import config


def analytics_topics() -> list[str]:
    return [
        config.output_topic(sensor, agg, data_type)
        for sensor, data_type in config.SENSORS
        for agg in config.AGGREGATIONS
    ]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Subscribe to Task 1 analytics Kafka topics and print received values."
    )
    parser.add_argument(
        "--seconds",
        type=int,
        default=120,
        help="How long to listen before exiting. Use 0 to listen forever.",
    )
    parser.add_argument(
        "--from-beginning",
        action="store_true",
        help="Read existing messages from the beginning instead of only new messages.",
    )
    args = parser.parse_args()

    topics = analytics_topics()
    print("Subscribing to analytics topics:")
    for topic in topics:
        print(f"  {topic}")

    consumer = KafkaConsumer(
        *topics,
        bootstrap_servers=config.KAFKA_BOOTSTRAP,
        group_id=f"{config.STUDENT}-verify-analytics-{int(time.time())}",
        auto_offset_reset="earliest" if args.from_beginning else "latest",
        enable_auto_commit=False,
        value_deserializer=lambda b: b.decode("utf-8", errors="replace"),
        consumer_timeout_ms=1000,
    )

    print()
    print("Waiting for analytics messages...")
    if not args.from_beginning:
        print("Tip: keep run_task1.ps1 running in another terminal so new results are produced.")
    print()

    deadline = None if args.seconds == 0 else time.monotonic() + args.seconds
    received = 0

    try:
        while deadline is None or time.monotonic() < deadline:
            for message in consumer:
                received += 1
                timestamp = dt.datetime.fromtimestamp(
                    message.timestamp / 1000, tz=dt.timezone.utc
                ).astimezone()
                print(
                    f"{timestamp:%Y-%m-%d %H:%M:%S} | "
                    f"{message.topic} | partition={message.partition} "
                    f"offset={message.offset} | value={message.value}"
                )
                if deadline is not None and time.monotonic() >= deadline:
                    break
    except KeyboardInterrupt:
        print()
        print("Stopped by user.")
    finally:
        consumer.close()

    print()
    print(f"Received {received} analytics message(s).")


if __name__ == "__main__":
    main()
