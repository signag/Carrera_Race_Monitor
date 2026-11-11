#!/bin/bash
set -e

################################################
# Carrera_Race_Monitor Installer + systemd setup
################################################
echo
echo "==================================================="
echo "=== Carrera_Race_Monitor Automated Installer    ==="
echo "===                                             ==="
echo "=== Exit at any step with Ctrl+C                ==="
echo "==================================================="

USER_NAME="$USER"
INSTALL_ROOT="$HOME/prg"
INSTALL_DIR="$INSTALL_ROOT/Carrera_Race_Monitor"
REPO_URL="https://github.com/signag/Carrera_Race_Monitor.git"
SERVICE_PORT=5100
HOSTNAME="$(hostname)"
UPDATE_INSTALL=true
INSTALL_SERVICES=false

##############################################
# Detect Raspberry Pi Model
##############################################
RPI_MODEL=$(tr -d '\0' < /proc/device-tree/model)
if [[ "$RPI_MODEL" == "Raspberry Pi Zero"* ]]; then
    RPI_MODEL_ZERO=true
    if [[ "$RPI_MODEL" == "Raspberry Pi Zero 2"* ]]; then
        RPI_MODEL_ZERO_1=false
    else
        RPI_MODEL_ZERO_1=true
    fi
else
    RPI_MODEL_ZERO=false
    RPI_MODEL_ZERO_1=false
fi

##############################################
# Detect OS version and check for full version
##############################################
OS_CODENAME=$(grep VERSION_CODENAME /etc/os-release | cut -d= -f2)

if dpkg -l | grep -q raspberrypi-ui-mods || \
   dpkg -l | grep -q lxsession || \
   [[ -d /usr/share/xsessions ]]; then
    OS_VARIANT="full"
else
    OS_VARIANT="lite"
    IS_LITE=true
fi
echo
echo "RPI Model           : $RPI_MODEL"
echo "Detected OS codename: $OS_CODENAME $OS_VARIANT"
echo "Hostname            : $HOSTNAME"
echo
echo "Running as user     : $USER_NAME"
echo "Installing at       : $INSTALL_ROOT"

##############################################
# Check crm_server service
##############################################
SERVICE_srv="crm_server.service"
SERVICE_srv_CONFIGURED=false
SERVICE_srv_RUNNING=false
SERVICE_srv_USER=false
SERVICE_srv_ENABLED=false

if systemctl --user cat "$SERVICE_srv" >/dev/null 2>&1; then
    SERVICE_srv_USER=true
    SERVICE_srv_CONFIGURED=true

    if systemctl --user is-enabled --quiet "$SERVICE_srv"; then
        SERVICE_srv_ENABLED=true
    fi

    if systemctl --user is-active --quiet "$SERVICE_srv"; then
        SERVICE_srv_RUNNING=true
    fi
fi

if [[ "$SERVICE_srv_USER" == false ]]; then
    if systemctl cat "$SERVICE_srv" >/dev/null 2>&1; then
        SERVICE_srv_CONFIGURED=true

        if systemctl is-enabled --quiet "$SERVICE_srv"; then
            SERVICE_srv_ENABLED=true
        fi

        if systemctl is-active --quiet "$SERVICE_srv"; then
            SERVICE_srv_RUNNING=true
        fi
    fi
fi

##############################################
# Check crm_client service
##############################################
SERVICE_clt="crm_client.service"
SERVICE_clt_CONFIGURED=false
SERVICE_clt_RUNNING=false
SERVICE_clt_USER=false
SERVICE_clt_ENABLED=false

if systemctl --user cat "$SERVICE_clt" >/dev/null 2>&1; then
    SERVICE_clt_USER=true
    SERVICE_clt_CONFIGURED=true

    if systemctl --user is-enabled --quiet "$SERVICE_clt"; then
        SERVICE_clt_ENABLED=true
    fi

    if systemctl --user is-active --quiet "$SERVICE_clt"; then
        SERVICE_clt_RUNNING=true
    fi
fi

if [[ "$SERVICE_clt_USER" == false ]]; then
    if systemctl cat "$SERVICE_clt" >/dev/null 2>&1; then
        SERVICE_clt_CONFIGURED=true

        if systemctl is-enabled --quiet "$SERVICE_clt"; then
            SERVICE_clt_ENABLED=true
        fi

        if systemctl is-active --quiet "$SERVICE_clt"; then
            SERVICE_clt_RUNNING=true
        fi
    fi
fi

############################################
# Ask user about Installation Mode
############################################
if [[ -d "$INSTALL_DIR" ]]; then
    INSTALL_SERVICES=true
    echo
    echo "====================="
    echo "Installation Mode"
    echo "====================="
    echo "Installation Path     : $INSTALL_DIR (exists)"
    if [[ "$SERVICE_srv_RUNNING" == true ]]; then
        echo "Service Status Server : $SERVICE_srv (running, will be stopped)"
    elif [[ "$SERVICE_srv_CONFIGURED" == true ]]; then
        echo "Service Status Server : $SERVICE_srv (configured, not running)"
    else
        echo "Service Status Server : $SERVICE_srv (not configured)"
    fi
    if [[ "$SERVICE_clt_RUNNING" == true ]]; then
        echo "Service Status Client : $SERVICE_clt (running, will be stopped)"
    elif [[ "$SERVICE_clt_CONFIGURED" == true ]]; then
        echo "Service Status Client : $SERVICE_clt (configured, not running)"
    else
        echo "Service Status Client : $SERVICE_clt (not configured)"
    fi
    echo
    echo "A Carrera_Race_Monitor installation exists already."
    echo
    read -rp "Do you want to skip update of Carrera_Race_Monitor and software stack and only reconfigure the services[Y/n]: " MODE_CHOICE
    echo

    MODE_CHOICE=${MODE_CHOICE,,}   # normalize to lowercase

    if [[ "$MODE_CHOICE" == "n" ]]; then
        UPDATE_INSTALL=true
        echo
        echo "Updating repository and software for existing installation"
    else
        UPDATE_INSTALL=false
        echo
        echo "Only installing/replacing services for existing installation"
    fi
else
    INSTALL_SERVICES=false
    echo
    echo "================="
    echo "Installation Mode"
    echo "================="
    echo "Installation Path     : $INSTALL_DIR (will be created)"
    echo
    echo "This is the first installation of Carrera_Race_Monitor on this system."
    echo "Services will not be installed to allow manual device tests during system assembly."
    echo "After successful device tests, you can run the installer again to configure and start the services."
fi

############################################
# Ask user about defaults
############################################
USE_DEFAULTS=true

############################################
# Request start confirmation
############################################
echo
read -rp "No more questions! Ready to start installation? [Y/n]: " START_CHOICE
START_CHOICE=${START_CHOICE,,}
if [[ "$START_CHOICE" == "n" ]]; then
    echo
    echo "================================================="
    echo "=== Carrera_Race_Monitor installation aborted ==="
    echo "================================================="
    exit 1
fi

############################################
# Stop running services before proceeding
############################################
if [[ "$SERVICE_srv_RUNNING" == true ]]; then
    echo
    echo "Stopping running service '$SERVICE_srv'..."
    if [[ "$SERVICE_srv_USER" == true ]]; then
        systemctl --user stop "$SERVICE_srv"
        if systemctl --user is-active --quiet "$SERVICE_srv"; then
            echo
            echo "Failed to stop user service '$SERVICE_srv'." 
            echo "Please check the service status and stop it manually before running the installer again."
            exit 1
        else
            echo
            echo "User service '$SERVICE_srv' stopped successfully."
        fi
    else
        sudo systemctl stop "$SERVICE_srv"
        if systemctl is-active --quiet "$SERVICE_srv"; then
            echo
            echo "Failed to stop system service '$SERVICE_srv'." 
            echo "Please check the service status and stop it manually before running the installer again."
            exit 1
        else
            echo
            echo "System service '$SERVICE_srv' stopped successfully."
        fi
    fi
fi

if [[ "$SERVICE_clt_RUNNING" == true ]]; then
    echo
    echo "Stopping running service '$SERVICE_clt'..."
    if [[ "$SERVICE_clt_USER" == true ]]; then
        systemctl --user stop "$SERVICE_clt"
        if systemctl --user is-active --quiet "$SERVICE_clt"; then
            echo
            echo "Failed to stop user service '$SERVICE_clt'." 
            echo "Please check the service status and stop it manually before running the installer again."
            exit 1
        else
            echo
            echo "User service '$SERVICE_clt' stopped successfully."
        fi
    else
        sudo systemctl stop "$SERVICE_clt"
        if systemctl is-active --quiet "$SERVICE_clt"; then
            echo
            echo "Failed to stop system service '$SERVICE_clt'." 
            echo "Please check the service status and stop it manually before running the installer again."
            exit 1
        else
            echo
            echo "System service '$SERVICE_clt' stopped successfully."
        fi
    fi
fi

############################################
# Create root directory
############################################
echo
echo "Creating root directory ..."
if [[ -d "$INSTALL_ROOT" ]]; then
    echo "Root directory exists already: $INSTALL_ROOT"
else
    mkdir -p "$INSTALL_ROOT"
    echo "Created: $INSTALL_ROOT"
fi
cd "$INSTALL_ROOT"

############################################
# Check that git is installed
############################################
echo
echo "Checking git ..."
if command -v git >/dev/null 2>&1; then
    echo "git is installed"
else
    echo "Installing git ..."
    sudo apt install -y git
fi

############################################
# Clone/update repository
############################################
if [[ "$UPDATE_INSTALL" == true ]]; then
    echo
    if [[ ! -d "Carrera_Race_Monitor" ]]; then
        echo "Cloning Carrera_Race_Monitor ..."
        git clone --branch main --single-branch --depth 1 --filter=blob:none --sparse "$REPO_URL"
        cd Carrera_Race_Monitor
        git sparse-checkout set code config scripts
        cd ..
    else
        echo "Repository already exists — updating ..."
        cd Carrera_Race_Monitor
        git sparse-checkout set code config scripts
        git fetch origin main --depth=1
        git reset --hard origin/main
        cd ..
    fi
else
    echo
    echo "Skipping repository setup for existing installation"
fi

############################################
# Python virtual environment
############################################
echo
echo "Creating virtual environment ..."
cd Carrera_Race_Monitor
if [[ -d ".venv" ]]; then
    echo "Virtual environment exists already"
else
    python3 -m venv --system-site-packages .venv
    echo "Created: .venv"
fi

############################################
# Activate virtual environment
############################################
echo
echo "Activating virtual environment ..."
source .venv/bin/activate
echo "Virtual environment activated"
echo "$PS1"

############################################
# Install Flask
############################################
if [[ "$UPDATE_INSTALL" == true ]]; then
    echo
    echo "Installing Flask ..."
    pip install --ignore-installed "Flask>=3,<4"
    echo "Installing flask-socketio ..."
    pip install --ignore-installed "flask-socketio"
    echo "Installing flask-cors ..."
    pip install --ignore-installed "flask-cors"
else
    echo
    echo "Skipping Flask installation for existing installation"
fi

############################################
# Install gpiozero
############################################
if [[ "$UPDATE_INSTALL" == true ]]; then
    echo
    echo "Installing gpiozero ..."
    pip install "gpiozero"
else
    echo
    echo "Skipping gpiozero installation for existing installation"
fi

############################################
# Install libraries for LCD display
############################################
if [[ "$UPDATE_INSTALL" == true ]]; then
    echo
    echo "Installing libraries for LCD display ..."
    sudo apt install -y python3-smbus i2c-tools
    pip install RPLCD --break-system-packages
else
    echo
    echo "Skipping libraries for LCD display installation for existing installation"
fi

############################################
# Install I18n tooling
############################################
if [[ "$UPDATE_INSTALL" == true ]]; then
    echo
    echo "Installing I18n tools ..."
    sudo apt install -y gettext
    pip install Babel --break-system-packages
else
    echo
    echo "Skipping I18n tools installation for existing installation"
fi

############################################
# Install Messaging infrastructure
############################################
if [[ "$UPDATE_INSTALL" == true ]]; then
    echo
    echo "Installing messaging infrastructure ..."
    sudo apt install -y mosquitto mosquitto-clients
    sudo systemctl enable --now mosquitto
    pip install paho-mqtt --break-system-packages
else
    echo
    echo "Skipping messaging infrastructure installation for existing installation"
fi

#############################################
# Enable I2C interface if not already enabled
#############################################
echo
echo "Checking I2C interface status ..."
NEED_REBOOT=0
if [ "$(sudo raspi-config nonint get_i2c)" -ne 0 ]; then
    echo
    echo "Enabling I2C interface ..."
    sudo raspi-config nonint do_i2c 0
    NEED_REBOOT=1
    echo "I2C interface enabled. Reboot required."
else
    echo "I2C interface already enabled."
fi

############################################
# Leaving venv
############################################
echo
deactivate
echo "Virtual environment deactivated"
echo "$PS1"

############################################
# Checking port
############################################
echo
echo "Checking Flask service port ..."

ok=false
while [[ "$ok" != true ]]; do
    echo "Trying port $SERVICE_PORT ..."
    if ss -tulpn | grep -q ":$SERVICE_PORT\b"; then
        SERVICE_PORT=$((SERVICE_PORT + 1))
    else
        ok=true
    fi
done
echo "Using port $SERVICE_PORT"

############################################
# Cleanup existing services
############################################
if [[ "$SERVICE_srv_CONFIGURED" == true ]]; then
    echo
    echo "Cleaning up existing server service before reinstalling ..."
fi

if [[ "$SERVICE_srv_USER" == true ]]; then
    if [[ "$SERVICE_srv_ENABLED" == true ]]; then
        systemctl --user disable "$SERVICE_srv" >/dev/null 2>&1
        echo "User service '$SERVICE_srv' disabled."
    fi
    if [[ "$SERVICE_srv_CONFIGURED" == true ]]; then
        SERVICE_FILE="$HOME/.config/systemd/user/$SERVICE_srv"
        rm "$SERVICE_FILE"
        echo "User service '$SERVICE_srv' configuration removed."
    fi
fi

if [[ "$SERVICE_srv_USER" == false ]]; then
    if [[ "$SERVICE_srv_ENABLED" == true ]]; then
        sudo systemctl disable "$SERVICE_srv" >/dev/null 2>&1
        echo "System service '$SERVICE_srv' disabled."
    fi
    if [[ "$SERVICE_srv_CONFIGURED" == true ]]; then
        SERVICE_FILE="/etc/systemd/system/$SERVICE_srv"
        sudo rm "$SERVICE_FILE"
        echo "System service '$SERVICE_srv' configuration removed."
    fi
fi
if [[ "$SERVICE_srv_CONFIGURED" == true ]]; then
    echo
    echo "Cleaning up existing server service before reinstalling ..."
fi

if [[ "$SERVICE_clt_USER" == true ]]; then
    if [[ "$SERVICE_clt_ENABLED" == true ]]; then
        systemctl --user disable "$SERVICE_clt" >/dev/null 2>&1
        echo "User service '$SERVICE_clt' disabled."
    fi
    if [[ "$SERVICE_clt_CONFIGURED" == true ]]; then
        SERVICE_FILE="$HOME/.config/systemd/user/$SERVICE_clt"
        rm "$SERVICE_FILE"
        echo "User service '$SERVICE_clt' configuration removed."
    fi
fi

if [[ "$SERVICE_clt_USER" == false ]]; then
    if [[ "$SERVICE_clt_ENABLED" == true ]]; then
        sudo systemctl disable "$SERVICE_clt" >/dev/null 2>&1
        echo "System service '$SERVICE_clt' disabled."
    fi
    if [[ "$SERVICE_clt_CONFIGURED" == true ]]; then
        SERVICE_FILE="/etc/systemd/system/$SERVICE_clt"
        sudo rm "$SERVICE_FILE"
        echo "System service '$SERVICE_clt' configuration removed."
    fi
fi

############################################
# Systemd System Units
############################################
if [[ "$INSTALL_SERVICES" == true ]]; then
    echo
    # Server service
    echo
    echo "Installing '$SERVICE_srv' as system service ..."

    SERVICE_FILE="/etc/systemd/system/$SERVICE_srv"

    if [[ -f "$SERVICE_FILE" ]]; then
        sudo rm "$SERVICE_FILE"
        echo "Existing service file removed: $SERVICE_FILE"
    fi
    sudo tee "$SERVICE_FILE" >/dev/null <<EOF
[Unit]
Description=$SERVICE_srv
After=network.target

[Service]
ExecStart=$INSTALL_ROOT/Carrera_Race_Monitor/.venv/bin/python code/crm_server.py
Environment="PATH=$INSTALL_ROOT/Carrera_Race_Monitor/.venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
WorkingDirectory=$INSTALL_ROOT/Carrera_Race_Monitor
StandardOutput=inherit
StandardError=inherit
Restart=always

[Install]
WantedBy=default.target
EOF

    sudo systemctl daemon-reload
    sudo systemctl enable "$SERVICE_srv" >/dev/null 2>&1
    sudo systemctl start "$SERVICE_srv"

    echo "System service '$SERVICE_srv' installed and started."

    # Client Service
    echo
    echo "Installing '$SERVICE_clt' as system service ..."

    SERVICE_FILE="/etc/systemd/system/$SERVICE_clt"

    if [[ -f "$SERVICE_FILE" ]]; then
        sudo rm "$SERVICE_FILE"
        echo "Existing service file removed: $SERVICE_FILE"
    fi
    sudo tee "$SERVICE_FILE" >/dev/null <<EOF
[Unit]
Description=$SERVICE_clt
After=network.target

[Service]
ExecStart=$INSTALL_ROOT/Carrera_Race_Monitor/.venv/bin/python code/crm_client.py
Environment="PATH=$INSTALL_ROOT/Carrera_Race_Monitor/.venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
WorkingDirectory=$INSTALL_ROOT/Carrera_Race_Monitor
StandardOutput=inherit
StandardError=inherit
Restart=always

[Install]
WantedBy=default.target
EOF

    sudo systemctl daemon-reload
    sudo systemctl enable "$SERVICE_clt" >/dev/null 2>&1
    sudo systemctl start "$SERVICE_clt"

    echo "System service '$SERVICE_clt' installed and started."
else
    echo
    echo "Services installation skipped."
    echo "This allows manual device tests during system assembly."
    echo "After assembly and successful device tests rerun this installer to install the services."
    echo "For details refer to CRM_Assembly_Instructions.pdf" 
fi

if [[ "$NEED_REBOOT" == true ]]; then
    echo
    echo "A system reboot is required to complete the installation."
fi
