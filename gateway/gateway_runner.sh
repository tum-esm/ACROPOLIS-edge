#!/bin/bash

args="$@"
echo "Args: $args"

# Expect the host filesystem to be mounted at /host
chroot /host /bin/bash <<EOT

cd $ACROPOLIS_GATEWAY_DIR

echo "Removing old virtual environment and creating a new one"
rm -rf .venv
python3.12 -m venv --copies .venv
source .venv/bin/activate

echo "Installing dependencies in the virtual environment"
pip install -r requirements.txt

echo "Running the gateway"
echo "Args: $args"
python -u src/main.py $args