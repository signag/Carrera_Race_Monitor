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
import json
import os
import time

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
        self.red.blink(on_time=0.5, off_time=0.5)
        self.yellow.blink(on_time=0.5, off_time=0.5)
        self.green.blink(on_time=0.5, off_time=0.5)

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

class LCD_crm():
    def __init__(self, params: dict):
        self.i2c_address = params.get("I2C_address")
        self.lcd = CharLCD('PCF8574',int(self.i2c_address, 16), cols=16, rows=2, dotsize=8)
        self.lcd.backlight_enabled = False

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

class Rotary_Encoder_Button_crm(Button):
    def __init__(self, params: dict):
        self.gpio_pin_SW = params.get("GPIO_pin_SW")
        bounce_time = params.get("bounce_time", 0.1)
        super().__init__(self.gpio_pin_SW, bounce_time=bounce_time)

class Sensor_crm(DigitalInputDevice):
    def __init__(self, params: dict):
        gpio_pin = params.get("GPIO_pin")
        bounce_time = params.get("bounce_time", 0.1)
        super().__init__(gpio_pin, bounce_time=bounce_time)

    def is_occupied(self) -> bool:
        """Check if the sensor is currently detecting an object.

        Returns:
            bool: True if the sensor is detecting an object, False otherwise.
        """
        return not self.value

    def register_Car_detected_callback(self, callback):
        """Register a callback function for the car detected event.

        Args:
            callback (function): The function to be called when a car is detected on this track.
        """
        self.when_deactivated = callback

    def register_Car_cleared_callback(self, callback):
        """Register a callback function for the Track 1 car cleared event.

        Args:
            callback (function): The function to be called when a car is no longer detected on this track.
        """
        self.when_activated = callback

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
            self.sensor_track_1 = Sensor_crm(device_config["SNS_Track_1"]["params"])
        else:
            self.sensor_track_1 = None

        if "SNS_Track_2" in device_config:
            self.sensor_track_2 = Sensor_crm(device_config["SNS_Track_2"]["params"])
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
    def on_track_1_car_detected():
        print(f"{dt.now()}: Track 1 car detected.")
        print(f"{dt.now()}: Track 1 occupied: {device_manager.sensor_track_1.is_occupied()}.")

    def on_track_1_car_cleared():
        print(f"{dt.now()}: Track 1 car cleared.")
        print(f"{dt.now()}: Track 1 occupied: {device_manager.sensor_track_1.is_occupied()}.")

    def on_track_2_car_detected():
        print(f"{dt.now()}: Track 2 car detected.")
        print(f"{dt.now()}: Track 2 occupied: {device_manager.sensor_track_2.is_occupied()}.")

    def on_track_2_car_cleared():
        print(f"{dt.now()}: Track 2 car cleared.")
        print(f"{dt.now()}: Track 2 occupied: {device_manager.sensor_track_2.is_occupied()}.")

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
            trl_1.alarm()
            trl_2.alarm()
            time.sleep(3)
        trl_1.turn_off()
        trl_2.turn_off()

    # Show traffic lights in own thread
    print("Starting Traffic Light Cycle: Red, Yellow, Green, Off")
    traffic_lights_thread = threading.Thread(target=show_traffic_lights)
    traffic_lights_stop = False
    traffic_lights_thread.daemon = True
    traffic_lights_thread.start()

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

    # Keep the script running to listen for input device actions
    # while sumultaneously generating output for output devices
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
        if lcd_track_1_thread.is_alive():
            lcd_track_1_stop = True
            time.sleep(1)
            lcd_track_1_thread.join()
        if lcd_track_2_thread.is_alive():
            lcd_track_2_stop = True
            time.sleep(1)
            lcd_track_2_thread.join()
        if lcd_circuit_thread.is_alive():
            lcd_circuit_stop = True
            time.sleep(1)
            lcd_circuit_thread.join()
