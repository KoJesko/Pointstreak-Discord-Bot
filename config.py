import os
from pathlib import Path
from typing import List

try:
	# Load variables from a local .env file if present (development convenience)
	from dotenv import load_dotenv  # type: ignore
	load_dotenv()
except Exception:
	# python-dotenv is optional for production; environment can be provided by the host
	pass

def _getenv_int(name: str, default: int | None = None) -> int | None:
	val = os.getenv(name)
	if val is None or val == "":
		return default
	try:
		return int(val)
	except ValueError:
		return default

def _getenv_int_list(name: str, default: List[int] | None = None) -> List[int]:
	raw = os.getenv(name, "").strip()
	if not raw:
		return default or []
	out: List[int] = []
	for part in raw.split(','):
		part = part.strip()
		if not part:
			continue
		try:
			out.append(int(part))
		except ValueError:
			continue
	return out

# --- DISCORD CONFIGURATION ---
# Read the bot token from environment; do not provide a hardcoded default.
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

# The Discord channel ID where the admin-autoplanned games will be pinned.
# Set via environment ADMIN_CHANNEL_ID or leave unset to disable channel-restricted admin commands.
ADMIN_CHANNEL_ID = _getenv_int("ADMIN_CHANNEL_ID") or 0

# --- SCRAPING CONFIGURATION ---

# Base URL for Pointstreak games. 
BASE_URL = "https://baseball.pointstreak.com"

# Template for getting a game's boxscore/play-by-play. The {game_id} must be replaced.
GAME_URL_TEMPLATE = f"{BASE_URL}/boxscore.html?gameid="

# URL template to scrape a team's upcoming schedule to find the current live game ID.
TEAM_SCHEDULE_URL_TEMPLATE = f"{BASE_URL}/team_scoreboard.html?teamid="

# NEW: URL template to scrape an entire league's scoreboard to get team IDs/Names (for /import_teams)
# Replace {league_id} with the ID of the league (e.g., Frontier League's ID).
LEAGUE_SCOREBOARD_URL_TEMPLATE = f"{BASE_URL}/scoreboard.html?leagueid="

# How often the bot checks for new plays (in seconds). 30 seconds is generally safe.
POLLING_INTERVAL_SECONDS = 30

# The crucial CSS selector for finding the play-by-play entries.
# NOTE: YOU MUST INSPECT A LIVE GAME TO FIND THE CORRECT CLASS/TAG.
CSS_SELECTOR = "table.boxscore-table tr.play-by-play-row" 

# --- PERSISTENCE CONFIGURATION ---

# File to store the list of games that admins have chosen to auto-plan/pin.
AUTOPLAN_FILE = Path("autoplan_games.json")

# File to store user-submitted predictions for fantasy-style betting.
PREDICTION_FILE = Path("user_predictions.json")

# NEW: File to store the Team ID -> Team Name mapping scraped via /import_teams.
TEAMS_FILE = Path("teams_data.json")

# Discord guild/server IDs used for fast per-guild command sync at startup (optional).
# Provide a comma-separated list in env GUILD_IDS, e.g., "123,456". Leave empty to auto-sync for all connected guilds.
GUILD_IDS = _getenv_int_list("GUILD_IDS", default=[]) 

# List of TEAM IDs (optional defaults). Can also be supplied by another config mechanism later.
AUTOPLAN_TEAM_IDS = [164977]

