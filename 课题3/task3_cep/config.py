"""
Kadai 3 Task 3 configuration.

The CEP job detects whether a room appears occupied by combining multiple
sensor changes instead of relying on one slow sensor alone.
"""

STUDENT = "s2410431"
KAFKA_BOOTSTRAP = "150.65.230.59:9092"
CONSUMER_GROUP = f"{STUDENT}-task3-occupancy"
ALLSENSORS_TOPIC = "i483-allsensors"
FVTT_TOPIC = "i483-fvtt"

# A short window reacts faster than the 5-minute analytics window.
WINDOW_SIZE_SECONDS = 60
WINDOW_SLIDE_SECONDS = 10

VALUE_DECIMALS = 3
PRINT_RESULTS_TO_CONSOLE = True

SENSORS = {
    ("SCD41", "co2"),
    ("SCD41", "temperature"),
    ("SCD41", "humidity"),
    ("BH1750", "illumination"),
    ("RPR0521", "infrared_illumination"),
    ("DPS310", "air_pressure"),
}


def input_topic(sensor: str, data_type: str) -> str:
    return f"i483-sensors-{STUDENT}-{sensor}-{data_type}"


INPUT_TOPICS = {input_topic(sensor, data_type) for sensor, data_type in SENSORS}


def output_topic(data_type: str) -> str:
    # Written to i483-fvtt as topic,value so the instructor connector can ingest it.
    return f"i483-sensors-{STUDENT}-CEP-{data_type}"
