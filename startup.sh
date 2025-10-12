#!/bin/bash

# This script is executed by systemd to launch the bot.
# It ensures the correct virtual environment is activated before running the main script.

# Navigate to the bot's working directory.
# This assumes the script is executed from the directory defined in the systemd service file (WorkingDirectory=).
cd "$(dirname "$0")"

# 1. Activate the virtual environment
# The source command is necessary to correctly set up the environment variables (like PATH).
source ./.venv/bin/activate

# 2. Load environment variables from .env if present (development convenience)
if [ -f ./.env ]; then
	# shellcheck disable=SC2046
	export $(grep -v '^#' ./.env | xargs -d '\n')
fi

# 3. Execute the main Python bot script
# Use the python executable within the activated environment.
exec python main_bot.py
