import time
import collections
from kafka import KafkaConsumer, KafkaProducer

KAFKA_BROKER  = "150.65.230.59:9092"
STUDENT_ID    = "s2410431"

TOPIC_LIGHT   = f"i483-sensors-{STUDENT_ID}-BH1750-illumination"
TOPIC_CO2     = f"i483-sensors-{STUDENT_ID}-SCD41-co2"
TOPIC_AVG     = f"i483-sensors-{STUDENT_ID}-BH1750_avg-illumination"
TOPIC_CO2_TH  = f"i483-actuators-{STUDENT_ID}-co2_threshold_crossed"

CO2_THRESHOLD = 700.0
AVG_INTERVAL  = 30      # seconds
WINDOW_SIZE   = 20      # 5分 ÷ 15秒 = 20サンプル

light_buf: collections.deque = collections.deque(maxlen=WINDOW_SIZE)
co2_above: bool | None = None
last_avg_time: float = time.time()

consumer = KafkaConsumer(
    TOPIC_LIGHT,
    TOPIC_CO2,
    bootstrap_servers=KAFKA_BROKER,
    auto_offset_reset="latest",
    value_deserializer=lambda v: v.decode("utf-8"),
)

producer = KafkaProducer(
    bootstrap_servers=KAFKA_BROKER,
    value_serializer=lambda v: v.encode("utf-8"),
)

print(f"[Kafka] Listening on {TOPIC_LIGHT} and {TOPIC_CO2}")

for msg in consumer:
    topic = msg.topic
    value = msg.value.strip()

    # --- BH1750 照度：Rolling Average ---
    if topic == TOPIC_LIGHT:
        try:
            light_buf.append(float(value))
        except ValueError:
            continue

        now = time.time()
        if now - last_avg_time >= AVG_INTERVAL and light_buf:
            avg = sum(light_buf) / len(light_buf)
            result = f"{avg:.2f}"
            producer.send(TOPIC_AVG, value=result)
            producer.flush()
            last_avg_time = now
            print(f"[AVG] {TOPIC_AVG} = {result}  (n={len(light_buf)})")

    # --- SCD41 CO2：Threshold Detection ---
    elif topic == TOPIC_CO2:
        try:
            co2 = float(value)
        except ValueError:
            continue

        now_above = co2 > CO2_THRESHOLD

        if now_above != co2_above:
            message = "yes" if now_above else "no"
            producer.send(TOPIC_CO2_TH, value=message)
            producer.flush()
            co2_above = now_above
            print(f"[TH]  CO2={co2:.2f} ppm → publish '{message}' to {TOPIC_CO2_TH}")
        else:
            print(f"[TH]  CO2={co2:.2f} ppm (no change, threshold={'exceeded' if co2_above else 'normal'})")
