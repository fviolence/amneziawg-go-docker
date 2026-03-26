#!/bin/bash
set -e

CONFIG_FILE="/etc/amnezia/amneziawg/awg0.conf"

# Use environment variables
IP="${AMNEZIAWG_IP:-10.9.9.1/24}"
PORT="${AMNEZIAWG_PORT:-49666}"
INTERFACE="${AMNEZIAWG_INTERFACE:-awg0}"

# Trap SIGTERM (Docker stop) or SIGINT, then bring down awg0
cleanup() {
  echo "Caught stop signal, bringing down $INTERFACE..."
  awg-quick down "$INTERFACE" || true
  pkill -f "^amneziawg-go ${INTERFACE}$" 2>/dev/null || true
  ip link del dev "$INTERFACE" 2>/dev/null || true
  exit 0
}
trap cleanup SIGTERM SIGINT

# Generate the default configuration if not present
if [ ! -f "$CONFIG_FILE" ]; then
  echo "Using IP: $IP, Port: $PORT, Interface: $INTERFACE"
  echo "Generating AmneziaWG configuration with ip $IP and port $PORT..."
  python3 /usr/local/bin/awgcfg.py --make $CONFIG_FILE -i $IP -p $PORT --tun $INTERFACE
else
  echo "Loading AmneziaWG configuration $CONFIG_FILE..."
  python3 /usr/local/bin/awgcfg.py --ldconf $CONFIG_FILE
fi

chmod 600 "$CONFIG_FILE" || true

# Generate config template only if missing
if [ ! -f /etc/amnezia/_defclient.config ]; then
  echo "Generating AmneziaWG configuration template..."
  python3 /usr/local/bin/awgcfg.py --create
fi

# Start the AmneziaWG interface
echo "Starting AmneziaWG interface: $INTERFACE..."
awg-quick up $INTERFACE

echo "All done!"

# Start tail in the background
tail -f /dev/null &
TAIL_PID=$!
# Wait in the shell foreground so it can receive signals
wait $TAIL_PID