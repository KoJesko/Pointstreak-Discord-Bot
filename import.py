import subprocess
import sys
import venv
import os
from pathlib import Path

# --- Configuration ---
VENV_DIR = ".venv"
REQUIRED_PACKAGES = [
    "discord.py",
    "requests",
    "beautifulsoup4",
    "lxml",  # Faster HTML parsing
]

print("--- Starting Environment Setup for Pointstreak Bot ---")

# 1. Create the Virtual Environment
venv_path = Path(VENV_DIR)
if not venv_path.exists():
    print(f"-> Creating isolated virtual environment in {VENV_DIR}...")
    try:
        venv.create(VENV_DIR, with_pip=True)
        print("✅ Virtual environment created successfully.")
    except Exception as e:
        print(f"❌ CRITICAL ERROR: Failed to create virtual environment. Details: {e}")
        sys.exit(1)
else:
    print(f"-> Virtual environment directory {VENV_DIR} already exists. Skipping creation.")

# Determine the correct python executable path within the venv
if sys.platform == "win32":
    VENV_PYTHON = venv_path / "Scripts" / "python.exe"
else:
    VENV_PYTHON = venv_path / "bin" / "python"

# 2. Explicitly Bootstrap and Upgrade pip (Critical fix for some Linux systems)
print("-> Ensuring pip is fully bootstrapped and upgraded (FOSS stability check)...")
try:
    # Use the ensurepip module to guarantee pip exists
    subprocess.check_call([str(VENV_PYTHON), '-m', 'ensurepip', '--upgrade'])
    # Upgrade pip using the venv's python executable
    subprocess.check_call([str(VENV_PYTHON), '-m', 'pip', 'install', '--upgrade', 'pip'])
    print("✅ Pip is upgraded and ready.")
except subprocess.CalledProcessError as e:
    print(f"❌ Warning: Could not fully bootstrap or upgrade pip. Proceeding anyway. Error: {e}")

# 3. Install Required Packages
print(f"-> Installing {len(REQUIRED_PACKAGES)} packages: {', '.join(REQUIRED_PACKAGES)}...")
try:
    subprocess.check_call([
        str(VENV_PYTHON),
        '-m',
        'pip',
        'install',
        *REQUIRED_PACKAGES
    ])
    print("✅ All required packages installed successfully.")

except subprocess.CalledProcessError as e:
    print(f"❌ CRITICAL ERROR: Failed to install one or more packages.")
    print(f"Error details: {e}")
    print(f"Attempted command: {e.cmd}")
    sys.exit(1)

# 4. Final Instructions
print("\n--- Installation Script Finished ---")
print("🚀 Setup complete. To activate your isolated environment and run the bot, use the following commands:")
if sys.platform == "win32":
    print(f"   1. {VENV_DIR}\Scripts\activate")
    print(f"   2. python main_bot.py")
else:
    print(f"   1. source ./{VENV_DIR}/bin/activate")
    print(f"   2. python main_bot.py")

