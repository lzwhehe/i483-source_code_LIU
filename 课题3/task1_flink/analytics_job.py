"""
I483 課題3 - 項目1(a)(b)  Stream Analytics with Apache Flink (PyFlink)

For every primary sensor listed in config.SENSORS this job:
  1. consumes the raw String values from  i483-sensors-<STUDENT>-<SENSOR>-<DATA_TYPE>
  2. computes min / max / avg over a sliding event-time window
     (size = 5 min, slide = 30 s  -> a result every 30 s covering the last 5 min)
  3. publishes each statistic, as a String, to
       i483-sensors-<STUDENT>-analytics-<STUDENT>_<SENSOR>_<min|max|avg>-<DATA_TYPE>

Because the whole sensor set is driven from config.py, the SAME code covers
  - 1(a): keep one (sensor, data_type) in config.SENSORS
  - 1(b): list every primary sensor you operate

Run:
  python analytics_job.py
(see README.md for cluster submission / required JARs)
"""

from pyflink.common import Types, WatermarkStrategy, Duration, Time
from pyflink.common.serialization import SimpleStringSchema
from pyflink.datastream import StreamExecutionEnvironment, RuntimeExecutionMode
from pyflink.datastream.connectors.kafka import (
    KafkaSource,
    KafkaOffsetsInitializer,
    KafkaSink,
    KafkaRecordSerializationSchema,
    DeliveryGuarantee,
)
from pyflink.datastream.functions import AggregateFunction
from pyflink.datastream.window import SlidingEventTimeWindows

from pathlib import Path

import config


PROJECT_ROOT = Path(__file__).resolve().parent
KAFKA_CONNECTOR_JAR = PROJECT_ROOT / ".tools" / "jars" / "flink-sql-connector-kafka-3.0.2-1.18.jar"


def configure_environment(env):
    """Load local connector JARs needed by the PyFlink Kafka source/sink."""
    if KAFKA_CONNECTOR_JAR.exists():
        env.add_jars(KAFKA_CONNECTOR_JAR.as_uri())
    else:
        raise FileNotFoundError(
            f"Kafka connector JAR not found: {KAFKA_CONNECTOR_JAR}. "
            "Download flink-sql-connector-kafka-3.0.2-1.18.jar into .tools/jars."
        )


# --------------------------------------------------------------------------- #
# Aggregate: keep (min, max, sum, count) incrementally, emit (min, max, avg).  #
# --------------------------------------------------------------------------- #
class MinMaxAvg(AggregateFunction):
    def create_accumulator(self):
        # min, max, sum, count
        return (float("inf"), float("-inf"), 0.0, 0)

    def add(self, value, acc):
        mn, mx, s, c = acc
        try:
            v = float(value)
        except (TypeError, ValueError):
            # ignore non-numeric / malformed payloads
            return acc
        return (min(mn, v), max(mx, v), s + v, c + 1)

    def get_result(self, acc):
        mn, mx, s, c = acc
        if c == 0:
            return (None, None, None)
        return (mn, mx, s / c)

    def merge(self, a, b):
        return (min(a[0], b[0]), max(a[1], b[1]), a[2] + b[2], a[3] + b[3])


def _fmt(v) -> str:
    return f"{v:.{config.VALUE_DECIMALS}f}"


def build_branch(env, sensor: str, data_type: str):
    """Wire one full source -> window -> 3 sinks pipeline for one sensor stream."""
    in_topic = config.input_topic(sensor, data_type)

    source = (
        KafkaSource.builder()
        .set_bootstrap_servers(config.KAFKA_BOOTSTRAP)
        .set_topics(in_topic)
        .set_group_id(config.CONSUMER_GROUP)
        .set_starting_offsets(KafkaOffsetsInitializer.latest())
        .set_value_only_deserializer(SimpleStringSchema())
        .build()
    )

    # Use the Kafka record timestamp as event time (payload is just a value).
    wm = WatermarkStrategy.for_bounded_out_of_orderness(
        Duration.of_seconds(config.MAX_OUT_OF_ORDERNESS_SECONDS)
    )

    stream = env.from_source(source, wm, f"src-{sensor}-{data_type}")

    # Single logical stream -> key by a constant so we can use a keyed window.
    results = (
        stream.key_by(lambda _v: f"{sensor}:{data_type}", key_type=Types.STRING())
        .window(
            SlidingEventTimeWindows.of(
                Time.seconds(config.WINDOW_SIZE_SECONDS),
                Time.seconds(config.WINDOW_SLIDE_SECONDS),
            )
        )
        .aggregate(
            MinMaxAvg(),
            output_type=Types.TUPLE(
                [Types.FLOAT(), Types.FLOAT(), Types.FLOAT()]
            ),
        )
    )

    # One sink per aggregation, each to its own fixed topic (no dynamic routing).
    agg_index = {"min": 0, "max": 1, "avg": 2}
    for agg in config.AGGREGATIONS:
        idx = agg_index[agg]
        out_topic = config.output_topic(sensor, agg, data_type)

        values = (
            results.filter(lambda r: r[0] is not None)
            .map(lambda r, i=idx: _fmt(r[i]), output_type=Types.STRING())
        )

        if config.PRINT_RESULTS_TO_CONSOLE:
            values.print(f"{agg}-{sensor}-{data_type}")

        sink = (
            KafkaSink.builder()
            .set_bootstrap_servers(config.KAFKA_BOOTSTRAP)
            .set_record_serializer(
                KafkaRecordSerializationSchema.builder()
                .set_topic(out_topic)
                .set_value_serialization_schema(SimpleStringSchema())
                .build()
            )
            .set_delivery_guarantee(DeliveryGuarantee.AT_LEAST_ONCE)
            .build()
        )
        values.sink_to(sink).name(f"sink-{agg}-{sensor}-{data_type}")


def main():
    env = StreamExecutionEnvironment.get_execution_environment()
    env.set_runtime_mode(RuntimeExecutionMode.STREAMING)
    env.set_parallelism(1)
    configure_environment(env)

    if not config.SENSORS:
        raise SystemExit("config.SENSORS is empty -- list your primary sensors.")

    for sensor, data_type in config.SENSORS:
        build_branch(env, sensor, data_type)

    env.execute(f"{config.STUDENT}-task1-min-max-avg")


if __name__ == "__main__":
    main()
