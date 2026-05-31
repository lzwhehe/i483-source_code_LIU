"""
I483 課題3 - Task 1 configuration.

Values below are filled in from your 課題2 source code
(esp32/main.py + pc/kafka_processor.py, student LIU ZHUOWEN / s2410431).

Kafka topics used by the supplementary Kadai 3 instructions:

  input stream : i483-allsensors
  output stream: i483-fvtt
  output value : i483-sensors-<STUDENT>-analytics-<STUDENT>_<SENSOR>_<min|max|avg>-<DATA_TYPE>,<VALUE>

  - STUDENT  : student id with a leading lowercase 's' (s2410431)
  - SENSOR   : uppercase sensor name (SCD41, BH1750, RPR0521, DPS310)
  - DATA_TYPE: lowercase (temperature, humidity, co2, air_pressure,
               illumination, infrared_illumination)
"""

# ---------------------------------------------------------------------------
# 1) WHO + WHERE
# ---------------------------------------------------------------------------
STUDENT = "s2410431"                      # from 課題2 source (LIU ZHUOWEN)
KAFKA_BOOTSTRAP = "150.65.230.59:9092"    # confirmed in 課題2 kafka_processor.py
CONSUMER_GROUP = f"{STUDENT}-task1-analytics"
ALLSENSORS_TOPIC = "i483-allsensors"
FVTT_TOPIC = "i483-fvtt"

# ---------------------------------------------------------------------------
# 2) WINDOWING (fixed by the assignment)
#    "30秒ごとに計算し、毎回最近の5分間のデータを利用する"
#    -> sliding event-time window: size = 5 min, slide = 30 s.
#    Your ESP32 publishes every 15 s, so a 5-min window holds ~20 samples.
# ---------------------------------------------------------------------------
WINDOW_SIZE_SECONDS = 5 * 60     # 300
WINDOW_SLIDE_SECONDS = 30
MAX_OUT_OF_ORDERNESS_SECONDS = 5 # watermark slack for late Kafka records

# ---------------------------------------------------------------------------
# 3) YOUR PRIMARY SENSORS  (課題2 項目2a)
#    These are exactly the 6 streams your ESP32 publishes (esp32/main.py),
#    so this list already satisfies 項目1(b) "all primary sensors".
#    For 項目1(a) alone, you could keep just one entry (e.g. SCD41/co2).
# ---------------------------------------------------------------------------
SENSORS = [
    # (SENSOR_UPPERCASE, DATA_TYPE_lowercase)
    ("SCD41",   "co2"),
    ("SCD41",   "temperature"),
    ("SCD41",   "humidity"),
    ("BH1750",  "illumination"),
    ("RPR0521", "infrared_illumination"),
    ("DPS310",  "air_pressure"),
]

# Aggregations to publish.  Spec requires min, max, avg.
AGGREGATIONS = ("min", "max", "avg")

# Decimal places for the published String value.
VALUE_DECIMALS = 3

# Print computed values to the terminal as well as publishing them to Kafka.
# Useful for local testing and demos.
PRINT_RESULTS_TO_CONSOLE = True


# ---------------------------------------------------------------------------
# Derived helpers -- do not edit.
# ---------------------------------------------------------------------------
def input_topic(sensor: str, data_type: str) -> str:
    return f"i483-sensors-{STUDENT}-{sensor}-{data_type}"


def output_topic(sensor: str, agg: str, data_type: str) -> str:
    # i483-sensors-<STUDENT>-analytics-<STUDENT>_<SENSOR>_<agg>-<DATA_TYPE>
    return f"i483-sensors-{STUDENT}-analytics-{STUDENT}_{sensor}_{agg}-{data_type}"


INPUT_TOPICS = {input_topic(sensor, data_type) for sensor, data_type in SENSORS}
