#!/bin/bash

set -o errexit

/home/pi/Documents/acropolis/%VERSION%/.venv/bin/python /home/pi/Documents/acropolis/%VERSION%/cli/main.py $*
