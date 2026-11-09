"""Device manager for Carrera Race Monitor.

This module handles the management of devices connected to the Carrera Race Monitor system.
It provides registration of callback functions for relevant events of input devices
as well as access to output devices.

Input devices:
- Button (from gpiozero)
- RotaryEncoder (from gpiozero)
- Obstacle Avoidance Sensor (from gpiozero)

Output Devices:
- Traffic Light (from gpiozero)
- Passive Buzzer (from gpiozero)
- LCD (from RPLCD)

"""
from gpiozero import Button, RotaryEncoder, DigitalInputDevice
from gpiozero import LED, TonalBuzzer
from RPLCD.i2c import CharLCD
from threading import Lock, Timer
import json
import os
import time
from pathlib import Path
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
logger.setLevel(logging.ERROR)

class Traffic_Light_crm():
    def __init__(self, params: dict):
        self.gpio_pin_red = params.get("GPIO_pin_red")
        self.gpio_pin_yellow = params.get("GPIO_pin_yellow")
        self.gpio_pin_green = params.get("GPIO_pin_green")
        # Initialize the traffic light pins as output devices
        self.red = LED(self.gpio_pin_red)
        self.yellow = LED(self.gpio_pin_yellow)
        self.green = LED(self.gpio_pin_green)

    def set_red(self):
        self.red.on()
        self.yellow.off()
        self.green.off()

    def set_yellow(self):
        self.red.on()
        self.yellow.on()
        self.green.off()

    def set_green(self):
        self.red.off()
        self.yellow.off()
        self.green.on()

    def turn_off(self):
        self.red.off()
        self.yellow.off()
        self.green.off()

    def alarm(self):
        self.red.blink(on_time=0.5, off_time=0.5, n=3)
        self.yellow.blink(on_time=0.5, off_time=0.5, n=3)
        self.green.blink(on_time=0.5, off_time=0.5, n=3)

    def close(self):
        self.red.close()
        self.yellow.close()
        self.green.close()

class Speaker_crm():
    def __init__(self, params: dict):
        self.gpio_pin = params.get("GPIO_pin")
        self.speaker = TonalBuzzer(self.gpio_pin)

    def play_fanfare(self):
        fanfare = [
            ("A3", 0.20),
            ("E4", 0.20),
            ("A4", 0.30),
            ("C5", 0.20),
            ("E5", 0.30),
            ("A4", 0.15),
            ("E5", 0.20),
            ("A5", 1.10),
        ]
        for note, duration in fanfare:
            self.speaker.play(note)
            time.sleep(duration)
            self.speaker.stop()
            time.sleep(0.05)

    def play_alarm(self):
        alarm = [
            ("A4", 0.15),
            ("B4", 0.15),
            ("C5", 0.15),
            ("D5", 0.15),
            ("E5", 0.15),
            ("D5", 0.15),
            ("C5", 0.15),
            ("B4", 0.15),
        ]

        for _ in range(3):
            for note, duration in alarm:
                self.speaker.play(note)
                time.sleep(duration)

        self.speaker.stop()
        time.sleep(0.05)

    def off(self):
        self.speaker.stop()

    def close(self):
        self.speaker.close()

class LCD_crm():
    def __init__(self, params: dict):
        self.i2c_address = params.get("I2C_address")
        self.lcd = CharLCD('PCF8574',int(self.i2c_address, 16), cols=16, rows=2, dotsize=8)
        self.lcd.backlight_enabled = False
        self.arrow = (
            0b00100,
            0b00100,
            0b00100,
            0b00100,
            0b00100,
            0b10101,
            0b01110,
            0b00100
        );
        self.lcd.create_char(0, self.arrow)

    def display_message(self, message: str):
        self.lcd.clear()
        self.lcd.backlight_enabled = True
        self.lcd.write_string(message)

    def write_to_position(self, row: int, col: int, message: str):
        self.lcd.backlight_enabled = True
        self.lcd.cursor_pos = (row, col)
        self.lcd.write_string(message)

    def clear(self):
        self.lcd.backlight_enabled = True
        self.lcd.clear()

    def off(self):
        self.lcd.clear()
        self.lcd.backlight_enabled = False

    def close(self):
        self.off()
        self.lcd.close()

class Button_crm(Button):
    def __init__(self, params: dict):
        gpio_pin = params.get("GPIO_pin")
        bounce_time = params.get("bounce_time", 0.1)
        super().__init__(gpio_pin, bounce_time=bounce_time)

    def close(self):
        super().close()

class Rotary_Encoder_crm(RotaryEncoder):
    def __init__(self, params: dict):
        self.gpio_pin_SW = params.get("GPIO_pin_SW")
        self.gpio_pin_DT = params.get("GPIO_pin_DT")
        self.gpio_pin_CLK = params.get("GPIO_pin_CLK")
        super().__init__(a=self.gpio_pin_CLK, b=self.gpio_pin_DT, wrap=True, max_steps=32)
        self.close = self._close

    def _close(self):
        super().close()

class Rotary_Encoder_Button_crm(Button):
    def __init__(self, params: dict):
        self.gpio_pin_SW = params.get("GPIO_pin_SW")
        bounce_time = params.get("bounce_time", 0.1)
        super().__init__(self.gpio_pin_SW, bounce_time=bounce_time)

    def close(self):
        super().close()

class Sensor_crm_simple(DigitalInputDevice):
    def __init__(self, type: str, params: dict):
        if type is not None and type in ["Obstacle_Sensor", "Light_Barrier_Sensor"]:
            self._type = type
        else:
            self._type = "Obstacle_Sensor"
        gpio_pin = params.get("GPIO_pin")
        bounce_time = params.get("bounce_time", 0.01)
        pull_up_required = True if self._type == "Light_Barrier_Sensor" else False
        super().__init__(gpio_pin, bounce_time=bounce_time, pull_up=pull_up_required)

    def is_occupied(self) -> bool:
        """Check if the sensor is currently detecting an object.

        Returns:
            bool: True if the sensor is detecting an object, False otherwise.
        """
        if self._type == "Light_Barrier_Sensor":
            return self.value == 1
        else:
            return self.value == 0

    def register_Car_detected_callback(self, callback):
        """Register a callback function for the car detected event.

        Args:
            callback (function): The function to be called when a car is detected on this track.
        """
        if self._type == "Light_Barrier_Sensor":
            self.when_activated = callback
        else:
            self.when_deactivated = callback

    def register_Car_cleared_callback(self, callback):
        """Register a callback function for the Track 1 car cleared event.

        Args:
            callback (function): The function to be called when a car is no longer detected on this track.
        """
        if self._type == "Light_Barrier_Sensor":
            self.when_deactivated = callback
        else:
            self.when_activated = callback

class Sensor_crm(DigitalInputDevice):
    """This class implements a car detection sensor as a specialized gpiozero DigitalInputDevice

    The class handles both obstacle sensors as well as light barrier sensors.

    It takes into account that a car passage may trigger multiple sensor activations and deactivations
    caused by the shape of the car with surfaces oriented in different directions with respect to the sensor.
    A lockout period is used to prevent multiple detections from being registered during a single car passage,
    and a clear delay ensures that the sensor is only considered cleared after a certain period of inactivity.

    Args:
        DigitalInputDevice (_type_): gpiozero DigitalInputDevice base class for the sensor.
    """

    def __init__(self, type: str, params: dict):
        """Constructor for car detection sensor class

        Args:
            type (str): Sensor type:
                        - "Obstacle_Sensor" (default)
                        - "Light_Barrier_Sensor"
            params (dict): Sensor parameters dictionary:
                        - "GPIO_pin" (int): GPIO pin number the sensor is connected to.
                        - "lockout_time" (float, optional): Lockout time in seconds (default: 0.1).
                        - "clear_delay" (float, optional): Clear delay time in seconds (default: 0.05).
        """
        logger.debug("Sensor_crm.__init__ - ENTRY - type=%s, params=%s", type, params)
        if type is not None and type in ["Obstacle_Sensor", "Light_Barrier_Sensor"]:
            self._type = type
        else:
            self._type = "Obstacle_Sensor"
        gpio_pin = params.get("GPIO_pin")
        self.lockout_time = params.get("lockout_time", 0.1)
        self.clear_delay = params.get("clear_delay", 0.05)

        self._armed = True
        self._passage_active = False
        self._lockout_until = 0.0

        self._state_lock = Lock()
        self._rearm_timer = None
        self._clear_timer = None

        self._car_detected_callback = None
        self._car_cleared_callback = None

        pull_up_required = True if self._type == "Light_Barrier_Sensor" else False

        logger.debug("Sensor_crm.__init__ - gpio_pin=%s", gpio_pin)
        logger.debug("Sensor_crm.__init__ - pull_up_required=%s", pull_up_required)
        logger.debug("Sensor_crm.__init__ - lockout_time=%s", self.lockout_time)
        super().__init__(
            gpio_pin,
            bounce_time=None,
            pull_up=pull_up_required
        )

        if self.is_occupied() == True:
            now = time.monotonic()
            self._armed = False
            self._passage_active = True
            self._lockout_until = now + self.lockout_time
            self._rearm_timer = Timer(
                self.lockout_time,
                self._try_rearm
            )
            self._rearm_timer.daemon = True
            self._rearm_timer.start()

        if self._type == "Light_Barrier_Sensor":
            self.when_activated = self._on_activated
            self.when_deactivated = self._on_deactivated
        else:
            self.when_activated = self._on_deactivated
            self.when_deactivated = self._on_activated
        logger.debug("Sensor_crm.__init__ - EXIT")

    def _on_activated(self):
        """Accept a new car passage."""

        logger.debug("Sensor_crm._on_activated - ENTRY - _armed=%s, _lockout_until=%s, _passage_active=%s", self._armed, self._lockout_until, self._passage_active)
        callback = None

        with self._state_lock:
            now = time.monotonic()
            logger.debug("Sensor_crm._on_activated - now=%s", now)

            # Flicker during a passage: cancel the pending clear.
            if self._clear_timer is not None:
                self._clear_timer.cancel()
                self._clear_timer = None
                logger.debug("Sensor_crm._on_activated - pending clear canceled")

            if self._armed and now >= self._lockout_until:
                self._armed = False
                self._passage_active = True
                self._lockout_until = now + self.lockout_time

                callback = self._car_detected_callback

                if self._rearm_timer is not None:
                    self._rearm_timer.cancel()

                self._rearm_timer = Timer(
                    self.lockout_time,
                    self._try_rearm
                )
                self._rearm_timer.daemon = True
                self._rearm_timer.start()

        if callback is not None:
            callback()
            logger.debug("Sensor_crm._on_activated - callback executed")
        else:
            logger.debug("Sensor_crm._on_activated - no callback executed")
        logger.debug("Sensor_crm._on_activated - EXIT - _armed=%s, _lockout_until=%s, _passage_active=%s", self._armed, self._lockout_until, self._passage_active)

    def _on_deactivated(self):
        """Accept a clear event only for an active passage."""
        logger.debug("Sensor_crm._on_deactivated - ENTRY - _armed=%s, _lockout_until=%s, _passage_active=%s", self._armed, self._lockout_until, self._passage_active)

        # The signal went inactive; wait to see whether it stays inactive.
        with self._state_lock:
            if not self._passage_active:
                return

            if self._clear_timer is not None:
                self._clear_timer.cancel()

            self._clear_timer = Timer(self.clear_delay, self._confirm_clear)
            self._clear_timer.daemon = True
            self._clear_timer.start()
        logger.debug("Sensor_crm._on_deactivated - EXIT - _armed=%s, _lockout_until=%s, _passage_active=%s", self._armed, self._lockout_until, self._passage_active)

    def _confirm_clear(self):
        """Confirm that the passage has cleared after the clear delay."""
        logger.debug("Sensor_crm._confirm_clear - ENTRY - _armed=%s, _lockout_until=%s, _passage_active=%s", self._armed, self._lockout_until, self._passage_active)
        callback = None

        with self._state_lock:
            self._clear_timer = None

            # The sensor became occupied again while the timer was running.
            if self.is_occupied() or not self._passage_active:
                return

            self._passage_active = False
            self._armed = True
            callback = self._car_cleared_callback

        if callback is not None:
            callback()
            logger.debug("Sensor_crm._confirm_clear - callback executed")
        logger.debug("Sensor_crm._confirm_clear - EXIT - _armed=%s, _lockout_until=%s, _passage_active=%s", self._armed, self._lockout_until, self._passage_active)

    def _try_rearm(self):
        """Re-arm only when lockout has expired and position is not occupied."""
        logger.debug("Sensor_crm._try_rearm - ENTRY")

        with self._state_lock:
            if (time.monotonic() >= self._lockout_until
                    and not self.is_occupied()
                    and not self._passage_active):
                self._armed = True
                logger.debug("Sensor_crm._try_rearm - Sensor re-armed")
        logger.debug("Sensor_crm._try_rearm - EXIT")

    def is_occupied(self) -> bool:
        """Check if the sensor is currently occupied by a car."""
        logger.debug("Sensor_crm.is_occupied - ENTRY")
        if self._type == "Light_Barrier_Sensor":
            logger.debug("Sensor_crm.is_occupied - EXIT - returning %s", self.value == 1)
            return self.value == 1
        else:
            logger.debug("Sensor_crm.is_occupied - EXIT - returning %s", self.value == 0)
            return self.value == 0

    def register_Car_detected_callback(self, callback):
        self._car_detected_callback = callback

    def register_Car_cleared_callback(self, callback):
        self._car_cleared_callback = callback

    def close(self):
        if self._rearm_timer is not None:
            self._rearm_timer.cancel()
        if self._clear_timer is not None:
            self._clear_timer.cancel()

        super().close()

class DeviceManager:
    def __init__(self, device_config: dict=None):
        """Initialization of DeviceManager

        If a configuration is provided, it will be used to initialize the devices.
        Otherwise, the configuration will be loaded from a JSON file

        Args:
            device_config (dict, optional): Configuration for devices. Defaults to None.
        """

        if device_config is None:
            # Load configuration from JSON file
            device_config = self.get_config()

        if "BTN_Reset" in device_config:
            self.reset_button = Button_crm(device_config["BTN_Reset"]["params"])
        else:
            self.reset_button = None

        if "BTN_Restart" in device_config:
            self.restart_button = Button_crm(device_config["BTN_Restart"]["params"])
        else:
            self.restart_button = None

        if "BTN_Start" in device_config:
            self.start_button = Button_crm(device_config["BTN_Start"]["params"])
        else:
            self.start_button = None

        if "Selector" in device_config:
            self.selector = Rotary_Encoder_crm(device_config["Selector"]["params"])
            self.selector_button = Rotary_Encoder_Button_crm(device_config["Selector"]["params"])
        else:
            self.selector = None
            self.selector_button = None

        if "SNS_Track_1" in device_config:
            self.sensor_track_1 = Sensor_crm(
                device_config["SNS_Track_1"]["type"],
                device_config["SNS_Track_1"]["params"]
            )
        else:
            self.sensor_track_1 = None

        if "SNS_Track_2" in device_config:
            self.sensor_track_2 = Sensor_crm(
                device_config["SNS_Track_2"]["type"],
                device_config["SNS_Track_2"]["params"]
            )
        else:
            self.sensor_track_2 = None

        if "TRL_Track_1" in device_config:
            self.traffic_light_track_1 = Traffic_Light_crm(device_config["TRL_Track_1"]["params"])
        else:
            self.traffic_light_track_1 = None

        if "TRL_Track_2" in device_config:
            self.traffic_light_track_2 = Traffic_Light_crm(device_config["TRL_Track_2"]["params"])
        else:
            self.traffic_light_track_2 = None

        if "Speaker" in device_config:
            self.speaker = Speaker_crm(device_config["Speaker"]["params"])
        else:
            self.speaker = None

        if "LCD_Track_1" in device_config:
            self.lcd_track_1 = LCD_crm(device_config["LCD_Track_1"]["params"])
        else:
            self.lcd_track_1 = None

        if "LCD_Track_2" in device_config:
            self.lcd_track_2 = LCD_crm(device_config["LCD_Track_2"]["params"])
        else:
            self.lcd_track_2 = None

        if "LCD_Circuit" in device_config:
            self.lcd_circuit = LCD_crm(device_config["LCD_Circuit"]["params"])
        else:
            self.lcd_circuit = None

    def get_config(self) -> dict:
        """Get the current device configuration.

        Search for the configuration in the file crm_config.json successively in 
        the current directory, ../config or HOME/.config

        Returns:
            dict: The current device configuration.
        """
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

        with open(config_file, "r") as f:
            content = json.load(f)

            if "devices" in content:
                return content["devices"]
            else:
                raise KeyError("The configuration file does not contain 'devices' key.")

    def get_traffic_light(self, track_name: str) -> Traffic_Light_crm:
        if track_name == "Track_1":
            return self.traffic_light_track_1
        elif track_name == "Track_2":
            return self.traffic_light_track_2
        else:
            return None

    def get_sensor(self, track_name: str) -> Sensor_crm:
        if track_name == "Track_1":
            return self.sensor_track_1
        elif track_name == "Track_2":
            return self.sensor_track_2
        else:
            return None

    def get_lcd(self, track_name: str) -> LCD_crm:
        if track_name == "Track_1":
            return self.lcd_track_1
        elif track_name == "Track_2":
            return self.lcd_track_2
        else:
            return None
            
    def register_BTN_Reset_pressed_callback(self, callback):
        """Register a callback function for the reset button press event.

        Args:
            callback (function): The function to be called when the reset button is pressed.
        """
        if self.reset_button:
            self.reset_button.when_pressed = callback
            
    def register_BTN_Restart_pressed_callback(self, callback):
        """Register a callback function for the restart button press event.

        Args:
            callback (function): The function to be called when the restart button is pressed.
        """
        if self.restart_button:
            self.restart_button.when_pressed = callback
            
    def register_BTN_Start_pressed_callback(self, callback):
        """Register a callback function for the start button press event.

        Args:
            callback (function): The function to be called when the start button is pressed.
        """
        if self.start_button:
            self.start_button.when_pressed = callback

    def register_Selector_rotated_clockwise_callback(self, callback):
        """Register a callback function for the selector rotated clockwise event.

        Args:
            callback (function): The function to be called when the selector is rotated clockwise.
        """
        if self.selector:
            self.selector.when_rotated_clockwise = callback

    def register_Selector_rotated_counter_clockwise_callback(self, callback):
        """Register a callback function for the selector rotated counter clockwise event.

        Args:
            callback (function): The function to be called when the selector is rotated counterclockwise.
        """
        if self.selector:
            self.selector.when_rotated_counter_clockwise = callback
            
    def register_Selector_Button_pressed_callback(self, callback):
        """Register a callback function for the selector button press event.

        Args:
            callback (function): The function to be called when the selector button is pressed.
        """
        if self.selector_button:
            self.selector_button.when_pressed = callback

    def close(self):
        if self.reset_button:
            self.reset_button.close()
        if self.restart_button:
            self.restart_button.close()
        if self.start_button:
            self.start_button.close()
        if self.selector:
            self.selector.close()
        if self.selector_button:
            self.selector_button.close()
        if self.sensor_track_1:
            self.sensor_track_1.close()
        if self.sensor_track_2:
            self.sensor_track_2.close()
        if self.traffic_light_track_1:
            self.traffic_light_track_1.close()
        if self.traffic_light_track_2:
            self.traffic_light_track_2.close()
        if self.speaker:
            self.speaker.close()
        if self.lcd_track_1:
            self.lcd_track_1.close()
        if self.lcd_track_2:
            self.lcd_track_2.close()
        if self.lcd_circuit:
            self.lcd_circuit.close()

if __name__ == "__main__":
    """Demo & Test for CRM Device Manager

       The test will initialize all devices and execute basic functionality tests for each.
    """
    from datetime import datetime as dt
    import threading

    device_manager = DeviceManager()

    ##############
    # Test Buttons
    ##############
    if device_manager.reset_button:
        print("Reset button initialized.")
    else:
        print("Reset button not found in configuration.")

    if device_manager.restart_button:
        print("Restart button initialized.")
    else:
        print("Restart button not found in configuration.")

    if device_manager.start_button:
        print("Start button initialized.")
    else:
        print("Start button not found in configuration.")

    def on_reset_button_pressed():
        print(f"{dt.now()}: Reset button pressed.")

    def on_restart_button_pressed():
        print(f"{dt.now()}: Restart button pressed.")

    def on_start_button_pressed():
        print(f"{dt.now()}: Start button pressed.")

    device_manager.register_BTN_Reset_pressed_callback(on_reset_button_pressed)
    device_manager.register_BTN_Restart_pressed_callback(on_restart_button_pressed)
    device_manager.register_BTN_Start_pressed_callback(on_start_button_pressed)

    ###############
    # Test Selector
    ###############
    if device_manager.selector:
        print("Selector initialized.")
    else:
        print("Selector not found in configuration.")

    def on_selector_rotated_clockwise():
        print(f"{dt.now()}: Selector rotated clockwise.")

    def on_selector_rotated_counter_clockwise():
        print(f"{dt.now()}: Selector rotated counter-clockwise.")
    device_manager.register_Selector_rotated_clockwise_callback(on_selector_rotated_clockwise)
    device_manager.register_Selector_rotated_counter_clockwise_callback(on_selector_rotated_counter_clockwise)

    ######################
    # Test Selector Button
    ######################
    if device_manager.selector_button:
        print("Selector button initialized.")
    else:
        print("Selector button not found in configuration.")

    def on_selector_button_pressed():
        print(f"{dt.now()}: Selector button pressed.")

    device_manager.register_Selector_Button_pressed_callback(on_selector_button_pressed)

    ####################
    # Test Track Sensors
    ####################

    cnt_track_1_detected = 0
    cnt_track_2_detected = 0
    cnt_track_1_cleared = 0
    cnt_track_2_cleared = 0

    def on_track_1_car_detected():
        global cnt_track_1_detected
        cnt_track_1_detected += 1
        print(f"{dt.now()}: Track 1 car detected: #{cnt_track_1_detected}")

    def on_track_1_car_cleared():
        global cnt_track_1_cleared
        cnt_track_1_cleared += 1
        print(f"{dt.now()}: Track 1 car cleared: #{cnt_track_1_cleared}")
        print()

    def on_track_2_car_detected():
        global cnt_track_2_detected
        cnt_track_2_detected += 1
        print(f"{dt.now()}: Track 2 car detected: #{cnt_track_2_detected}")

    def on_track_2_car_cleared():
        global cnt_track_2_cleared
        cnt_track_2_cleared += 1
        print(f"{dt.now()}: Track 2 car cleared: #{cnt_track_2_cleared}")
        print()

    if device_manager.sensor_track_1:
        print("Track 1 sensor initialized.")
        print(f"Track 1 occupied: {device_manager.sensor_track_1.is_occupied()}.")
        device_manager.sensor_track_1.register_Car_detected_callback(on_track_1_car_detected)
        device_manager.sensor_track_1.register_Car_cleared_callback(on_track_1_car_cleared)
    else:
        print("Track 1 sensor not found in configuration.")

    if device_manager.sensor_track_2:
        print("Track 2 sensor initialized.")
        print(f"Track 2 occupied: {device_manager.sensor_track_2.is_occupied()}.")
        device_manager.sensor_track_2.register_Car_detected_callback(on_track_2_car_detected)
        device_manager.sensor_track_2.register_Car_cleared_callback(on_track_2_car_cleared)
    else:
        print("Track 2 sensor not found in configuration.")

    ################
    # Traffic Lights
    ################
    if device_manager.traffic_light_track_1:
        print("Traffic light for Track 1 initialized.")
    else:
        print("Traffic light for Track 1 not found in configuration.")

    if device_manager.traffic_light_track_2:
        print("Traffic light for Track 2 initialized.")
    else:
        print("Traffic light for Track 2 not found in configuration.")

    def show_traffic_lights():
        trl_1 = device_manager.traffic_light_track_1
        trl_2 = device_manager.traffic_light_track_2
        while not traffic_lights_stop:
            if trl_1:
                trl_1.set_red()
            if trl_2:
                trl_2.set_red()
            time.sleep(1)
            if trl_1:
                trl_1.set_yellow()
            if trl_2:
                trl_2.set_yellow()
            time.sleep(1)
            if trl_1:
                trl_1.set_green()
            if trl_2:
                trl_2.set_green()
            time.sleep(1)
            if trl_1:
                trl_1.turn_off()
            if trl_2:
                trl_2.turn_off()
            time.sleep(1)
            if trl_1:
                trl_1.alarm()
            if trl_2:
                trl_2.alarm()
            time.sleep(3)
        if trl_1:
            trl_1.turn_off()
        if trl_2:
            trl_2.turn_off()

    # Show traffic lights in own thread
    if device_manager.traffic_light_track_1 or device_manager.traffic_light_track_2:
        print("Starting Traffic Light Cycle: red - yellow - green - off - alarm - off")
        traffic_lights_thread = threading.Thread(target=show_traffic_lights)
        traffic_lights_stop = False
        traffic_lights_thread.daemon = True
        traffic_lights_thread.start()
    else:
        traffic_lights_thread = None
        if device_manager.traffic_light_track_1 is None:
            print("Traffic light for Track 1 not found in configuration.")
        if device_manager.traffic_light_track_2 is None:
            print("Traffic light for Track 2 not found in configuration.")

    ################
    # Test Speaker
    ################
    def show_speaker():
        spk = device_manager.speaker
        while not speaker_stop:
            spk.play_fanfare()
            time.sleep(5)
            spk.play_alarm()
            time.sleep(5)
            spk.off()

    # Show speaker in own thread
    spk = device_manager.speaker
    if spk:
        buz = spk.speaker
        print("Speaker Info:")
        print(f"Speaker max_tone: {buz.max_tone}")
        print(f"Speaker min_tone: {buz.min_tone}")
        print(f"Speaker mid_tone: {buz.mid_tone}")
        print(f"Speaker octaves: {buz.octaves}")
        print()
        print("Starting Speaker Cycle: fanfare - alarm - off")
        speaker_thread = threading.Thread(target=show_speaker)
        speaker_stop = False
        speaker_thread.daemon = True
        speaker_thread.start()
    else:
        speaker_thread = None
        print("Speaker not found in configuration.")

    ################
    # LCD Displays
    ################
    if device_manager.lcd_track_1:
        print("LCD for Track 1 initialized.")
    else:
        print("LCD for Track 1 not found in configuration.")

    if device_manager.lcd_track_2:
        print("LCD for Track 2 initialized.")
    else:
        print("LCD for Track 2 not found in configuration.")

    if device_manager.lcd_circuit:
        print("LCD for Circuit initialized.")
    else:
        print("LCD for Circuit not found in configuration.")

    def show_lcd_track_1():
        lcd = device_manager.lcd_track_1
        while not lcd_track_1_stop:
            lcd.display_message("Track 1 Info\n\rLine 2")
            time.sleep(5)
            lcd.off()
            time.sleep(1)

    # Show LCD for Track 1 in own thread
    if device_manager.lcd_track_1:
        lcd_track_1_stop = False
        lcd_track_1_thread = threading.Thread(target=show_lcd_track_1)
        lcd_track_1_thread.daemon = True
        lcd_track_1_thread.start()
    else:
        lcd_track_1_thread = None

    def show_lcd_track_2():
        lcd = device_manager.lcd_track_2
        while not lcd_track_2_stop:
            lcd.display_message("Track 2 Info\n\rLine 2")
            time.sleep(5)
            lcd.off()
            time.sleep(1)

    # Show LCD for Track 2 in own thread
    if device_manager.lcd_track_2:
        lcd_track_2_stop = False
        lcd_track_2_thread = threading.Thread(target=show_lcd_track_2)
        lcd_track_2_thread.daemon = True
        lcd_track_2_thread.start()
    else:
        lcd_track_2_thread = None

    def show_lcd_circuit():
        lcd = device_manager.lcd_circuit
        while not lcd_circuit_stop:
            lcd.display_message("Circuit Info")
            lcd.write_to_position(1, 0, "1")
            lcd.write_to_position(1, 4, "5")
            lcd.write_to_position(1, 14, "16")
            time.sleep(5)
            lcd.off()
            time.sleep(1)

    # Show LCD for Circuit in own thread
    if device_manager.lcd_circuit:
        lcd_circuit_stop = False
        lcd_circuit_thread = threading.Thread(target=show_lcd_circuit)
        lcd_circuit_thread.daemon = True
        lcd_circuit_thread.start()
    else:
        lcd_circuit_thread = None

    # Keep the script running to listen for input device actions
    # while sumultaneously generating output for output devices
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Exiting...")
        if traffic_lights_thread is not None and traffic_lights_thread.is_alive():
            traffic_lights_stop = True
            time.sleep(1)
            traffic_lights_thread.join()
        if speaker_thread is not None and speaker_thread.is_alive():
            speaker_stop = True
            time.sleep(1)
            speaker_thread.join()
        if lcd_track_1_thread is not None and lcd_track_1_thread.is_alive():
            lcd_track_1_stop = True
            time.sleep(1)
            lcd_track_1_thread.join()
        if lcd_track_2_thread is not None and lcd_track_2_thread.is_alive():
            lcd_track_2_stop = True
            time.sleep(1)
            lcd_track_2_thread.join()
        if lcd_circuit_thread is not None and lcd_circuit_thread.is_alive():
            lcd_circuit_stop = True
            time.sleep(1)
            lcd_circuit_thread.join()
        if device_manager:
            device_manager.close()