#!/bin/bash

args="$@"
echo "Args: $args"

# Expect the host filesystem to be mounted at /host
chroot /host /bin/bash <<EOT

cd $ACROPOLIS_GATEWAY_DIR

echo "Removing old virtual environment and creating a new one"
rm -rf .venv
python3.13 -m venv --copies .venv
source .venv/bin/activate

echo "Installing dependencies in the virtual environment"
if ! pip install --find-links="~/.python-cache" --cache-dir="~/.python-cache" --no-index -r requirements.txt; then
    echo "Failed to install dependencies from local cache, downloading and installing from PyPI"
    pip download --cache-dir="~/.python-cache" -d "~/.python-cache" -r requirements.txt
    pip install --find-links="~/.python-cache" --cache-dir="~/.python-cache" --no-index -r requirements.txt
else
    echo "Dependencies installed from local cache"
fi

echo "Running the gateway"
echo "Args: $args"
python -u src/main.py $args