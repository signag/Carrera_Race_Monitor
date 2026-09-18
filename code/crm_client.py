"""Carrera Race Monitor Client Module
This module provides the client-side functionality for the Carrera Race Monitor application.
"""
import paho.mqtt.client as mqtt
from flask import Flask, render_template
from flask_socketio import SocketIO, emit
import paho.mqtt.client as mqtt
from flask_cors import CORS
import logging
from flask.logging import default_handler
import json
import os
from pathlib import Path

app = Flask(__name__)
socketio = SocketIO(app)
CORS(app)

HOMEDIR = os.getcwd()

#
# Logging configuration
#
logsPath = os.path.join(HOMEDIR, "logs")
os.makedirs(logsPath, exist_ok=True)
logFile = os.path.join(logsPath, "crm.log")
Path(logFile).touch(exist_ok=True)
filehandler = logging.FileHandler(logFile)
filehandler.setFormatter(app.logger.handlers[0].formatter)
logger = app.logger
logger.setLevel(logging.ERROR)
logger.addHandler(filehandler)
#
# Set up messaging client
#
client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

def on_connect(client, userdata, flags, reason_code, properties):
    """Handle MQTT connect

    Args:
        client (mqtt.Client): The MQTT client instance.
        userdata (any): The private user data as set in Client() or userdata_set().
        flags (dict): Response flags sent by the broker.
        reason_code (int): The reason code for the connection.
        properties (mqtt.Properties): The properties of the MQTT message.
    """
    logger.debug("Connected with reason code: %s", reason_code)
    client.subscribe("race_monitor/response")
    logger.debug("Subscribed to topic: race_monitor/response")

def on_message(client, userdata, msg):
    """Process MQTT message from crm_server

    Args:
        client (mqtt.Client): The MQTT client instance.
        userdata (any): The private user data as set in Client() or userdata_set().
        msg (mqtt.MQTTMessage): An instance of MQTTMessage, which contains topic, payload, qos, retain.
    """
    data = json.loads(msg.payload.decode())
    logger.debug("Received MQTT message: %s", data)
    status = data.get("status")
    received = data.get("received")
    message = data.get("message")
    if "params" in data:
        logger.debug("Received robot params: %s", data["params"])
        params = data.get("params", {})
    else:
        message = ""
    socketio.emit("message_update", {"status": status, "message": message})

client.on_connect = on_connect
client.on_message = on_message
client.connect("localhost", 1883)
client.loop_start()


@app.route("/")
def index():
    return render_template("index.html")

if __name__ == "__main__":
    logger.debug("Starting Carrera Race Monitor client")
    app.run(host="0.0.0.0", port=5100, debug=False)
