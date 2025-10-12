# Pointstreak Discord Bot

A Discord bot that tracks Pointstreak baseball games and runs fantasy-style prediction polls.

## Setup

1. Python 3.12+, Git, and a Discord application with the `applications.commands` scope.
2. Create a virtual environment and install deps:

```bash
cd "Discord Bot"
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt  # or run `python import.py`
```

3. Configure environment variables:

- Copy `.env.example` to `.env` and fill in values.
- Required: `DISCORD_TOKEN`.
- Optional: `ADMIN_CHANNEL_ID`, `GUILD_IDS`.

4. Run locally:

```bash
source ./.venv/bin/activate
python main_bot.py
```

## Systemd service (optional)

Edit `pointstreak.service` paths if your home directory differs. Then:

```bash
sudo systemctl daemon-reload
sudo systemctl enable pointstreak.service
sudo systemctl start pointstreak.service
sudo journalctl -u pointstreak.service -f
```

Provide secrets via `/home/<user>/Discord Bot/.env`.

## Security

- No secrets are committed to the repo. `config.py` reads from environment and never hardcodes tokens.
- `.gitignore` excludes `.env`, venv, caches, and runtime JSON data.

## Slash commands not showing?

- Ensure the bot was invited with `applications.commands` scope.
- After the bot starts, run `/sync` (admin) to force a guild sync.
- Check logs for sync messages.
