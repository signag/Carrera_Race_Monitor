"""Carrera Race Monitor Server Module
This module provides the server-side functionality for the Carrera Race Monitor application.
"""
import os
from pathlib import Path
import gettext
import paho.mqtt.client as mqtt
from collections import deque
import json
import signal
import threading
import sys
import time
from i18n import _, set_language
from crm_device_manager import DeviceManager
import logging

HOMEDIR = os.getcwd()

#
# Logging configuration
#
logsPath = os.path.join(HOMEDIR, "logs")
os.makedirs(logsPath, exist_ok=True)
logFile = os.path.join(logsPath, "crm.log")
Path(logFile).touch(exist_ok=True)
filehandler = logging.FileHandler(logFile)
filehandler.setFormatter(logging.Formatter('[%(asctime)s] %(levelname)s in %(name)s: %(message)s'))
streamhandler = logging.StreamHandler()
streamhandler.setFormatter(logging.Formatter('[%(asctime)s] %(levelname)s in %(name)s: %(message)s'))

logger = logging.getLogger("crm_server")
logger.addHandler(streamhandler)
logger.addHandler(filehandler)
logger.setLevel(logging.DEBUG)

class Race_Monitor:
    def __init__(self):
        self.tracks = None

        # Get configuration
        self.config = self.get_config()

        # Initialize the devices
        self.device_manager = DeviceManager(self.config["devices"])

    def get_config(self) -> dict:
        """Get the race monitor configuration.

        Search for the configuration in the file crm_config.json successively in 
        the current directory, ../config or HOME/.config

        Returns:
            dict: The current race monitor configuration.
        """
        logger.debug("get_config Entry")

        config_file = ""
        curDir = os.path.dirname(os.path.realpath(__file__))
        if os.path.exists(os.path.join(curDir, "crm_config.json")):
            config_file = os.path.join(curDir, "crm_config.json")
        else:
            curDir = os.path.dirname(curDir)
            if os.path.exists(os.path.join(curDir, "config/crm_config.json")):
                config_file = os.path.join(curDir, "config/crm_config.json")
            else:
                if os.path.exists(os.path.join(os.getenv("HOME"), ".config", "crm_config.json")):
                    config_file = os.path.join(os.getenv("HOME"), ".config", "crm_config.json")
                else:
                    raise FileNotFoundError("Configuration file crm_config.json not found.")
        logger.debug("get_config - config_file: %s", config_file)

        with open(config_file, "r") as f:
            content = json.load(f)

            if "devices" in content:
                return content
            else:
                raise KeyError("The configuration file does not contain 'devices' key.")


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
    client.subscribe("race_monitor/request")
    logger.debug("Subscribed to topic: race_monitor/request")


def on_message(client, userdata, msg):
    """Message event handler

    Args:
        client (mqtt.Client): The MQTT client instance.
        userdata (any): The private user data as set in Client() or userdata_set().
        msg (mqtt.MQTTMessage): An instance of MQTTMessage, which contains topic, payload, qos, retain.
    """
    global bb_robot
    data = json.loads(msg.payload.decode())
    logger.debug("Received: %s", data)

    method = data.get("method")
    params = data.get("params", {})

    response = {
        "status": "error",
        "received": data,
        "message": "Invalid method"
    }
    if method == "get_state":
        response["status"] = "success"
        response["message"] = ""


def shutdown(sig, frame):
    logger.debug("Shutting down...")
    global shutdown
    client.disconnect()   # 👈 stops loop_forever
    sys.exit(0)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)    

    logger.debug("Starting Carrera Race Monitor server")
    #
    # Instantiate the robot
    #
    circuit = Race_Monitor()
    #
    # Start MQTT client loop
    #
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.on_connect = on_connect
    client.on_message = on_message

    client.connect("localhost", 1883)
    client.loop_forever()    
