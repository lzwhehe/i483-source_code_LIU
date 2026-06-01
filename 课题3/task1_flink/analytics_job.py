"""
I483 Kadai 3 - Task 1(a)(b) Stream Analytics with Apache Flink / PyFlink.

This follows the supplementary Kadai 3 slides:
  1. consume the shared Kafka topic i483-allsensors
  2. validate records formatted as topic,timestamp,value
  3. validate sensor topics and process all students' sensor records by default
  4. key by the original sensor topic
  5. compute min / max / avg with a 5-minute sliding processing-time window
     that emits every 30 seconds
  6. publish every result to i483-fvtt as topic,value
"""

import re
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
    r"^i483-sensors-(?P<student>s[0-9]+)-(?P<sensor>[A-Z0-9]+)-(?P<data_type>[a-z0-9_]+)$"
)


def configure_environment(env):
    """Load local connector JARs needed by the PyFlink Kafka source/sink."""
    if KAFKA_CONNECTOR_JAR.exists():
        env.add_jars(KAFKA_CONNECTOR_JAR.as_uri())
    else:
        raise FileNotFoundError(
            f"Kafka connector JAR not found: {KAFKA_CONNECTOR_JAR}. "
            "Run setup_env.ps1 to download it."
        )


def _fmt(value: float) -> str:
    return f"{value:.{config.VALUE_DECIMALS}f}"


def parse_allsensors_record(record: str):
    """Validate i483-allsensors records and emit (topic, timestamp_ms, value)."""
    parts = [part.strip() for part in record.split(",", 2)]
    if len(parts) != 3:
        return []

    topic, timestamp_text, value_text = parts
    parsed_topic = parse_sensor_topic(topic)
    if parsed_topic is None:
        return []

    if not config.PROCESS_ALL_STUDENTS and topic not in config.INPUT_TOPICS:
        return []

    try:
        timestamp_ms = int(timestamp_text)
        value = float(value_text)
    except ValueError:
        return []

    return [(topic, timestamp_ms, value)]


def parse_sensor_topic(topic: str):
    match = SENSOR_TOPIC_RE.match(topic)
    if match is None:
        return None

    student = match.group("student")
    sensor = match.group("sensor")
    data_type = match.group("data_type")
    if data_type not in config.ALLOWED_DATA_TYPES:
        return None

    return student, sensor, data_type


class EmitMinMaxAvg(ProcessWindowFunction):
    def process(self, key, context, elements):
        values = [float(row[2]) for row in elements]
        if not values:
            return []

        parsed = parse_sensor_topic(str(key))
        if parsed is None:
            return []
        student, sensor, data_type = parsed

        stats = {
            "min": min(values),
            "max": max(values),
            "avg": sum(values) / len(values),
        }

        output = []
        for agg in config.AGGREGATIONS:
            topic = config.output_topic(sensor, agg, data_type, student=student)
            output.append(f"{topic},{_fmt(stats[agg])}")
        return output


def build_pipeline(env):
    """Wire i483-allsensors -> windowed analytics -> i483-fvtt."""
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
            output_type=Types.TUPLE([Types.STRING(), Types.LONG(), Types.FLOAT()]),
        )
        .key_by(lambda row: row[0], key_type=Types.STRING())
        .window(
            SlidingProcessingTimeWindows.of(
                Time.seconds(config.WINDOW_SIZE_SECONDS),
                Time.seconds(config.WINDOW_SLIDE_SECONDS),
            )
        )
        .process(EmitMinMaxAvg(), output_type=Types.STRING())
    )

    if config.PRINT_RESULTS_TO_CONSOLE:
        results.print("fvtt")

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

    if not config.SENSORS:
        raise SystemExit("config.SENSORS is empty -- list your primary sensors.")

    build_pipeline(env)
    env.execute(f"{config.STUDENT}-task1-allsensors-to-fvtt")


if __name__ == "__main__":
    main()
