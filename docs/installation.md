# Carrera Race Monitor Installation

[![Up](img/goup.gif)](./index.md)

## Installation Steps

1. Connect to the Pi using SSH: 
<br>```ssh <user>@<host>```
<br>with ```<user>``` and ```<host>``` as specified during setup with Imager.
2. Make sure that the system is up to date
<br>```sudo apt update``` 
<br>```sudo apt full-upgrade```
3. Run the automatic installer with:      
```
bash <(curl -fsSL https://raw.githubusercontent.com/signag/Carrera_Race_Monitor/main/scripts/install_Carrera_Race_Monitor.sh)
```    
Follow instructions given by the installer (see [below](#installer))

## Installer

### First Installation

With the first installation of Carrera Race Monitor, services will not yet be installed in order to allow device tests during system assembly.

```
===================================================
=== Carrera_Race_Monitor Automated Installer    ===
===                                             ===
=== Exit at any step with Ctrl+C                ===
===================================================

RPI Model           : Raspberry Pi Zero 2 W Rev 1.0
Detected OS codename: trixie full
Hostname            : raspi12

Running as user     : sn
Installing at       : /home/sn/prg

=================
Installation Mode
=================
Installation Path     : /home/sn/prg/Carrera_Race_Monitor (will be created)

This is the first installation of Carrera_Race_Monitor on this system.
Services will not be installed to allow manual device tests during system assembly.
After successful device tests, you can run the installer again to configure and start the services.

No more questions! Ready to start installation? [Y/n]:

```

### Installation Protocol

The following is a shortenedinstallation protocol showing the different installation steps:

```
Creating root directory ...
Created: /home/sn/prg

Checking git ...
git is installed

Cloning Carrera_Race_Monitor ...
Cloning into 'Carrera_Race_Monitor'...
...

Creating virtual environment ...
Created: .venv

Activating virtual environment ...
Virtual environment activated
(.venv)

Installing Flask ...
...

Installing flask-cors ...
...

Installing gpiozero ...
...

Installing libraries for LCD display ...
...

Installing I18n tools ...
...

Installing messaging infrastructure ...
...

Checking I2C interface status ...
...

Virtual environment deactivated
(.venv)

Checking Flask service port ...
Trying port 5100 ...
Using port 5100

Services installation skipped.
This allows manual device tests during system assembly.
After assembly and successful device tests rerun this installer to install the services.
For details refer to CRM_Assembly_Instructions.pdf

```

If you see errors, such as

```
ERROR: pip's dependency resolver does not currently take into account all the packages that are installed. This behaviour is the source of
```
these can be ignored

### Service Installation

To automatically start Carrera Race Monitor when the system is powered up, it is necessary to install and enable two services:
- crm_server.service
<br>runs the server software
- crm_client.service
<br>runs the client to which you can connect with a browser

If the installer is run on a system where Carrera Race Monitor is already installed and where services are not yet installed, the following option will be offered:

```
===================================================
=== Carrera_Race_Monitor Automated Installer    ===
===                                             ===
=== Exit at any step with Ctrl+C                ===
===================================================

RPI Model           : Raspberry Pi Zero 2 W Rev 1.0
Detected OS codename: trixie full
Hostname            : raspi12

Running as user     : sn
Installing at       : /home/sn/prg

=====================
Installation Mode
=====================
Installation Path     : /home/sn/prg/Carrera_Race_Monitor (exists)
Service Status Server : crm_server.service (not configured)
Service Status Client : crm_client.service (not configured)

A Carrera_Race_Monitor installation exists already.

Do you want to skip update of Carrera_Race_Monitor and software stack and only reconfigure the services[Y/n]:

```

If you confirm with "y", the update will be skipped and only the services will be configured and enabled.

### System Upgrades

On a system with Carrera Race Monitor services installed, the installer will offer an update:

```
===================================================
=== Carrera_Race_Monitor Automated Installer    ===
===                                             ===
=== Exit at any step with Ctrl+C                ===
===================================================

RPI Model           : Raspberry Pi Zero 2 W Rev 1.0
Detected OS codename: trixie full
Hostname            : raspi12

Running as user     : sn
Installing at       : /home/sn/prg

=====================
Installation Mode
=====================
Installation Path     : /home/sn/prg/Carrera_Race_Monitor (exists)
Service Status Server : crm_server.service (running, will be stopped)
Service Status Client : crm_client.service (running, will be stopped)

A Carrera_Race_Monitor installation exists already.

Do you want to skip update of Carrera_Race_Monitor and software stack and only reconfigure the services[Y/n]:

```

Replying with "n" will now
- Stop running services
- Run through the complete installation procedure, updating Carrera Race Monitor as well as required packages to the latest version
- Remove and reinstall the services.

## Uninstall

For uninstalling Carrera Race Monitor, run

```
bash <(curl -fsSL https://raw.githubusercontent.com/signag/Carrera_Race_Monitor/main/scripts/uninstall_Carrera_Race_Monitor.sh)
```