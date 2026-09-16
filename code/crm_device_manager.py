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
from RPLCD import CharLCD
import json
import os
import time

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
        else:
            self.selector = None

        if "SNS_Track_1" in device_config:
            self.track_1_sensor = Sensor_crm(device_config["SNS_Track_1"]["params"])
        else:
            self.track_1_sensor = None

        if "SNS_Track_2" in device_config:
            self.track_2_sensor = Sensor_crm(device_config["SNS_Track_2"]["params"])
        else:
            self.track_2_sensor = None

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

    def register_Track_1_Car_detected_callback(self, callback):
        """Register a callback function for the Track 1 car detected event.

        Args:
            callback (function): The function to be called when a car is detected on Track 1.
        """
        if self.track_1_sensor:
            self.track_1_sensor.when_deactivated = callback

    def register_Track_2_Car_detected_callback(self, callback):
        """Register a callback function for the Track 2 car detected event.

        Args:
            callback (function): The function to be called when a car is detected on Track 2.
        """
        if self.track_2_sensor:
            self.track_2_sensor.when_deactivated = callback

    def register_Track_1_Car_cleared_callback(self, callback):
        """Register a callback function for the Track 1 car cleared event.

        Args:
            callback (function): The function to be called when a car is no longer detected on Track 1.
        """
        if self.track_1_sensor:
            self.track_1_sensor.when_activated = callback

    def register_Track_2_Car_cleared_callback(self, callback):
        """Register a callback function for the Track 2 car cleared event.

        Args:
            callback (function): The function to be called when a car is no longer detected on Track 2.
        """
        if self.track_2_sensor:
            self.track_2_sensor.when_activated = callback

class Button_crm(Button):
    def __init__(self, params: dict):
        gpio_pin = params.get("GPIO_pin")
        bounce_time = params.get("bounce_time", 0.1)
        super().__init__(gpio_pin, bounce_time=bounce_time)

class Rotary_Encoder_crm(RotaryEncoder):
    def __init__(self, params: dict):
        self.gpio_pin_SW = params.get("GPIO_pin_SW")
        self.gpio_pin_DT = params.get("GPIO_pin_DT")
        self.gpio_pin_CLK = params.get("GPIO_pin_CLK")
        super().__init__(a=self.gpio_pin_CLK, b=self.gpio_pin_DT, wrap=True, max_steps=32)

class Sensor_crm(DigitalInputDevice):
    def __init__(self, params: dict):
        gpio_pin = params.get("GPIO_pin")
        bounce_time = params.get("bounce_time", 0.1)
        super().__init__(gpio_pin, bounce_time=bounce_time)

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

if __name__ == "__main__":
    # Example usage
    from datetime import datetime as dt
    import threading

    device_manager = DeviceManager()

    # Test Buttons
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

    # Test Selector
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

    # Test Track Sensors
    if device_manager.track_1_sensor:
        print("Track 1 sensor initialized.")
    else:
        print("Track 1 sensor not found in configuration.")

    if device_manager.track_2_sensor:
        print("Track 2 sensor initialized.")
    else:
        print("Track 2 sensor not found in configuration.")

    def on_track_1_car_detected():
        print(f"{dt.now()}: Track 1 car detected.")

    def on_track_1_car_cleared():
        print(f"{dt.now()}: Track 1 car cleared.")

    def on_track_2_car_detected():
        print(f"{dt.now()}: Track 2 car detected.")

    def on_track_2_car_cleared():
        print(f"{dt.now()}: Track 2 car cleared.")

    device_manager.register_Track_1_Car_detected_callback(on_track_1_car_detected)
    device_manager.register_Track_1_Car_cleared_callback(on_track_1_car_cleared)
    device_manager.register_Track_2_Car_detected_callback(on_track_2_car_detected)
    device_manager.register_Track_2_Car_cleared_callback(on_track_2_car_cleared)

    # Traffic Lights
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
            trl_1.set_red()
            trl_2.set_red()
            time.sleep(1)
            trl_1.set_yellow()
            trl_2.set_yellow()
            time.sleep(1)
            trl_1.set_green()
            trl_2.set_green()
            time.sleep(1)
            trl_1.turn_off()
            trl_2.turn_off()
            time.sleep(1)
        trl_1.turn_off()
        trl_2.turn_off()

    # Show traffic lights in own thread
    print("Starting Traffic Light Cycle: Red, Yellow, Green, Off")
    traffic_lights_thread = threading.Thread(target=show_traffic_lights)
    traffic_lights_stop = False
    traffic_lights_thread.daemon = True
    traffic_lights_thread.start()

    def show_speaker():
        spk = device_manager.speaker
        while not speaker_stop:
            spk.play_fanfare()
            time.sleep(5)
            spk.play_alarm()
            time.sleep(5)
            spk.off()

    # Show speaker in own thread
    spk = device_manager.speaker.speaker
    print("Speaker Info:")
    print(f"Speaker max_tone: {spk.max_tone}")
    print(f"Speaker min_tone: {spk.min_tone}")
    print(f"Speaker mid_tone: {spk.mid_tone}")
    print(f"Speaker octaves: {spk.octaves}")
    print()
    print("Starting Speaker Cycle: Fanfare")
    speaker_thread = threading.Thread(target=show_speaker)
    speaker_stop = False
    speaker_thread.daemon = True
    speaker_thread.start()

    # Keep the script running to listen for button presses
    try:
        while True:
            pass
    except KeyboardInterrupt:
        print("Exiting...")
        if traffic_lights_thread.is_alive():
            traffic_lights_stop = True
            time.sleep(1)
            traffic_lights_thread.join()
        if speaker_thread.is_alive():
            speaker_stop = True
            time.sleep(1)
            speaker_thread.join()
