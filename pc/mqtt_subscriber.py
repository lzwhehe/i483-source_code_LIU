import paho.mqtt.client as mqtt
import datetime

BROKER_HOST = "150.65.230.59"
BROKER_PORT = 1883
STUDENT_ID  = "s2410431"
TOPIC       = f"i483/sensors/{STUDENT_ID}/#"

def on_connect(client, userdata, flags, reason_code, properties):
    print(f"[MQTT] Connected: {reason_code}")
    client.subscribe(TOPIC)
    print(f"[MQTT] Subscribed to: {TOPIC}")

def on_message(client, userdata, msg):
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    value = msg.payload.decode("utf-8")
    print(f"[{ts}] {msg.topic} = {value}")

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.on_connect = on_connect
client.on_message = on_message

client.connect(BROKER_HOST, BROKER_PORT, keepalive=60)
client.loop_forever()
