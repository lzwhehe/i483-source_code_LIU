"""
Kadai 3 Task 3(b) - Occupancy detection with PyFlink.

Input:
  i483-allsensors records formatted as original_topic,timestamp,value

Output to i483-fvtt:
  i483-sensors-s2410431-CEP-occupancy,<0 or 1>
  i483-sensors-s2410431-CEP-occupancy_score,<score>

The detector is intentionally multi-sensor and fast:
  - CO2 absolute level and short-term increase
  - illumination and infrared changes
  - humidity / temperature / pressure changes

This is more responsive than waiting for CO2 alone, which can lag when the room
or sensor position makes CO2 changes slow.
"""

import re
from collections import defaultdict
from pathlib import Path

from pyflink.common import Time, Types, WatermarkStrategy
from pyflink.common.serialization import SimpleStringSchema
from pyflink.datastream import RuntimeExecutionMode, StreamExecutionEnvironment
from pyflink.datastream.connectors.kafka import (
    DeliveryGuarantee,
    KafkaOffsetsInitializer,
    KafkaRecordSerializationSchema,
    KafkaSink,
    KafkaSource,
)
from pyflink.datastream.functions import ProcessWindowFunction
from pyflink.datastream.window import SlidingProcessingTimeWindows

import config


PROJECT_ROOT = Path(__file__).resolve().parent
KAFKA_CONNECTOR_JAR = (
    PROJECT_ROOT / ".tools" / "jars" / "flink-sql-connector-kafka-3.0.2-1.18.jar"
)
SENSOR_TOPIC_RE = re.compile(
    rf"^i483-sensors-{config.STUDENT}-(?P<sensor>[A-Z0-9]+)-(?P<data_type>[a-z0-9_]+)$"
)


def configure_environment(env):
    if KAFKA_CONNECTOR_JAR.exists():
        env.add_jars(KAFKA_CONNECTOR_JAR.as_uri())
    else:
        raise FileNotFoundError(
            f"Kafka connector JAR not found: {KAFKA_CONNECTOR_JAR}. "
            "Run setup_env.ps1 to download it."
        )


def parse_allsensors_record(record: str):
    parts = [part.strip() for part in record.split(",", 2)]
    if len(parts) != 3:
        return []

    topic, timestamp_text, value_text = parts
    match = SENSOR_TOPIC_RE.match(topic)
    if match is None:
        return []

    sensor = match.group("sensor")
    data_type = match.group("data_type")
    if (sensor, data_type) not in config.SENSORS:
        return []

    try:
        timestamp_ms = int(timestamp_text)
        value = float(value_text)
    except ValueError:
        return []

    return [(sensor, data_type, timestamp_ms, value)]


def _span(values):
    if len(values) < 2:
        return 0.0
    ordered = sorted(values, key=lambda row: row[0])
    return ordered[-1][1] - ordered[0][1]


def _latest(values):
    if not values:
        return None
    return sorted(values, key=lambda row: row[0])[-1][1]


def _abs_span(values):
    return abs(_span(values))


def score_occupancy(by_type):
    co2_latest = _latest(by_type["co2"])
    co2_rise = _span(by_type["co2"])
    illumination_change = _abs_span(by_type["illumination"])
    infrared_change = _abs_span(by_type["infrared_illumination"])
    humidity_change = _abs_span(by_type["humidity"])
    temperature_change = _abs_span(by_type["temperature"])
    pressure_change = _abs_span(by_type["air_pressure"])

    score = 0.0
    reasons = []

    if co2_latest is not None:
        if co2_latest >= 700:
            score += 0.35
            reasons.append("co2_high")
        elif co2_latest >= 550:
            score += 0.15
            reasons.append("co2_medium")

    if co2_rise >= 15:
        score += 0.35
        reasons.append("co2_rising_fast")
    elif co2_rise >= 8:
        score += 0.20
        reasons.append("co2_rising")

    if illumination_change >= 20:
        score += 0.20
        reasons.append("light_changed")
    elif illumination_change >= 8:
        score += 0.10
        reasons.append("light_changed_small")

    if infrared_change >= 20:
        score += 0.15
        reasons.append("infrared_changed")
    elif infrared_change >= 8:
        score += 0.08
        reasons.append("infrared_changed_small")

    if humidity_change >= 0.30:
        score += 0.10
        reasons.append("humidity_changed")

    if temperature_change >= 0.08:
        score += 0.08
        reasons.append("temperature_changed")

    if pressure_change >= 0.04:
        score += 0.04
        reasons.append("pressure_changed")

    return min(score, 1.0), reasons


class OccupancyWindow(ProcessWindowFunction):
    def process(self, key, context, elements):
        by_type = defaultdict(list)
        for sensor, data_type, timestamp_ms, value in elements:
            by_type[data_type].append((timestamp_ms, value))

        score, reasons = score_occupancy(by_type)
        occupied = 1 if score >= 0.35 else 0

        score_topic = config.output_topic("occupancy_score")
        occupancy_topic = config.output_topic("occupancy")

        outputs = [
            f"{score_topic},{score:.{config.VALUE_DECIMALS}f}",
            f"{occupancy_topic},{occupied}",
        ]

        if reasons:
            reason_topic = config.output_topic("occupancy_reason_code")
            # Numeric reason code keeps the payload parseable by IoTDB.
            outputs.append(f"{reason_topic},{len(reasons)}")

        return outputs


def build_pipeline(env):
    source = (
        KafkaSource.builder()
        .set_bootstrap_servers(config.KAFKA_BOOTSTRAP)
        .set_topics(config.ALLSENSORS_TOPIC)
        .set_group_id(config.CONSUMER_GROUP)
        .set_starting_offsets(KafkaOffsetsInitializer.latest())
        .set_value_only_deserializer(SimpleStringSchema())
        .build()
    )

    stream = env.from_source(
        source,
        watermark_strategy=WatermarkStrategy.no_watermarks(),
        source_name=f"src-{config.ALLSENSORS_TOPIC}",
    )

    results = (
        stream.flat_map(
            parse_allsensors_record,
            output_type=Types.TUPLE(
                [Types.STRING(), Types.STRING(), Types.LONG(), Types.FLOAT()]
            ),
        )
        .key_by(lambda _row: config.STUDENT, key_type=Types.STRING())
        .window(
            SlidingProcessingTimeWindows.of(
                Time.seconds(config.WINDOW_SIZE_SECONDS),
                Time.seconds(config.WINDOW_SLIDE_SECONDS),
            )
        )
        .process(OccupancyWindow(), output_type=Types.STRING())
    )

    if config.PRINT_RESULTS_TO_CONSOLE:
        results.print("cep")

    sink = (
        KafkaSink.builder()
        .set_bootstrap_servers(config.KAFKA_BOOTSTRAP)
        .set_record_serializer(
            KafkaRecordSerializationSchema.builder()
            .set_topic(config.FVTT_TOPIC)
            .set_value_serialization_schema(SimpleStringSchema())
            .build()
        )
        .set_delivery_guarantee(DeliveryGuarantee.AT_LEAST_ONCE)
        .build()
    )
    results.sink_to(sink).name(f"sink-{config.FVTT_TOPIC}")


def main():
    env = StreamExecutionEnvironment.get_execution_environment()
    env.set_runtime_mode(RuntimeExecutionMode.STREAMING)
    env.set_parallelism(1)
    configure_environment(env)
    build_pipeline(env)
    env.execute(f"{config.STUDENT}-task3-occupancy")


if __name__ == "__main__":
    main()
