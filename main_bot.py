import discord
from discord.ext import tasks, commands
from bs4 import BeautifulSoup
import requests
import json
import asyncio
import time
import random 
from pathlib import Path 
from config import (
    DISCORD_TOKEN, 
    ADMIN_CHANNEL_ID, 
    GAME_URL_TEMPLATE, 
    POLLING_INTERVAL_SECONDS, 
    CSS_SELECTOR,
    AUTOPLAN_FILE,
    PREDICTION_FILE,
    GUILD_IDS,
    AUTOPLAN_TEAM_IDS,
    TEAM_SCHEDULE_URL_TEMPLATE,
    TEAMS_FILE,
    LEAGUE_SCOREBOARD_URL_TEMPLATE
)
from discord import app_commands, Embed, Color, utils

# Initialize the command Bot and intents
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True 
intents.reactions = True 
bot = commands.Bot(command_prefix='!', intents=intents)

# --- State Management and Persistence ---
active_game_trackers = {} 

# --- App Commands Error Handling ---
@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        missing = ', '.join(error.missing_permissions)
        try:
            await interaction.response.send_message(
                f"You’re missing required permissions to use this command: {missing}.",
                ephemeral=True
            )
        except discord.InteractionResponded:
            await interaction.followup.send(
                f"You’re missing required permissions to use this command: {missing}.",
                ephemeral=True
            )
        return
    if isinstance(error, app_commands.CheckFailure):
        try:
            await interaction.response.send_message(
                "You don’t have permission to use this command in this channel.",
                ephemeral=True
            )
        except discord.InteractionResponded:
            await interaction.followup.send(
                "You don’t have permission to use this command in this channel.",
                ephemeral=True
            )
        return
    # Fallback: log and notify
    print(f"App command error: {type(error).__name__}: {error}")
    try:
        await interaction.response.send_message(
            "An error occurred while running this command.", ephemeral=True
        )
    except discord.InteractionResponded:
        await interaction.followup.send(
            "An error occurred while running this command.", ephemeral=True
        )

def load_autoplans():
    """Loads auto-planned games from the JSON file."""
    if AUTOPLAN_FILE.exists():
        with open(AUTOPLAN_FILE, 'r') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}
    return {}

def save_autoplans(data):
    """Saves auto-planned games to the JSON file."""
    with open(AUTOPLAN_FILE, 'w') as f:
        json.dump(data, f, indent=4)

def load_predictions():
    """Loads user predictions from the JSON file."""
    if PREDICTION_FILE.exists():
        with open(PREDICTION_FILE, 'r') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}
    return {}

def save_predictions(data):
    """Saves user predictions to the JSON file."""
    with open(PREDICTION_FILE, 'w') as f:
        json.dump(data, f, indent=4)

def load_teams():
    """Loads the stored team name/ID mapping."""
    if TEAMS_FILE.exists():
        with open(TEAMS_FILE, 'r') as f:
            try:
                # Key is team_id (str), Value is team_name (str)
                return {int(k): v for k, v in json.load(f).items()}
            except json.JSONDecodeError:
                return {}
            except ValueError:
                return {}
    return {}

def save_teams(data):
    """Saves the team name/ID mapping."""
    # Ensure keys are strings for JSON
    with open(TEAMS_FILE, 'w') as f:
        json.dump({str(k): v for k, v in data.items()}, f, indent=4)


# --- Scraping Logic ---

def find_live_game_id(team_id: int) -> tuple[str, str, str, str]: 
    """
    Scrapes the team scoreboard to find the active live game ID and opponent.
    
    NOTE: The placeholder scraping logic must be inspected against a real Pointstreak page.
    Returns: (game_id, team_name, opponent_name, full_name) or (None, None, None, None)
    """
    url = f"{TEAM_SCHEDULE_URL_TEMPLATE}{team_id}"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'}
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
    except requests.exceptions.RequestException:
        return None, None, None, None

    soup = BeautifulSoup(response.text, 'lxml')
    
    # --- PLACEHOLDER LOGIC: Targets a link associated with a live or in-progress game ---
    # This selector needs to be specific to a row or element indicating a game is current.
    live_game_link = soup.find('a', string=lambda t: t and ('live' in t.lower() or 'in progress' in t.lower()))
    
    if live_game_link and 'gameid=' in live_game_link['href']:
        game_id = live_game_link['href'].split('gameid=')[-1].split('&')[0]
        
        team_name = load_teams().get(team_id, f"Team {team_id}")
        
        # Simplified assumption for opponent extraction (highly dependent on HTML structure)
        opponent_cell = live_game_link.find_next_sibling('td') 
        opponent_name = opponent_cell.text.strip() if opponent_cell else "Unknown Opponent"

        full_name = f"{team_name} vs {opponent_name}"
        return game_id, team_name, opponent_name, full_name

    return None, None, None, None


def get_latest_play(game_id: str) -> tuple[str, str, str, bool, int, int, bool, bool, int]:
    """
    CORE SCRAPING FUNCTION: Fetches latest play, scores, and resolution metrics.
    
    !!! The selectors and parsing logic here are placeholders and MUST BE CUSTOMIZED. !!!
    """
    url = f"{GAME_URL_TEMPLATE}{game_id}"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'}
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"Scraping Error for Game {game_id}: {e}")
        return f"Error connecting to Pointstreak: {e}", "Error", "", False, 0, 0, False, False, 0 

    soup = BeautifulSoup(response.text, 'lxml')
    
    # --- SCORE and STATUS Scraping (Placeholders) ---
    home_score_element = soup.find('span', class_='home-score') 
    away_score_element = soup.find('span', class_='away-score') 
    
    try:
        home_score = int(home_score_element.text.strip()) if home_score_element else 0
        away_score = int(away_score_element.text.strip()) if away_score_element else 0
    except ValueError:
        home_score, away_score = 0, 0 

    status_element = soup.find('span', class_='game-status') 
    score_element = soup.find('div', class_=['final-score', 'current-score']) 
    
    game_status = status_element.text.strip() if status_element else "In Progress"
    final_score_text = score_element.text.strip() if score_element else f"{away_score}-{home_score}"
    is_game_over = "final" in game_status.lower() or "over" in game_status.lower()

    # --- RESOLUTION METRICS Scraping (Placeholders) ---
    pitcher_relief_occurred = bool(soup.find(text=lambda t: t and 'pitching change' in t.lower()))
    relief_inning = 0
    
    if pitcher_relief_occurred:
        # This is where detailed PBP scraping logic goes to find the inning number of the FIRST change
        relief_inning_element = soup.find('span', class_='first-relief-inning') 
        try:
            relief_inning = int(relief_inning_element.text.strip()) if relief_inning_element else 1
        except ValueError:
            relief_inning = 1
    
    is_shutout = (home_score > 0 and away_score == 0) or (away_score > 0 and home_score == 0)
    
    # --- Play-by-Play Scraping (Using CSS_SELECTOR from config.py) ---
    play_elements = soup.select(CSS_SELECTOR) 
    
    if not play_elements:
        return f"Current Score: {final_score_text} | Status: {game_status}", game_status, final_score_text, is_game_over, home_score, away_score, pitcher_relief_occurred, is_shutout, relief_inning

    latest_play = play_elements[-1].text.strip().replace('\n', ' ').replace('\r', '')
    
    return latest_play, game_status, final_score_text, is_game_over, home_score, away_score, pitcher_relief_occurred, is_shutout, relief_inning


# --- Prediction Resolution Logic ---

def resolve_predictions(game_id: str, home_score: int, away_score: int, is_shutout: bool, relief_inning: int, poll_data: dict = None, random_resolution: bool = False) -> Embed:
    """
    Calculates fantasy prediction results.
    """
    
    user_votes = poll_data.get('votes', {}) if poll_data else {}
    game_predictions = load_predictions().get(game_id, {})

    all_user_ids = set(game_predictions.keys())
    all_user_ids.update(user_votes.keys())
    
    if not all_user_ids:
        return Embed(title="❌ No Predictions Submitted", description="The game finished, but no predictions were recorded.", color=Color.red())

    total_runs = home_score + away_score
    results = []
    
    POSSIBLE_OUTCOMES = {
        'winner': ['Home', 'Away'],
        'shutout': ['Yes', 'No'],
        'relief_timing': ['None', 'Next Inning', 'Early', 'Mid', 'Late'],
        'over_under': ['Over 9.5', 'Under 9.5'],
        'pitch_speed': ['Fast', 'Slow']
    }

    if random_resolution:
        actual_results = {
            'winner': random.choice(POSSIBLE_OUTCOMES['winner']),
            'shutout': random.choice(POSSIBLE_OUTCOMES['shutout']),
            'relief_timing': random.choice(POSSIBLE_OUTCOMES['relief_timing']),
            'over_under': random.choice(POSSIBLE_OUTCOMES['over_under']),
            'pitch_speed': random.choice(POSSIBLE_OUTCOMES['pitch_speed']),
            'total_runs_display': 'N/A (Random)',
            'relief_display': 'Random'
        }
    else:
        actual_relief_timing = "None"
        if relief_inning > 0:
            if relief_inning == 1:
                actual_relief_timing = "Next Inning"
            elif 1 <= relief_inning <= 4:
                actual_relief_timing = "Early"
            elif 5 <= relief_inning <= 7:
                actual_relief_timing = "Mid"
            elif relief_inning >= 8:
                actual_relief_timing = "Late"

        actual_results = {
            'winner': 'Home' if home_score > away_score else ('Away' if away_score > home_score else 'Tie'),
            'shutout': 'Yes' if is_shutout else 'No',
            'relief_timing': actual_relief_timing,
            'over_under': 'Over 9.5' if total_runs >= 10 else 'Under 9.5',
            'pitch_speed': random.choice(POSSIBLE_OUTCOMES['pitch_speed']), 
            'total_runs_display': total_runs,
            'relief_display': actual_relief_timing
        }


    for user_id_str in all_user_ids:
        score = 0
        correct_list = []
        
        pred = game_predictions.get(user_id_str) or user_votes.get(user_id_str)
        if not pred:
            continue

        if pred['winner'] == actual_results['winner']:
            score += 10
            correct_list.append("Winner (10)")
        
        if pred['shutout'] == actual_results['shutout']:
            score += 5
            correct_list.append("Shutout (5)")

        if pred['relief_timing'] == actual_results['relief_timing']:
            score += 10
            correct_list.append(f"Relief Timing ({actual_results['relief_timing']}) (10)")

        if pred['over_under'] == actual_results['over_under']:
            score += 10
            correct_list.append("Total Runs (O/U) (10)")

        if pred['pitch_speed'] == actual_results['pitch_speed']:
            score += 5 
            correct_list.append("Pitch Speed (Simulated) (5)")
        
        results.append({
            'user': f"<@{user_id_str}>",
            'score': score,
            'correct': correct_list
        })

    # Format the results into a leader board message
    results.sort(key=lambda x: x['score'], reverse=True)
    
    embed_color = Color.gold() if not random_resolution else Color.purple()
    embed_title = "🏆 Prediction Battle Results 🏆 (Total Points: 40)" if not random_resolution else "🔮 Random Resolution Results 🔮"
    
    leaderboard_embed = Embed(
        title=embed_title,
        description=f"Total Runs: **{actual_results['total_runs_display']}** | Shutout: **{actual_results['shutout']}** | First Relief: **{actual_results['relief_display']}**\n",
        color=embed_color
    )
    
    rank_text = ""
    for i, res in enumerate(results):
        correct_str = ', '.join(res['correct']) if res['correct'] else 'None'
        rank_text += f"**#{i+1}:** {res['user']} — **{res['score']} Points**\n"
        rank_text += f"*{correct_str}*\n"
        
    leaderboard_embed.add_field(name="Leaderboard", value=rank_text if rank_text else "No predictions submitted.")
    
    # Remove predictions for this game after resolution
    predictions_data = load_predictions()
    if game_id in predictions_data:
        del predictions_data[game_id]
        save_predictions(predictions_data)

    return leaderboard_embed


async def sync_app_commands():
    """Sync app commands globally and to each connected guild for faster availability."""
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} global app commands.")
    except Exception as e:
        print(f"Global app command sync failed: {e}")

    # Also copy globals into each guild for immediate visibility (dev convenience)
    for guild in bot.guilds:
        try:
            bot.tree.copy_global_to(guild=guild)
            await bot.tree.sync(guild=guild)
            print(f"Synced app commands to guild: {guild.name} ({guild.id})")
        except Exception as ge:
            print(f"Guild sync failed for {guild.id}: {ge}")


@bot.event
async def on_ready():
    """Confirms the bot is logged in and starts the background tasks."""
    print(f'Logged in as {bot.user} (ID: {bot.user.id})')
    print(f'Discord.py Version: {discord.__version__}')
    print('Connected guilds: ' + ', '.join(f"{g.name}({g.id})" for g in bot.guilds))

    # Ensure slash commands are synced
    await sync_app_commands()

    autoplanned_games = load_autoplans()
    admin_channel = bot.get_channel(ADMIN_CHANNEL_ID)
    
    if admin_channel:
        for key, data in autoplanned_games.items():
            if data.get('type') == 'team':
                tracker_key = ('team', data['team_id'])
            else:
                tracker_key = ('game', data['game_id'])

            active_game_trackers[tracker_key] = {
                'game_id': data.get('game_id'), 
                'team_id': data.get('team_id'), 
                'last_play': data.get('last_play', 'START'),
                'name': data['name'],
                'teams': data.get('teams', []), 
                'poll_id': data.get('poll_id'),
                'poll_end_time': data.get('poll_end_time'), 
                'total_runs': data.get('total_runs'), 
                'relief_inning': data.get('relief_inning'), 
                'target_channel_id': admin_channel.id
            }
        print(f"Loaded {len(autoplanned_games)} autoplanned items.")
    
    live_score_tracker.start()
    
# --- Discord Commands ---

def get_tracker_data(channel_id: int):
    """Finds the active tracker data based on channel ID."""
    for key, data in active_game_trackers.items():
        if data.get('target_channel_id') == channel_id:
            return data, key
    return None, None

@bot.tree.command(name="import_teams", description="[ADMIN] Scrapes a Pointstreak League page to import all team names and IDs.")
@app_commands.default_permissions(manage_channels=True)
@app_commands.checks.has_permissions(manage_channels=True)
@app_commands.describe(league_id="The league ID (e.g., '200' for Frontier League) to scrape for teams.")
async def import_teams_command(interaction: discord.Interaction, league_id: str):
    """
    Admin command to import teams from a specified Pointstreak league ID.
    """
    await interaction.response.defer(ephemeral=True, thinking=True)
    
    url = f"{LEAGUE_SCOREBOARD_URL_TEMPLATE}{league_id}"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'}
    
    imported_teams = {}
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'lxml')
        
        # --- PLACEHOLDER SCRAPING LOGIC: Targets links with teamid in the URL ---
        team_links = soup.select('a[href*="teamid="]') 
        
        for link in team_links:
            href = link.get('href')
            team_id_match = next((s.split('teamid=')[-1].split('&')[0] for s in href.split('?') if 'teamid=' in s), None)
            team_name = link.text.strip()
            
            if team_id_match and team_name and len(team_name) > 1:
                try:
                    team_id = int(team_id_match)
                    if team_id not in imported_teams:
                        imported_teams[team_id] = team_name
                except ValueError:
                    continue 

        if not imported_teams:
            return await interaction.followup.send(f"⚠️ **Import Failed:** Could not find any team links with IDs on the specified league page. URL: <{url}>", ephemeral=True)

        save_teams(imported_teams)
        
        return await interaction.followup.send(f"✅ **Team Import Successful!** Imported **{len(imported_teams)}** teams from League ID `{league_id}`. Autoplan commands are now updated with these teams.", ephemeral=True)

    except requests.exceptions.RequestException as e:
        return await interaction.followup.send(f"❌ **Scraping Error:** Failed to fetch data from Pointstreak. Error: {e}", ephemeral=True)
    except Exception as e:
        return await interaction.followup.send(f"❌ An unexpected error occurred during import: {e}", ephemeral=True)


@bot.tree.command(name="track_game", description="Start tracking a specific Pointstreak game in a new thread.")
@app_commands.default_permissions(manage_threads=True)
@app_commands.checks.has_permissions(manage_threads=True)
@app_commands.describe(game_id="The Pointstreak game ID (e.g., '514852').", team1_name="Away Team Name.", team2_name="Home Team Name.")
async def track_game_command(interaction: discord.Interaction, game_id: str, team1_name: str, team2_name: str):
    """
    User command to dynamically start tracking a single game in a dedicated thread.
    """
    await interaction.response.defer(thinking=True)
    game_name = f"{team1_name} vs {team2_name}"
    
    try:
        thread = await interaction.channel.create_thread(
            name=f"LIVE | {game_name}",
            type=discord.ChannelType.public_thread,
            reason="Starting Pointstreak live game tracking."
        )
        
        tracker_key = thread.id
        
        active_game_trackers[tracker_key] = {
            'game_id': game_id,
            'last_play': 'START',
            'name': game_name,
            'teams': [team1_name, team2_name], 
            'poll_id': None,
            'poll_end_time': None,
            'total_runs': None, 
            'relief_inning': 0, 
            'target_channel_id': thread.id
        }

        initial_message = f"🚨 **Tracking Started!** 🚨\nWatching Game ID `{game_id}`: **{game_name}**.\nUpdates will post here every {POLLING_INTERVAL_SECONDS} seconds.\nURL: <{GAME_URL_TEMPLATE}{game_id}>"
        await thread.send(initial_message)
        await interaction.followup.send(f"Tracking thread {thread.mention} created for {game_name}!", ephemeral=True)

    except Exception as e:
        await interaction.followup.send(f"Error creating thread or starting tracking: {e}", ephemeral=True)


@bot.tree.command(name="admin_autoplan", description="[ADMIN] Add a game or team to be continuously tracked in the admin channel.")
@app_commands.default_permissions(manage_channels=True)
@app_commands.checks.has_permissions(manage_channels=True)
@app_commands.describe(team_id="Team ID for season tracking (check teams_data.json).", game_id="Specific game ID for single-game tracking.", game_name="Name of the game (required with game_id).", team1_name="Away team name (required with game_id).", team2_name="Home team name (required with game_id).")
async def admin_autoplan_command(interaction: discord.Interaction, team_id: str = None, game_id: str = None, game_name: str = None, team1_name: str = None, team2_name: str = None):
    """
    Admin command to add a single game or an entire team to the persistent tracking list.
    """
    await interaction.response.defer(ephemeral=True, thinking=True)

    # Only enforce admin channel restriction if configured
    if ADMIN_CHANNEL_ID and ADMIN_CHANNEL_ID > 0 and interaction.channel_id != ADMIN_CHANNEL_ID:
        return await interaction.followup.send("This command must be run in the designated admin channel.", ephemeral=True)
    target_channel = bot.get_channel(ADMIN_CHANNEL_ID) if (ADMIN_CHANNEL_ID and ADMIN_CHANNEL_ID > 0) else interaction.channel

    autoplanned_games = load_autoplans()
    tracker_key = None
    
    if team_id:
        # --- TEAM AUTOPLANNING ---
        try:
            team_id = int(team_id)
        except ValueError:
            return await interaction.followup.send("Team ID must be a number.", ephemeral=True)
            
        teams_data = load_teams()
        team_name = teams_data.get(team_id, f"Team {team_id}")

        tracker_key = ('team', team_id)

        autoplanned_games[str(team_id)] = {
            'type': 'team',
            'team_id': team_id,
            'name': team_name,
            'last_play': 'START',
            'teams': [team_name], 
            'poll_id': None,
            'poll_end_time': None,
            'total_runs': None,
            'relief_inning': 0, 
            'target_channel_id': target_channel.id
        }
        initial_message = f"✅ **Team Autoplan Activated!**\nNow tracking all future live games for **{team_name}** (ID: `{team_id}`)."
    elif game_id and game_name and team1_name and team2_name:
        # --- SINGLE GAME AUTOPLANNING ---
        game_name = f"{team1_name} vs {team2_name}"
        tracker_key = ('game', game_id)

        if game_id in [data.get('game_id') for data in autoplanned_games.values()]:
            return await interaction.followup.send(f"Game ID `{game_id}` is already being tracked.", ephemeral=True)

        autoplanned_games[game_id] = {
            'type': 'game',
            'game_id': game_id,
            'name': game_name,
            'last_play': 'START',
            'teams': [team1_name, team2_name],
            'poll_id': None,
            'poll_end_time': None,
            'total_runs': None,
            'relief_inning': 0, 
            'target_channel_id': target_channel.id
        }
        initial_message = f"✅ **Single Game Autoplan Activated!**\nNow continuously tracking Game ID `{game_id}`: **{game_name}**."
    else:
        return await interaction.followup.send("Invalid command usage. Provide EITHER `team_id` OR all three (`game_id`, `game_name`, `team1_name`, `team2_name`).", ephemeral=True)

    if tracker_key:
        save_autoplans(autoplanned_games)
        json_key = str(tracker_key[1]) if tracker_key[0] == 'team' else tracker_key[0]
        active_game_trackers[tracker_key] = autoplanned_games[json_key]
        await target_channel.send(initial_message)
        await interaction.followup.send(f"Successfully added tracking to the list.", ephemeral=True)
    
    return 

# NEW COMMAND: Fantasy Prediction System Poll Starter
@bot.tree.command(name="start_fantasy_poll", description="Starts a fantasy-style prediction poll for the current game.")
@app_commands.describe(
    close_in_minutes='Optional: Timer in minutes (e.g., 30) after which the poll will close regardless of game status.'
)
async def start_fantasy_poll_command(
    interaction: discord.Interaction,
    close_in_minutes: int = None
):
    """
    Creates a poll using reactions for fantasy prediction, including the new 'Relief Timing' option.
    """
    await interaction.response.defer(thinking=True)
    
    tracker_data, tracker_key = get_tracker_data(interaction.channel_id)

    if not tracker_data or not tracker_data.get('game_id') or not tracker_data.get('teams'):
        return await interaction.followup.send("This channel/thread is not tracking an active game with known teams. Start tracking first!", ephemeral=True)

    if tracker_data.get('poll_id'):
        return await interaction.followup.send("A fantasy poll is already active for this game.", ephemeral=True)

    team1, team2 = tracker_data['teams'][0], tracker_data['teams'][1]
    
    # 2. Define Poll Options and Emojis
    poll_emojis = {
        '🏆': 'Winner',
        '1️⃣': team1,
        '2️⃣': team2,
        
        '🥅': 'Shutout?',
        '✅': 'Shutout: Yes',
        '❌': 'Shutout: No',
        
        '⌚': 'Relief Timing?',
        '🇳': 'Relief: None', 
        '🔜': 'Relief: Next Inning', 
        '🇪': 'Relief: Early (1-4)',
        '🇲': 'Relief: Mid (5-7)',
        '🇱': 'Relief: Late (8+)',
        
        '📊': 'Total Runs (O/U 9.5)',
        '⬆️': 'Total Runs: Over 9.5',
        '⬇️': 'Total Runs: Under 9.5',
        
        '💨': 'Pitch Speed (>85 MPH)?',
        '🟢': 'Pitch Speed: Fast',
        '🟠': 'Pitch Speed: Slow',
    }

    poll_message_text = f"""
**🏟️ Live Fantasy Predictions for {tracker_data['name']}**
Vote for **ALL** six categories below by reacting to the corresponding emojis!

**--- Voting Categories ---**
🏆 **Winner** (1️⃣ {team1} or 2️⃣ {team2})
🥅 **Shutout?** (✅ Yes or ❌ No)
⌚ **Pitcher Relief Timing** (🇳 None, 🔜 Next Inning, 🇪 Early (1-4), 🇲 Mid (5-7), 🇱 Late (8+))
📊 **Total Runs (O/U 9.5)** (⬆️ Over or ⬇️ Under)
💨 **Pitch Speed** (🟢 Fast or 🟠 Slow - Simulated)

"""
    end_time = None
    if close_in_minutes and close_in_minutes > 0:
        end_time = int(time.time() + close_in_minutes * 60)
        poll_message_text += f"\n**🚨 This poll will close <t:{end_time}:R>!**"
    else:
        poll_message_text += "\n**🚨 This poll closes when the game goes FINAL!**"

    try:
        poll_message = await interaction.channel.send(poll_message_text)
        
        for emoji in poll_emojis.keys():
            await poll_message.add_reaction(emoji)

        active_game_trackers[tracker_key]['poll_id'] = poll_message.id
        active_game_trackers[tracker_key]['poll_end_time'] = end_time
        
        poll_options_data = {
            'winner': {'1️⃣': 'Away', '2️⃣': 'Home'}, 
            'shutout': {'✅': 'Yes', '❌': 'No'},
            'relief_timing': {'🇳': 'None', '🔜': 'Next Inning', '🇪': 'Early', '🇲': 'Mid', '🇱': 'Late'}, 
            'over_under': {'⬆️': 'Over 9.5', '⬇️': 'Under 9.5'},
            'pitch_speed': {'🟢': 'Fast', '🟠': 'Slow'}
        }
        active_game_trackers[tracker_key]['poll_options'] = poll_options_data
        
        await interaction.followup.send(f"Fantasy Poll successfully started! Vote in {poll_message.jump_url}", ephemeral=True)

    except Exception as e:
        print(f"Error creating poll: {e}")
        await interaction.followup.send(f"Failed to create the poll. Error: {e}", ephemeral=True)

@bot.tree.command(name="resolve_random", description="[ADMIN] Closes the poll and resolves results randomly. For tie games or errors.")
@app_commands.default_permissions(manage_channels=True)
@app_commands.checks.has_permissions(manage_channels=True)
async def resolve_random_command(interaction: discord.Interaction):
    """
    Admin command to force a random resolution of the active poll in the current channel/thread.
    """
    await interaction.response.defer(thinking=True)
    
    tracker_data, tracker_key = get_tracker_data(interaction.channel_id)

    if not tracker_data or not tracker_data.get('poll_id'):
        return await interaction.followup.send("No active fantasy poll found in this channel/thread to resolve.", ephemeral=True)
        
    poll_id = tracker_data['poll_id']
    current_game_id = tracker_data['game_id']

    dummy_scores = {
        'home_score': 0,
        'away_score': 0,
        'is_shutout': False,
        'relief_inning': 0
    }
    
    try:
        poll_message = await interaction.channel.fetch_message(poll_id)
        user_votes = {}
        poll_options = tracker_data.get('poll_options')
        
        for reaction in poll_message.reactions:
            if reaction.emoji in ['1️⃣', '2️⃣', '✅', '❌', '🇳', '🇪', '🇲', '🇱', '🔜', '⬆️', '⬇️', '🟢', '🟠']:
                async for user in reaction.users():
                    if user.bot: continue
                    user_id_str = str(user.id)
                    if user_id_str not in user_votes: user_votes[user_id_str] = {}
                    
                    if reaction.emoji in ['1️⃣', '2️⃣']: user_votes[user_id_str]['winner'] = poll_options['winner'][reaction.emoji]
                    elif reaction.emoji in ['✅', '❌']: user_votes[user_id_str]['shutout'] = poll_options['shutout'][reaction.emoji]
                    elif reaction.emoji in ['🇳', '🔜', '🇪', '🇲', '🇱']: user_votes[user_id_str]['relief_timing'] = poll_options['relief_timing'][reaction.emoji]
                    elif reaction.emoji in ['⬆️', '⬇️']: user_votes[user_id_str]['over_under'] = poll_options['over_under'][reaction.emoji]
                    elif reaction.emoji in ['🟢', '🟠']: user_votes[user_id_str]['pitch_speed'] = poll_options['pitch_speed'][reaction.emoji]

        leaderboard_embed = await bot.loop.run_in_executor(
            None, resolve_predictions, current_game_id, 
            dummy_scores['home_score'], dummy_scores['away_score'], 
            dummy_scores['is_shutout'], dummy_scores['relief_inning'],
            {'votes': user_votes}, 
            True 
        )
        
        await interaction.channel.send(f"🎲 **Admin requested random resolution for Game ID `{current_game_id}`!** 🎲", embed=leaderboard_embed)
        
        active_game_trackers[tracker_key]['poll_id'] = None
        active_game_trackers[tracker_key]['poll_end_time'] = None

        await interaction.followup.send("Random resolution complete and poll closed.", ephemeral=True)

    except Exception as e:
        print(f"Error during random resolution for game {current_game_id}: {e}")
        await interaction.followup.send(f"An error occurred during random resolution: {e}", ephemeral=True)


# --- Background Task ---

# Utility: manual sync command for admins
@bot.tree.command(name="sync", description="[ADMIN] Force re-sync of application commands (global and this guild).")
@app_commands.default_permissions(administrator=True)
async def sync_commands(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True, thinking=True)
    try:
        await sync_app_commands()
        # Also ensure current guild specifically
        if interaction.guild:
            bot.tree.copy_global_to(guild=interaction.guild)
            await bot.tree.sync(guild=interaction.guild)
        await interaction.followup.send("✅ Commands synced.", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ Sync failed: {e}", ephemeral=True)


@bot.event
async def on_guild_join(guild: discord.Guild):
    """When the bot joins a new guild, sync commands for immediate availability."""
    try:
        bot.tree.copy_global_to(guild=guild)
        await bot.tree.sync(guild=guild)
        print(f"Auto-synced commands for new guild: {guild.name} ({guild.id})")
    except Exception as e:
        print(f"Failed to auto-sync commands for {guild.id}: {e}")

@tasks.loop(seconds=POLLING_INTERVAL_SECONDS)
async def live_score_tracker():
    """
    The main asynchronous loop that scrapes and posts game updates.
    """
    keys_to_remove = [] 
    games_to_update_autoplan = {} 

    for tracker_key, data in active_game_trackers.items():
        channel = bot.get_channel(data.get('target_channel_id'))
        
        if not channel:
            keys_to_remove.append(tracker_key)
            continue
        
        current_game_id = data.get('game_id')
        
        # --- PHASE 1: Find Game ID for Team Autoplan ---
        if isinstance(tracker_key, tuple) and tracker_key[0] == 'team' and not current_game_id:
            team_id = tracker_key[1]
            game_id, team_name, opponent_name, full_name = await bot.loop.run_in_executor(
                None, find_live_game_id, team_id
            )
            if game_id:
                data['game_id'] = game_id
                data['name'] = full_name
                data['teams'] = [team_name, opponent_name] 
                data['last_play'] = 'GAME START'
                active_game_trackers[tracker_key] = data
                games_to_update_autoplan[tracker_key] = data
                await channel.send(f"✅ **Autoplan Game Found!** Now tracking **{full_name}** (ID: `{game_id}`).")
            else:
                continue

        if not current_game_id:
            continue

        # --- PHASE 2: Check for Timed Poll Expiry ---
        poll_id = data.get('poll_id')
        poll_end_time = data.get('poll_end_time')
        
        if poll_id and poll_end_time and time.time() > poll_end_time:
            await resolve_and_announce_poll(tracker_key, data, channel, is_game_final=False)
            active_game_trackers[tracker_key]['poll_id'] = None
            active_game_trackers[tracker_key]['poll_end_time'] = None
            
        # --- PHASE 3: Scrape the Game for Play-by-Play ---
        latest_play, game_status, final_score, is_game_over, home_score, away_score, pitcher_relief_occurred, is_shutout, relief_inning = await bot.loop.run_in_executor(
            None, get_latest_play, current_game_id
        )

        last_play = data['last_play']
        
        # --- PHASE 3.5: Update Relief Inning State ---
        if relief_inning > 0 and data['relief_inning'] == 0:
            active_game_trackers[tracker_key]['relief_inning'] = relief_inning
            await channel.send(f"🚨 **Pitching Change Detected!** The first relief pitcher entered in **Inning {relief_inning}**.")


        # Logic to handle new plays
        if latest_play != last_play and "Error" not in latest_play:
            active_game_trackers[tracker_key]['last_play'] = latest_play
            active_game_trackers[tracker_key]['total_runs'] = home_score + away_score 
            
            if isinstance(tracker_key, tuple): 
                games_to_update_autoplan[tracker_key] = active_game_trackers[tracker_key]
            
            embed = discord.Embed(
                title=f"⚾ {data['name']} Update | Score: {away_score}-{home_score}",
                description=latest_play,
                color=discord.Color.blue() if not is_game_over else discord.Color.red()
            )
            embed.set_footer(text=f"Status: {game_status} | ID: {current_game_id}")
            
            await channel.send(embed=embed)
            

        # --- PHASE 4: Handle Game End and Final Resolution ---
        if is_game_over:
            await resolve_and_announce_poll(tracker_key, data, channel, is_game_final=True, final_scores={
                'home_score': home_score,
                'away_score': away_score,
                'relief_inning': relief_inning,
                'is_shutout': is_shutout
            })
            
            final_message = f"🏆 **GAME FINAL** 🏆\n**{data['name']}** is **{game_status.upper()}**.\n**Final Score:** {final_score}"
            await channel.send(final_message)
            
            keys_to_remove.append(tracker_key)
            
            if isinstance(tracker_key, tuple):
                autoplanned_games = load_autoplans()
                
                if tracker_key[0] == 'team':
                    data['game_id'] = None
                    data['last_play'] = 'START'
                    data['relief_inning'] = 0 
                    games_to_update_autoplan[tracker_key] = data 
                    await channel.send("Team tracking reset. Waiting for the next live game.")
                else:
                    del autoplanned_games[tracker_key[1]]
                    save_autoplans(autoplanned_games)
                    await channel.send("Single game tracking stopped and removed from persistence.")

    # Apply persistence updates 
    if games_to_update_autoplan:
        autoplanned_games = load_autoplans()
        for tracker_key, data in games_to_update_autoplan.items():
            json_key = str(tracker_key[1]) if tracker_key[0] == 'team' else tracker_key[1]
            if json_key in autoplanned_games:
                autoplanned_games[json_key].update({
                    'game_id': data.get('game_id'),
                    'last_play': data['last_play'],
                    'teams': data['teams'],
                    'name': data['name'],
                    'poll_id': data.get('poll_id'),
                    'poll_end_time': data.get('poll_end_time'),
                    'total_runs': data.get('total_runs'),
                    'relief_inning': data.get('relief_inning') 
                })
        save_autoplans(autoplanned_games)


    # Clean up ended games from the active trackers
    for key in keys_to_remove:
        if key in active_game_trackers:
            del active_game_trackers[key]
            print(f"Stopped tracking for game associated with {key}.")


async def resolve_and_announce_poll(tracker_key, data, channel, is_game_final: bool, final_scores: dict = None):
    """Handles the resolution, cleanup, and announcement of the poll."""
    
    poll_id = data.get('poll_id')
    current_game_id = data.get('game_id')

    if not poll_id:
        return

    try:
        poll_message = await channel.fetch_message(poll_id)
        
        poll_options = data.get('poll_options')
        user_votes = {}
        
        for reaction in poll_message.reactions:
            if reaction.emoji in ['1️⃣', '2️⃣', '✅', '❌', '🇳', '🇪', '🇲', '🇱', '🔜', '⬆️', '⬇️', '🟢', '🟠']:
                async for user in reaction.users():
                    if user.bot:
                        continue
                    
                    user_id_str = str(user.id)
                    if user_id_str not in user_votes:
                        user_votes[user_id_str] = {}
                    
                    if reaction.emoji in ['1️⃣', '2️⃣']: user_votes[user_id_str]['winner'] = poll_options['winner'][reaction.emoji]
                    elif reaction.emoji in ['✅', '❌']: user_votes[user_id_str]['shutout'] = poll_options['shutout'][reaction.emoji]
                    elif reaction.emoji in ['🇳', '🔜', '🇪', '🇲', '🇱']: user_votes[user_id_str]['relief_timing'] = poll_options['relief_timing'][reaction.emoji]
                    elif reaction.emoji in ['⬆️', '⬇️']: user_votes[user_id_str]['over_under'] = poll_options['over_under'][reaction.emoji]
                    elif reaction.emoji in ['🟢', '🟠']: user_votes[user_id_str]['pitch_speed'] = poll_options['pitch_speed'][reaction.emoji]


        # Use final scores for resolution if the game is over, otherwise announce closure
        if is_game_final and final_scores:
            leaderboard_embed = await bot.loop.run_in_executor(
                None, resolve_predictions, current_game_id, 
                final_scores['home_score'], final_scores['away_score'], 
                final_scores['is_shutout'], final_scores['relief_inning'],
                {'votes': user_votes},
                False 
            )
            await channel.send(embed=leaderboard_embed)
            
        else:
            closure_embed = Embed(
                title="🚨 Prediction Poll CLOSED by Timer 🚨",
                description="Voting has ended! Results will be tallied and announced when the game goes FINAL.",
                color=Color.red()
            )
            await channel.send(embed=closure_embed)

        active_game_trackers[tracker_key]['poll_id'] = None
        active_game_trackers[tracker_key]['poll_end_time'] = None
        
    except discord.NotFound:
        print(f"Poll message {poll_id} not found to close.")
    except Exception as e:
        print(f"Error during poll resolution for game {current_game_id}: {e}")


if __name__ == "__main__":
    import sys
    if not DISCORD_TOKEN:
        print("CRITICAL ERROR: DISCORD_TOKEN not set. Create a .env with DISCORD_TOKEN=<token> or export env var.")
        sys.exit(1)
        
    try:
        # Initialize JSON files if they don't exist
        if not AUTOPLAN_FILE.exists(): save_autoplans({})
        if not PREDICTION_FILE.exists(): save_predictions({})
        if not TEAMS_FILE.exists(): save_teams({})
            
        bot.run(DISCORD_TOKEN)
    except discord.errors.LoginFailure:
        print("CRITICAL ERROR: Invalid token. Check your DISCORD_TOKEN in config.py.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

