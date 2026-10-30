# Installation

1. Clone repository
<br>```git clone https://github.com/signag/Carrera_Race_Monitor```
2. Create virtual environment
<br>```cd Carrera_Race_Monitor```
<br>```python -m venv --system-site-packages .venv```
3. Activate virtual environment
<br>```source .venv/bin/activate```
4. Install required Packages
<br>```pip install gpiozero```
5. Libraries for LCD display
<br>```sudo apt install python3-smbus i2c-tools```
<br>```pip install RPLCD --break-system-packages```
<br>Doc: https://rplcd.readthedocs.io/en/stable/
6. I18n
<br>```sudo apt install gettext```
7. Flask
<br>```pip install flask```
<br>```pip install flask-socketio```
<br>```pip install flask-cors```
7. Messaging
<br>```sudo apt install mosquitto mosquitto-clients```
<br>```sudo systemctl enable --now mosquitto```
<br>```pip install paho-mqtt```
8. Enable I2C
<br>```sudo raspi-config```
<br>Interface Options -> I2C -> Enable
9. Check I2C ports for LCD2
<br>If LCD2 are connected and properly soldered for different ports, run
<br>```sudo i2cdetect -y 1```
<br>Depending on your chosen ports, you should see something like the following showing one distinct port for each of the three LCD displays
<br>```
     0  1  2  3  4  5  6  7  8  9  a  b  c  d  e  f
00:                         -- -- -- -- -- -- -- --
10: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
20: -- -- -- -- -- 25 26 27 -- -- -- -- -- -- -- --
30: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
40: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
50: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
60: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
70: -- -- -- -- -- -- -- --

```
