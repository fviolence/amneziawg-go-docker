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
  awg-quick down $INTERFACE || true
  exit 0
}
trap cleanup SIGTERM SIGINT

# Generate the default configuration if not present
if [ ! -f "$CONFIG_FILE" ]; then
  echo "Using IP: $IP, Port: $PORT, Interface: $INTERFACE"
  echo "Generating AmneziaWG configuration with ip $IP and port $PORT..."
  python3 /etc/amnezia/awgcfg.py --make $CONFIG_FILE -i $IP -p $PORT --tun $INTERFACE
else
  echo "Loading AmneziaWG configuration $CONFIG_FILE..."
  python3 /etc/amnezia/awgcfg.py --ldconf $CONFIG_FILE
fi

# Generate config template
echo "Generating AmneziaWG configuration template..."
python3 /etc/amnezia/awgcfg.py --create

# Start the AmneziaWG interface
echo "Starting AmneziaWG interface: $INTERFACE..."
awg-quick up $INTERFACE

echo "All done!"

# Start tail in the background
tail -f /dev/null &
TAIL_PID=$!
# Wait in the shell foreground so it can receive signals
wait $TAIL_PID