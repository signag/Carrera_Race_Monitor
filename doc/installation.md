# Installation

1. Clone repository
<br>```git clone https://github.com/signag/Carrera_Race_Monitor```
2. Create virtual environment
<br>```cd Carrera_Race_Monitor```
<br>```python -m venv --system-site-packages .venv```
3. Install required Packages
<br>```pip install gpiozero```
4. Libraries for LCD display
<br>```sudo apt install python3-smbus i2c-tools```
<br>```pip install RPLCD --break-system-packages```
<br>Doc: https://rplcd.readthedocs.io/en/stable/