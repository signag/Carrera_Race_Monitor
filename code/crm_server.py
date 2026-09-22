"""Carrera Race Monitor Server Module
    This module provides the server-side functionality for the Carrera Race Monitor application.
"""
import os
from pathlib import Path
import paho.mqtt.client as mqtt
import json
import signal
import threading
import sys
import time
import datetime
from i18n import _, set_language
from babel import Locale
from babel.numbers import format_decimal
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
        logger.debug("Race_Monitor.__init__ Entry")
        self._device_manager = None
        self._lng = "en"
        self._tracks = None
        self._instantiated_tracks = []
        self._start_control = False
        self._race_mode = "OPEN"
        self._race_time_min = 5
        self._race_laps = 10
        self._last_reset_press_time = None
        self._current_setup_step = None
        self._save_config = False
        self._handicap = 0.0
        self.languages = self.supported_languages

        # Get configuration
        self.config = self.get_config()

        if "config" in self.config:
            self.lng = self.config["config"].get("lng", "en")
            self.tracks = self.config["config"].get("tracks", 
                                                    {"Track_1": {
                                                        "enabled": True,
                                                        "handicap": 0.0
                                                    },
                                                     "Track_2": {
                                                        "enabled": True,
                                                        "handicap": 0.0
                                                     }})
            self.start_control = self.config["config"].get("start_control", False)
            self.race_mode = self.config["config"].get("race_mode", "OPEN")
            self.race_time = self.config["config"].get("race_time_min", 5)
            self.race_laps = self.config["config"].get("race_laps", 10)

        self.lng_index = self.languages.index(self._lng) if self._lng in self.languages else 0

        # Check if tracks are instantiated
        if self._tracks is None or len(self._tracks) < 1:
            logger.error("No tracks are defined in configuration.")
            raise ValueError("No tracks are defined in configuration.")

        # Initialize the devices
        self.device_manager = DeviceManager(self.config["devices"])

        # Translate modes
        self._modes = {
            "OPEN": _("OPEN    "),
            "LAPS": _("LAPS    "),
            "TIME": _("TIME    ")
        }
        logger.debug("Race_Monitor.__init__ - lng=%s", self._lng)
        logger.debug("Race_Monitor.__init__ - _modes=%s", self._modes)

        self.restart()

    @property
    def device_manager(self) -> DeviceManager:
        return self._device_manager

    @device_manager.setter
    def device_manager(self, value: DeviceManager):
        self._device_manager = value

    @property
    def lng(self) -> str:
        return self._lng
    
    @lng.setter
    def lng(self, value: str):
        self._lng = value
        set_language(self._lng)

    @property
    def supported_languages(self) -> list:
        """Return a list of supported languages

        The list is determined from the list of direct subdirectories in the languages folder.

        Returns:
            list: supported languages
        """
        languages_dir = os.path.join(os.path.dirname(__file__), "locales")
        lngs = [name for name in os.listdir(languages_dir) if os.path.isdir(os.path.join(languages_dir, name))]
        if not "en" in lngs:
            lngs.append("en")
        return lngs
    
    @property
    def tracks(self) -> dict:
        return self._tracks

    @tracks.setter
    def tracks(self, value: dict):
        self._tracks = value

    @property
    def enabled_tracks_count(self) -> int:
        count = 0
        for track in self._tracks.values():
            if track.get("enabled", False):
                count += 1
        return count

    @property
    def handicap(self) -> float:
        return self._handicap

    @handicap.setter
    def handicap(self, value: float):
        """Set the handicap

        Args:
            value (float): handicap in seconds
                           < 0.0 for first track
                           > 0.0 for second track
        """
        self._handicap = value
        if len(self._instantiated_tracks) > 1:
            trk1 = self._instantiated_tracks[0]
            trk2 = self._instantiated_tracks[1]
            if value < 0.0:
                trk1.handicap = abs(value)
                trk2.handicap = 0.0
            elif value > 0.0:
                trk2.handicap = abs(value)
                trk1.handicap = 0.0
            elif value == 0.0:
                trk1.handicap = 0.0
                trk2.handicap = 0.0

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

    @property
    def last_reset_press_time(self) -> float:
        return self._last_reset_press_time

    @last_reset_press_time.setter
    def last_reset_press_time(self, value: float):
        self._last_reset_press_time = value

    @property
    def current_setup_step(self) -> str:
        return self._current_setup_step

    @current_setup_step.setter
    def current_setup_step(self, value: str):
        self._current_setup_step = value

    def get_config(self) -> dict:
        """Get the race monitor configuration.

        Search for the configuration in the file crm_config.json successively in 
        the current directory, ../config or HOME/.config

        Returns:
            dict: The current race monitor configuration.
        """
        logger.debug("Race_Monitor.get_config Entry")

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

    def ignore_button_pressed(self):
        logger.debug("Race_Monitor.ignore_button_pressed Entry")
        pass

    def reset_button_pressed(self):
        """Handle a reset button press event

        This will terminate an active race and reset all tracks

        If the time from a previous press is > 2 seconds, the setup mode will be entered.
        Otherwise, the system will remain in the "off" state with only the
        reset an restart buttons active
        """
        logger.debug("Race_Monitor.reset_button_pressed Entry with last_reset_press_time: %s", self.last_reset_press_time)

        self.cleanup()
        if self.last_reset_press_time is None or (time.time() - self.last_reset_press_time) > 2:
            # Enter setup mode
            self.enter_setup_mode()
        self.last_reset_press_time = time.time()

    def restart_button_pressed(self):
        logger.debug("Race_Monitor.restart_button_pressed Entry")
        self.restart()

    def start_button_pressed(self):
        logger.debug("Race_Monitor.start_button_pressed Entry")
        pass

    def selector_button_pressed(self):
        logger.debug("Race_Monitor.selector_button_pressed Entry")
        self.next_setup_step()

    def selector_turned_left(self):
        logger.debug("Race_Monitor.selector_turned_left Entry")
        lcd = self.device_manager.lcd_circuit
        if self.current_setup_step == "TRACKS":
            if len(self._instantiated_tracks) == 0:
                self.show_selected_tracks()
            t1 = self._instantiated_tracks[0]
            if len(self.tracks) == 2:
                t2 = self._instantiated_tracks[1]
                if t1.enabled == True:
                    if t2.enabled == False:
                        t1.enabled = False
                        t2.enabled = True
                    else:
                        t2.enabled = False
                else:
                    t1.enabled = True
                    t2.enabled = True
            else:
                if t1.enabled == False:
                    t1.enabled = True
                else:
                    t1.enabled = False
            for track in self._instantiated_tracks:
                name = track.name
                enabled = track.enabled
                self.tracks[name]["enabled"] = enabled
                logger.debug("Race_Monitor.selector_turned_left - Track %s - Enabled: %s", name, enabled)
            self.show_selected_tracks()
        elif self.current_setup_step == "RCMODE":
            if self.race_mode == "OPEN":
                self.race_mode = "TIME"
            elif self.race_mode == "LAPS":
                self.race_mode = "OPEN"
            elif self.race_mode == "TIME":
                self.race_mode = "LAPS"
            lcd.write_to_position(1, 0, " " * 16)
            lcd.write_to_position(1, 0, self._modes[self.race_mode])
            if self.race_mode == "TIME":
                lcd.write_to_position(1, 9, f"{self.race_time:3d}")
                lcd.write_to_position(1, 13, _("min"))
            elif self.race_mode == "LAPS":
                lcd.write_to_position(1, 9, f"{self.race_laps:3d}")
        elif self.current_setup_step == "MODDAT":
            if self.race_mode == "TIME":
                self.race_time -= 1
                lcd.write_to_position(1, 9, f"{self.race_time:3d}")
                lcd.write_to_position(1, 13, _("min"))
            elif self.race_mode == "LAPS":
                self.race_laps -= 1
                lcd.write_to_position(1, 9, f"{self.race_laps:3d}")
        elif self.current_setup_step == "STARTC":
            if self.start_control == True:
                lcd.write_to_position(1, 0, _("DISABLED        "))
                self.start_control = False
            else:
                lcd.write_to_position(1, 0, _("ENABLED         "))
                self.start_control = True
        elif self.current_setup_step == "HANDIC":
            self.handicap -= 1.0
            for track in self._instantiated_tracks:
                track.show_setup()
        elif self.current_setup_step == "LANGUA":
            lcd.write_to_position(1, 0, " " * 16)
            self.lng_index = (self.lng_index - 1) % len(self.languages)
            self.lng = self.languages[self.lng_index]
            lcd.write_to_position(1, 0, Locale(self.lng).get_display_name(self.lng))
            set_language(self.lng)

    def selector_turned_right(self):
        logger.debug("Race_Monitor.selector_turned_right Entry")
        lcd = self.device_manager.lcd_circuit
        if self.current_setup_step == "TRACKS":
            if len(self._instantiated_tracks) == 0:
                self.show_selected_tracks()
            t1 = self._instantiated_tracks[0]
            if len(self.tracks) == 2:
                t2 = self._instantiated_tracks[1]
                if t1.enabled == True:
                    if t2.enabled == False:
                        t2.enabled = True
                    else:
                        t1.enabled = False
                        t2.enabled = True
                else:
                    t1.enabled = True
                    t2.enabled = False
            else:
                if t1.enabled == False:
                    t1.enabled = True
                else:
                    t1.enabled = False
            for track in self._instantiated_tracks:
                name = track.name
                enabled = track.enabled
                self.tracks[name]["enabled"] = enabled
                logger.debug("Race_Monitor.selector_turned_right - Track %s - Enabled: %s", name, enabled)
            self.show_selected_tracks()
        elif self.current_setup_step == "RCMODE":
            if self.race_mode == "OPEN":
                self.race_mode = "LAPS"
            elif self.race_mode == "LAPS":
                self.race_mode = "TIME"
            elif self.race_mode == "TIME":
                self.race_mode = "OPEN"
            lcd.write_to_position(1, 0, " " * 16)
            lcd.write_to_position(1, 0, self._modes[self.race_mode])
            if self.race_mode == "TIME":
                lcd.write_to_position(1, 9, f"{self.race_time:3d}")
                lcd.write_to_position(1, 13, _("min"))
            elif self.race_mode == "LAPS":
                lcd.write_to_position(1, 9, f"{self.race_laps:3d}")
        elif self.current_setup_step == "MODDAT":
            if self.race_mode == "TIME":
                self.race_time += 1
                lcd.write_to_position(1, 9, f"{self.race_time:3d}")
                lcd.write_to_position(1, 13, _("min"))
            elif self.race_mode == "LAPS":
                self.race_laps += 1
                lcd.write_to_position(1, 9, f"{self.race_laps:3d}")
        elif self.current_setup_step == "STARTC":
            if self.start_control == True:
                lcd.write_to_position(1, 0, _("DISABLED        "))
                self.start_control = False
            else:
                lcd.write_to_position(1, 0, _("ENABLED         "))
                self.start_control = True
        elif self.current_setup_step == "HANDIC":
            self.handicap += 1.0
            for track in self._instantiated_tracks:
                track.show_setup()
        elif self.current_setup_step == "LANGUA":
            lcd.write_to_position(1, 0, " " * 16)
            self.lng_index = (self.lng_index + 1) % len(self.languages)
            self.lng = self.languages[self.lng_index]
            lcd.write_to_position(1, 0, Locale(self.lng).get_display_name(self.lng))
            set_language(self.lng)

    def enter_setup_mode(self):
        """Enter the setup mode
        
        This will enter the setup mode for the race monitor.
        The sequence of the setup steps is:
        1. TRACKS : Configure tracks
        2. RCMODE : Set race mode and parameters
        3. MODDAT : Set mode-specific data (time or # of laps)
        4. STARTC : Enable/disable start control
        5. HANDIC : Set track handicaps
        6. LANGUA : Set language
        7. SAVCFG : Save configuration
        """
        logger.debug("Race_Monitor.enter_setup_mode Entry")

        self.current_setup_step = None
        self.cleanup()

        # Activate selector
        self.device_manager.register_Selector_Button_pressed_callback(self.selector_button_pressed)
        self.device_manager.register_Selector_rotated_clockwise_callback(self.selector_turned_right)
        self.device_manager.register_Selector_rotated_counter_clockwise_callback(self.selector_turned_left)

        # Set next (first) setup step
        self.next_setup_step()

    def next_setup_step(self):
        """Move to the next setup step"""
        logger.debug("Race_Monitor.next_setup_step: Entry - Current step: %s", self.current_setup_step)
        lcd = self.device_manager.lcd_circuit

        if self.current_setup_step is None:
            self.current_setup_step = "TRACKS"
            lcd.clear()
            lcd.write_to_position(0, 0, _("SELECT TRACKS   "))
            self.show_selected_tracks()
        elif self.current_setup_step == "TRACKS":
            lcd.clear()
            lcd.write_to_position(0, 0, _("SELECT MODE     "))
            lcd.write_to_position(1, 0, self._modes[self.race_mode])
            if self.race_mode == "TIME":
                lcd.write_to_position(1, 9, f"{self.race_time:3d}")
                lcd.write_to_position(1, 13, _("min"))
            elif self.race_mode == "LAPS":
                lcd.write_to_position(1, 9, f"{self.race_laps:3d}")
            self.current_setup_step = "RCMODE"
        elif self.current_setup_step == "RCMODE" \
         and self.race_mode in ["LAPS", "TIME"]:
            if self.race_mode == "TIME":
                lcd.write_to_position(0, 0, _("SELECT RACE TIME"))
            elif self.race_mode == "LAPS":
                lcd.write_to_position(0, 0, _("SELECT # LAPS   "))
            self.current_setup_step = "MODDAT"
        elif self.current_setup_step == "MODDAT" \
          or (self.current_setup_step == "RCMODE" and self.race_mode == "OPEN"):
            lcd.clear()
            lcd.write_to_position(0, 0, _("START-CONTROL   "))
            if self.start_control == True:
                lcd.write_to_position(1, 0, _("ENABLED         "))
            else:
                lcd.write_to_position(1, 0, _("DISABLED        "))
            self.current_setup_step = "STARTC"
        elif self.current_setup_step == "STARTC" \
         and self.start_control == True \
         and self.enabled_tracks_count > 1:
            lcd.clear()
            lcd.write_to_position(0, 0, _("SELECT HANDICAP "))
            lcd.write_to_position(1, 0, _("See Tracks      "))
            self.current_setup_step = "HANDIC"
        elif (self.current_setup_step == "HANDIC" \
          or (self.current_setup_step == "STARTC" and self.start_control == False) \
          or (self.current_setup_step == "STARTC" and self.enabled_tracks_count < 2) ) \
         and len(self.supported_languages) > 1: 
            lcd.clear()
            lcd.write_to_position(0, 0, _("SELECT LANGUAGE "))
            lcd.write_to_position(1, 0, Locale(self.lng).get_display_name(self.lng))
            self.current_setup_step = "LANGUA"
        elif self.current_setup_step == "LANGUA" :
            lcd.clear()
            lcd.write_to_position(0, 0, _("SAVE CONFIG     "))
            if self._save_config:
                lcd.write_to_position(1, 0, _("YES             "))
            else:
                lcd.write_to_position(1, 0, _("NO              "))
            self.current_setup_step = "SAVCFG"
        elif self.current_setup_step == "SAVCFG":
            lcd.clear()
            lcd.write_to_position(0, 0, _("SELECT TRACKS   "))
            self.show_selected_tracks()
            self.current_setup_step = "TRACKS"
        else:
            lcd.clear()
            lcd.write_to_position(0, 0, _("SELECT TRACKS   "))
            self.show_selected_tracks()
            self.current_setup_step = "TRACKS"
        logger.debug("Race_Monitor.next_setup_step: Exit - New step: %s", self.current_setup_step)

    def show_selected_tracks(self):
        """Display the selected tracks on the LCDs
        
        If a track is enabled, its display will be activated and setup information is shown
        In addition, enabled tracks are shown on the main LCD display.
        """
        logger.debug("Race_Monitor.show_selected_tracks Entry")
        # Set up tracks
        if len(self._instantiated_tracks) == 0:
            for track_name, tr_cfg in self.tracks.items():
                enabled = tr_cfg.get("enabled", True)
                handicap = tr_cfg.get("handicap", 0.0)
                track = Track(name=track_name, 
                                enabled=enabled,
                                handicap=handicap,
                                start_control=self.start_control,
                                trl=self.device_manager.get_traffic_light(track_name),
                                sns=self.device_manager.get_sensor(track_name),
                                lcd=self.device_manager.get_lcd(track_name),
                                lng=self.lng
                                )
                self._instantiated_tracks.append(track)

        lcd = self.device_manager.lcd_circuit
        ind = 0
        lcd.write_to_position(1, 0, " " * 16)
        for track in self._instantiated_tracks:
            track.show_setup()
            if track.enabled:
                lcd.write_to_position(1, ind, _("TRACK"))
                lcd.write_to_position(1, ind + 6, track.id)
            ind += 9

    def restart(self):
        """Restart a race with the previous configuration

        This will terminate a previous race and clean up all tracks 
        before restarting with the current configuration.

        Also, the setup mode will be terminated.
        """
        logger.debug("Race_Monitor.restart Entry")

        # Cleanup
        self.cleanup()
        self.current_setup_step = None

        # Set up tracks
        self._instantiated_tracks = []
        for track_name, tr_cfg in self.tracks.items():
            enabled = tr_cfg.get("enabled", True)
            handicap = tr_cfg.get("handicap", 0.0)
            track = Track(name=track_name, 
                            enabled=enabled, 
                            handicap=handicap,
                            start_control=self.start_control,
                            trl=self.device_manager.get_traffic_light(track_name),
                            sns=self.device_manager.get_sensor(track_name),
                            lcd=self.device_manager.get_lcd(track_name),
                            lng=self.lng
                            )
            self._instantiated_tracks.append(track)
            if enabled:
                if self.start_control:
                    track.status = "LINEUP"
                else:
                    track.status = "ACTIVE"

        # Show race information on the LCD
        lcd = self.device_manager.lcd_circuit
        if self.race_mode == "OPEN":
            lcd.write_to_position(0, 0, _("KEEP DRIVING    "))
        else:
            if self.start_control == True:
                if self.lineup_ok() == False:
                    lcd.write_to_position(0, 0, "LINEUP CARS     ")
                else:
                    lcd.write_to_position(0, 0, "PRESS START     ")
            else:
                lcd.write_to_position(0, 0, "START DRIVING   ")
        lcd.write_to_position(1, 0, _("RACE:  "))
        if self.race_mode == "OPEN":
            lcd.write_to_position(1, 7, _("OPEN     "))
        elif self.race_mode == "LAPS":
            lcd.write_to_position(1, 7, f"{self.race_laps:3d}")
            lcd.write_to_position(1, 11, _("LAPS "))
        elif self.race_mode == "TIME":
            lcd.write_to_position(1, 7, f"{self.race_time:3d}")
            lcd.write_to_position(1, 11, _("min "))
        else:
            lcd.write_to_position(1, 7, _("???"))

        # Activate required input devices
        self.device_manager.register_BTN_Reset_pressed_callback(self.reset_button_pressed)
        self.device_manager.register_BTN_Restart_pressed_callback(self.restart_button_pressed)
        if self.start_control == True:
            self.device_manager.register_BTN_Start_pressed_callback(self.start_button_pressed)

    def lineup_ok(self):
        """Check if all tracks are ready for the race."""
        logger.debug("Race_Monitor.lineup_ok Entry")
        for track in self._instantiated_tracks:
            if track.enabled and track.is_lined_up() == False:
                logger.debug("Race_Monitor.lineup_ok - Track %s is not lined up", track.name)
                return False
        logger.debug("Race_Monitor.lineup_ok - All tracks are lined up")
        return True

    def cleanup(self):
        """Cleanup the race monitor and all tracks.
        
            Deactivate all input devices and clean up all output devices
            Deactivate all tracks
        """
        logger.debug("Race_Monitor.cleanup Entry")

        # Ignore any general input devices
        self.device_manager.register_BTN_Reset_pressed_callback(self.ignore_button_pressed)
        self.device_manager.register_BTN_Restart_pressed_callback(self.ignore_button_pressed)
        self.device_manager.register_BTN_Start_pressed_callback(self.ignore_button_pressed)
        self.device_manager.register_Selector_Button_pressed_callback(self.ignore_button_pressed)
        self.device_manager.register_Selector_rotated_clockwise_callback(self.ignore_button_pressed)
        self.device_manager.register_Selector_rotated_counter_clockwise_callback(self.ignore_button_pressed)

        # Clean up all tracks
        for track in self._instantiated_tracks:
            track.enabled = False
            track.status = "INACTIVE"

        self._instantiated_tracks = []

        # Stop speaker
        spk = self.device_manager.speaker
        spk.off()

        # Clean up all LCDs
        lcd = self.device_manager.lcd_circuit
        lcd.clear()
        lcd.off()

        # Only active buttons are reset and restart
        self.device_manager.register_BTN_Reset_pressed_callback(self.reset_button_pressed)
        self.device_manager.register_BTN_Restart_pressed_callback(self.restart_button_pressed)


    def terminate(self):
        """Terminate the race and reset all tracks."""
        logger.debug("Race_Monitor.terminate Entry")

        self.cleanup()

        # Ignare reset button
        self.device_manager.register_BTN_Reset_pressed_callback(self.ignore_button_pressed)

class Track:
    def __init__(self, 
                 name: str, 
                 enabled: bool = True,
                 handicap: float = 0.0,
                 start_control: bool = False,
                 trl: Traffic_Light_crm = None,
                 sns: Sensor_crm = None,
                 lcd: LCD_crm = None,
                 lng: str = "en"
                 ):
        logger.debug("Track.__init__ Entry for track: %s", name)
        self._name = name
        self._enabled = enabled
        self._handicap = handicap
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
        self._lng = lng

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
    def id(self) -> str:
        """Return the track ID, which is the last character of its name"""
        return self._name[-1]

    @property
    def lng(self) -> str:
        return self._lng

    @lng.setter
    def lng(self, value: str):
        self._lng = value

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool):
        self._enabled = value

    @property
    def handicap(self) -> float:
        return self._handicap

    @handicap.setter
    def handicap(self, value: float):
        self._handicap = value

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
        logger.debug(f"Track.status setter Entry with value: {value}")
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
                self.lcd.clear()
                self.lcd.write_to_position(0,0,_("LINEUP CAR      "))
                self.lcd.write_to_position(1,0,("\x00" * 16))
            case "READY":
                self._status = "READY"
                self.sns.register_Car_cleared_callback(self.READY_handle_car_cleared)
                self.sns.register_Car_detected_callback(self.READY_handle_car_detected)
                self.lcd.clear()
                self.lcd.write_to_position(0,0,_("READY TO START  "))
            case "START_RED":
                self._status = "START_RED"
                self.sns.register_Car_cleared_callback(self.START_RED_handle_car_cleared)
                self.sns.register_Car_detected_callback(self.START_RED_handle_car_detected)
                self.trl.set_red()
                self.lcd.clear()
                self.lcd.write_to_position(0,0,_("WAIT FOR GREEN  "))
            case "START_YELLOW":
                self._status = "START_YELLOW"
                self.sns.register_Car_cleared_callback(self.START_YELLOW_handle_car_cleared)
                self.sns.register_Car_detected_callback(self.START_YELLOW_handle_car_detected)
                self.trl.set_yellow()
                self.lcd.clear()
                self.lcd.write_to_position(0,0,_("WAIT FOR GREEN  "))
            case "START_GREEN":
                self._status = "START_GREEN"
                self.sns.register_Car_cleared_callback(self.START_GREEN_handle_car_cleared)
                self.sns.register_Car_detected_callback(self.START_GREEN_handle_car_detected)
                self.trl.set_green()
                self.lcd.clear()
                self.lcd.write_to_position(0,0,_("GO!            "))
            case "ACTIVE":
                self._status = "ACTIVE"
                self.sns.register_Car_cleared_callback(self.ACTIVE_handle_car_cleared)
                self.sns.register_Car_detected_callback(self.ACTIVE_handle_car_detected)
                self.trl.set_green()
                self.lcd.clear()
                self.lcd.write_to_position(0,0,_("LAP :"))
                self.lcd.write_to_position(1,0,_("BEST:"))
            case "FALSE_START":
                self._status = "FALSE_START"
                self.sns.register_Car_cleared_callback(self.ignore_car_cleared)
                self.sns.register_Car_detected_callback(self.ignore_car_detected)
                self.trl.alarm()
                self.lcd.clear()
                self.lcd.write_to_position(0,0,_("FALSE START     "))
            case "RACE_END":
                self._status = "RACE_END"
                self.sns.register_Car_cleared_callback(self.ignore_car_cleared)
                self.sns.register_Car_detected_callback(self.ignore_car_detected)
                self.trl.turn_off()

    def is_lined_up(self):
        logger.debug("Track.is_lined_up Entry - Track %s", self.name)
        if self.sns.is_occupied() == True:
            logger.debug("Track.is_lined_up - Track %s is occupied", self.name)
            self.status = "LINEUP"
            return True
        else:
            logger.debug("Track.is_lined_up - Track %s is not occupied", self.name)
        return False

    def ignore_car_detected(self):
        logger.debug("Track.ignore_car_detected Entry")
        pass

    def ignore_car_cleared(self):
        logger.debug("Track.ignore_car_cleared Entry")
        pass

    def LINEUP_handle_car_detected(self):
        logger.debug("Track.LINEUP_handle_car_detected Entry")
        self.status = "READY"

    def LINEUP_handle_car_cleared(self):
        logger.debug("Track.LINEUP_handle_car_cleared Entry")
        self.status = "LINEUP"

    def READY_handle_car_detected(self):
        logger.debug("Track.READY_handle_car_detected Entry")
        pass

    def READY_handle_car_cleared(self):
        logger.debug("Track.READY_handle_car_cleared Entry")
        self.status = "LINEUP"

    def START_RED_handle_car_detected(self):
        logger.debug("Track.START_RED_handle_car_detected Entry")
        pass

    def START_RED_handle_car_cleared(self):
        logger.debug("Track.START_RED_handle_car_cleared Entry")
        self.status = "FALSE_START"

    def START_YELLOW_handle_car_detected(self):
        logger.debug("Track.START_YELLOW_handle_car_detected Entry")
        pass

    def START_YELLOW_handle_car_cleared(self):
        logger.debug("Track.START_YELLOW_handle_car_cleared Entry")
        self.status = "FALSE_START"

    def START_GREEN_handle_car_detected(self):
        logger.debug("Track.START_GREEN_handle_car_detected Entry")
        pass

    def START_GREEN_handle_car_cleared(self):
        logger.debug("Track.START_GREEN_handle_car_cleared Entry")
        self.status = "ACTIVE"

    def ACTIVE_handle_car_detected(self):
        """Handle car detection within an active race

           Increment the lap count and determine the best lap
        """
        logger.debug("Track.ACTIVE_handle_car_detected Entry")
        if self.lap_start is None:
            self.lap_start = time.time()
            self.start = time.time()
            self.laps = 0
            self.total_time = 0.0
            self.current_lap_time = 0.0
            self.lcd.write_to_position(0,5,f"{self.laps:2d}")
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
            self.lcd.write_to_position(0,8,f"{format_decimal(self.current_lap_time, format='0.0', locale=self.lng):>5}")
            self.lcd.write_to_position(0,14,_("sc"))
            self.lcd.write_to_position(1,8,f"{format_decimal(self.best_lap_time, format='0.0', locale=self.lng):>5}")
            self.lcd.write_to_position(1,14,_("sc"))

    def ACTIVE_handle_car_cleared(self):
        logger.debug("Track.ACTIVE_handle_car_cleared Entry")
        pass

    def show_setup(self):
        """Display the setup information on the track LCD"""
        logger.debug("Track.show_setup Entry")

        if self.enabled:
            self.lcd.write_to_position(0, 0, _("TRACK"))
            self.lcd.write_to_position(0, 6, self.id)
            self.lcd.write_to_position(1, 0, _("HANDICAP :"))
            self.lcd.write_to_position(1, 11, f"{int(self.handicap):2d}")
        else:
            self.lcd.clear()
            self.lcd.off()

class Race:
    """This class implements a race
    """
    def __init__(self):
        self._state = "IDLE"
        self._tracks = []
        self._race_mode = "OPEN"
        self._race_laps = 0
        self._race_time_min = 0
        self._start_time = None
        self._end_time = None
        self._duration = 0.0
        self._winner = None

    @property
    def state(self) -> str:
        return self._state

    @state.setter
    def state(self, value: str):
        self._state = value

    @property
    def tracks(self) -> list["Track"]:
        return self._tracks

    @tracks.setter
    def tracks(self, value: list["Track"]):
        self._tracks = value

    @property
    def race_mode(self) -> str:
        return self._race_mode

    @race_mode.setter
    def race_mode(self, value: str):
        self._race_mode = value

    @property
    def race_laps(self) -> int:
        return self._race_laps

    @race_laps.setter
    def race_laps(self, value: int):
        self._race_laps = value

    @property
    def race_time_min(self) -> int:
        return self._race_time_min

    @race_time_min.setter
    def race_time_min(self, value: int):
        self._race_time_min = value

    @property
    def start_time(self) -> datetime.datetime:
        return self._start_time

    @start_time.setter
    def start_time(self, value: datetime.datetime):
        self._start_time = value

    @property
    def end_time(self) -> datetime.datetime:
        return self._end_time

    @end_time.setter
    def end_time(self, value: datetime.datetime):
        self._end_time = value

    @property
    def duration(self) -> datetime.timedelta:
        return self._duration

    @duration.setter
    def duration(self, value: datetime.timedelta):
        self._duration = value

    @property
    def winner(self) -> "Track":
        return self._winner

    @winner.setter
    def winner(self, value: "Track"):
        self._winner = value

    def start(self):
        """Start a race
        """
        self.state = "running"
        self.start_time = datetime.datetime.now()
        self.end_time = None
        self.duration = datetime.timedelta(0)

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
