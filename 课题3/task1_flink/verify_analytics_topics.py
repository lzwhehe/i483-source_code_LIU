"""
Read back Task 1 analytics results from i483-fvtt.

Run this in a second terminal while analytics_job.py is running:
  python verify_analytics_topics.py
"""

from __future__ import annotations

import argparse
import datetime as dt
import time

from kafka import KafkaConsumer

import config


def expected_output_topics() -> set[str]:
    return {
        config.output_topic(sensor, agg, data_type)
        for sensor, data_type in config.SENSORS
        for agg in config.AGGREGATIONS
    }


def parse_fvtt_value(value: str):
    parts = [part.strip() for part in value.split(",", 1)]
    if len(parts) != 2:
        return None
    topic, numeric_text = parts
    try:
        float(numeric_text)
    except ValueError:
        return None
    return topic, numeric_text


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Subscribe to i483-fvtt and print this student's analytics values."
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

    wanted = expected_output_topics()
    consumer = KafkaConsumer(
        config.FVTT_TOPIC,
        bootstrap_servers=config.KAFKA_BOOTSTRAP,
        group_id=f"{config.STUDENT}-verify-fvtt-{int(time.time())}",
        auto_offset_reset="earliest" if args.from_beginning else "latest",
        enable_auto_commit=False,
        value_deserializer=lambda b: b.decode("utf-8", errors="replace"),
        consumer_timeout_ms=1000,
    )

    print(f"Subscribing to {config.FVTT_TOPIC}")
    print("Waiting for this student's analytics messages...")
    print()

    deadline = None if args.seconds == 0 else time.monotonic() + args.seconds
    received = 0

    try:
        while deadline is None or time.monotonic() < deadline:
            for message in consumer:
                parsed = parse_fvtt_value(message.value)
                if parsed is None:
                    continue
                output_topic, value = parsed
                if output_topic not in wanted:
                    continue

                received += 1
                timestamp = dt.datetime.fromtimestamp(
                    message.timestamp / 1000, tz=dt.timezone.utc
                ).astimezone()
                print(
                    f"{timestamp:%Y-%m-%d %H:%M:%S} | "
                    f"{output_topic} | value={value} | "
                    f"offset={message.offset}"
                )
                if deadline is not None and time.monotonic() >= deadline:
                    break
    except KeyboardInterrupt:
        print()
        print("Stopped by user.")
    finally:
        consumer.close()

    print()
    print(f"Received {received} matching analytics message(s) from {config.FVTT_TOPIC}.")


if __name__ == "__main__":
    main()
