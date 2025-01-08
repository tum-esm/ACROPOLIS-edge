#!/bin/bash

set -o errexit

echo "Removing old mypy cache"
rm -rf .mypy_cache 

# *********************************************************
# sensor code

echo "Checking main.py"
mypy src/main.py

# *********************************************************
# other

echo "Checking scripts/"
mypy scripts/

echo "Checking tests/"
mypy tests/
