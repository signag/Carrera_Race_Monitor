"""Carrera Race Monitor Server Module
    This module provides the server-side functionality for the Carrera Race Monitor application.
"""
import os
from pathlib import Path
import gettext
import select
from unittest import case
import paho.mqtt.client as mqtt
from collections import deque
import json
import signal
import threading
import sys
import time
from i18n import _, set_language
from crm_device_manager import DeviceManager, Traffic_Light_crm, Sensor_crm, LCD_crm
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
        self._lng = "en"
        self._tracks = None
        self._instantiated_tracks = []
        self._start_control = False
        self._race_mode = "OPEN"
        self._race_time_min = 5
        self._race_laps = 10

        # Get configuration
        self.config = self.get_config()

        if "config" in self.config:
            self.lng = self.config["config"].get("lng", "en")
            self.tracks = self.config["config"].get("tracks", {"Track_1": True, "Track_2": True})
            self.start_control = self.config["config"].get("start_control", False)
            self.race_mode = self.config["config"].get("race_mode", "OPEN")
            self.race_time = self.config["config"].get("race_time_min", 5)
            self.race_laps = self.config["config"].get("race_laps", 10)

        # Initialize the devices
        self.device_manager = DeviceManager(self.config["devices"])

        self.restart()

    @property
    def lng(self) -> str:
        return self._lng
    
    @lng.setter
    def lng(self, value: str):
        self._lng = value
        set_language(self._lng)

    @property
    def tracks(self) -> dict:
        return self._tracks

    @tracks.setter
    def tracks(self, value: dict):
        self._tracks = value

    @property
    def start_control(self) -> bool:
        return self._start_control

    @start_control.setter
    def start_control(self, value: bool):
        self._start_control = value

    @property
    def race_mode(self) -> str:
        return self._race_mode

    @race_mode.setter
    def race_mode(self, value: str):
        self._race_mode = value

    @property
    def race_time_min(self) -> int:
        return self._race_time_min

    @race_time_min.setter
    def race_time_min(self, value: int):
        self._race_time_min = value

    @property
    def race_laps(self) -> int:
        return self._race_laps

    @race_laps.setter
    def race_laps(self, value: int):
        self._race_laps = value

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

    def restart(self):
      """Restart a race with the previous configuration

      """
      logger.debug("Race_Monitor.restart Entry")

      # Show race information on the LCD
      lcd = self.device_manager.lcd_circuit
      lcd.clear()
      lcd.write_to_position(1, 0, _("RACE"))
      lcd.write_to_position(1, 4, ":")
      if self.race_mode == "OPEN":
          lcd.write_to_position(1, 5, _("OPEN"))
      elif self.race_mode == "LAPS":
          lcd.write_to_position(1, 5, _("LAPS"))
          lcd.write_to_position(1, 11, str(self.race_laps))
      elif self.race_mode == "TIME":
          lcd.write_to_position(1, 5, _("TIME"))
          lcd.write_to_position(1, 11, str(self.race_time_min))
      else:
          lcd.write_to_position(1, 5, _("???"))

      # Set up tracks
      self._instantiated_tracks = []
      for track_name, enabled in self.tracks.items():
          track = Track(name=track_name, 
                        enabled=enabled, 
                        start_control=self.start_control,
                        trl=self.device_manager.get_traffic_light(track_name),
                        sns=self.device_manager.get_sensor(track_name),
                        lcd=self.device_manager.get_lcd(track_name)
                        )
          self._instantiated_tracks.append(track)
          if enabled:
              if self.start_control:
                  track.status = "LINEUP"
              else:
                  track.status = "ACTIVE"

    def terminate(self):
        """Terminate the race and reset all tracks."""
        logger.debug("Race_Monitor.terminate Entry")
        for track in self._instantiated_tracks:
            track.enabled = False
            track.status = "INACTIVE"

        lcd = self.device_manager.lcd_circuit
        lcd.clear()
        lcd.off()

class Track:
    def __init__(self, 
                 name: str, 
                 enabled: bool = True,
                 start_control: bool = False,
                 trl: Traffic_Light_crm = None,
                 sns: Sensor_crm = None,
                 lcd: LCD_crm = None
                 ):
        self._name = name
        self._enabled = enabled
        self._lcd = lcd
        self._trl = trl
        self._sns = sns
        self._laps = 0
        self._start = None
        self._lap_start = None
        self._total_time = 0.0
        self._best_lap = 0
        self._best_lap_time = 0.0
        self._current_lap_time = 0.0
        self._start_control = start_control
        self._status = "UNKNOWN"

        if self.enabled == False:
            self.sns.register_Car_cleared_callback(self.ignore_car_cleared)
            self.sns.register_Car_detected_callback(self.ignore_car_detected)
            self.trl.turn_off()

    @property
    def name(self) -> str:
        return self._name

    @name.setter
    def name(self, value: str):
        self._name = value

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool):
        self._enabled = value

    @property
    def lcd(self) -> LCD_crm:
        return self._lcd

    @lcd.setter
    def lcd(self, value: LCD_crm):
        self._lcd = value

    @property
    def trl(self) -> Traffic_Light_crm:
        return self._trl

    @trl.setter
    def trl(self, value: Traffic_Light_crm):
        self._trl = value

    @property
    def sns(self) -> Sensor_crm:
        return self._sns

    @sns.setter
    def sns(self, value: Sensor_crm):
        self._sns = value

    @property
    def laps(self) -> int:
        return self._laps

    @laps.setter
    def laps(self, value: int):
        self._laps = value

    @property
    def start(self) -> float:
        return self._start

    @start.setter
    def start(self, value: float):
        self._start = value

    @property
    def lap_start(self) -> float:
        return self._lap_start

    @lap_start.setter
    def lap_start(self, value: float):
        self._lap_start = value

    @property
    def current_lap_time(self) -> float:
        return self._current_lap_time

    @current_lap_time.setter
    def current_lap_time(self, value: float):
        self._current_lap_time = value

    @property
    def total_time(self) -> float:
        return self._total_time

    @total_time.setter
    def total_time(self, value: float):
        self._total_time = value

    @property
    def best_lap(self) -> int:
        return self._best_lap

    @best_lap.setter
    def best_lap(self, value: int):
        self._best_lap = value

    @property
    def best_lap_time(self) -> float:
        return self._best_lap_time

    @best_lap_time.setter
    def best_lap_time(self, value: float):
        self._best_lap_time = value

    @property
    def status(self) -> str:
        return self._status

    @status.setter
    def status(self, value: str):
        """Manage the status of the track.

        This method handles the track status according to the track state chart
        """
        match value:
            case "INACTIVE":
                self._status = "INACTIVE"
                self.sns.register_Car_cleared_callback(self.ignore_car_cleared)
                self.sns.register_Car_detected_callback(self.ignore_car_detected)
                self.trl.turn_off()
                self.lcd.clear()
                self.lcd.off()
            case "LINEUP":
                self._status = "LINEUP"
                self.sns.register_Car_cleared_callback(self.LINEUP_handle_car_cleared)
                self.sns.register_Car_detected_callback(self.LINEUP_handle_car_detected)
                self.trl.turn_off()
            case "READY":
                self._status = "READY"
                self.sns.register_Car_cleared_callback(self.READY_handle_car_cleared)
                self.sns.register_Car_detected_callback(self.READY_handle_car_detected)
                self.trl.turn_off()
            case "START_RED":
                self._status = "START_RED"
                self.sns.register_Car_cleared_callback(self.START_RED_handle_car_cleared)
                self.sns.register_Car_detected_callback(self.START_RED_handle_car_detected)
                self.trl.set_red()
            case "START_YELLOW":
                self._status = "START_YELLOW"
                self.sns.register_Car_cleared_callback(self.START_YELLOW_handle_car_cleared)
                self.sns.register_Car_detected_callback(self.START_YELLOW_handle_car_detected)
                self.trl.set_yellow()
            case "START_GREEN":
                self._status = "START_GREEN"
                self.sns.register_Car_cleared_callback(self.START_GREEN_handle_car_cleared)
                self.sns.register_Car_detected_callback(self.START_GREEN_handle_car_detected)
                self.trl.set_green()
            case "ACTIVE":
                self._status = "ACTIVE"
                self.sns.register_Car_cleared_callback(self.ACTIVE_handle_car_cleared)
                self.sns.register_Car_detected_callback(self.ACTIVE_handle_car_detected)
                self.trl.set_green()
                self.lcd.clear()
                self.lcd.write_to_position(0,0,_("LAP"))
                self.lcd.write_to_position(0,4,":")
                self.lcd.write_to_position(0,8,_("TIME"))
                self.lcd.write_to_position(0,12,":")
                self.lcd.write_to_position(1,0,_("BEST"))
                self.lcd.write_to_position(1,4,":")
            case "FALSE_START":
                self._status = "FALSE_START"
                self.sns.register_Car_cleared_callback(self.ignore_car_cleared)
                self.sns.register_Car_detected_callback(self.ignore_car_detected)
                self.trl.alarm()
            case "RACE_END":
                self._status = "RACE_END"
                self.sns.register_Car_cleared_callback(self.ignore_car_cleared)
                self.sns.register_Car_detected_callback(self.ignore_car_detected)
                self.trl.turn_off()

    def ignore_car_detected(self):
        pass

    def ignore_car_cleared(self):
        pass

    def LINEUP_handle_car_detected(self):
        self.status = "READY"

    def LINEUP_handle_car_cleared(self):
        self.status = "LINEUP"

    def READY_handle_car_detected(self):
        pass

    def READY_handle_car_cleared(self):
        self.status = "LINEUP"

    def START_RED_handle_car_detected(self):
        pass

    def START_RED_handle_car_cleared(self):
        self.status = "FALSE_START"

    def START_YELLOW_handle_car_detected(self):
        pass

    def START_YELLOW_handle_car_cleared(self):
        self.status = "FALSE_START"

    def START_GREEN_handle_car_detected(self):
        pass

    def START_GREEN_handle_car_cleared(self):
        self.status = "ACTIVE"

    def ACTIVE_handle_car_detected(self):
        """Handle car detection within an active race

           Increment the lap count and determine the best lap
        """
        if self.lap_start is None:
            self.lap_start = time.time()
            self.start = time.time()
            self.laps = 0
            self.total_time = 0.0
            self.current_lap_time = 0.0
        else:
            self.laps += 1
            self.current_lap_time = time.time() - self.lap_start
            if self.best_lap_time == 0.0 or self.current_lap_time < self.best_lap_time:
                self.best_lap_time = self.current_lap_time
                self.best_lap = self.laps
            self.total_time = time.time() - self.start
            self.lap_start = time.time()
            self.lcd.write_to_position(0,5,f"{self.laps:2d}")
            self.lcd.write_to_position(1,5,f"{self.best_lap:2d}")
            self.lcd.write_to_position(0,13,f"{int(self.total_time):3d}")
            self.lcd.write_to_position(1,11,f"{self.best_lap_time:5.1f}")

    def ACTIVE_handle_car_cleared(self):
        pass

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
    race_monitor.terminate()
    client.disconnect()   # 👈 stops loop_forever
    sys.exit(0)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)    

    logger.debug("Starting Carrera Race Monitor server")
    #
    # Instantiate the Race Monitor
    #
    race_monitor = Race_Monitor()
    #
    # Start MQTT client loop
    #
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.on_connect = on_connect
    client.on_message = on_message

    client.connect("localhost", 1883)
    client.loop_forever()    
