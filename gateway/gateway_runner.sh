#!/bin/bash

echo "Removing old virtual environment and creating a new one"
rm -rf .venv
python3.12 -m venv --copies .venv
source .venv/bin/activate

echo "Installing dependencies in the virtual environment"
pip install -r requirements.txt

echo "Running the gateway"
python src/main.py $@
