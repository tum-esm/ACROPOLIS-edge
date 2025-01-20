#!/bin/bash

set -o errexit  # Exit on any command failure
set -o nounset  # Treat unset variables as an error
set -o pipefail # Catch errors in pipelines

# Get the absolute path of the script's parent directory
SCRIPT_DIR=$(dirname "$(realpath "$0")")

# Navigate to the project root (controller/)
cd "$SCRIPT_DIR/.." || exit 1

echo "Removing old mypy cache..."
rm -rf .mypy_cache

# Dynamically set MYPYPATH to the src directory
export MYPYPATH="$PWD/src"
echo "MYPYPATH set to: $MYPYPATH"

echo "Checking files in src/ using mypy..."
mypy --explicit-package-bases src/

echo "Mypy check completed successfully!"