# Discord Stock Bot

A Discord bot that provides financial news and stock market information.

## Features
- Real-time financial news from Finnhub and Marketaux
- Stock price tracking and watchlists
- Automated news updates every few minutes
- Private watchlist channels for users
- Interactive stock information buttons

## Setup

### Prerequisites
- Python 3.8+
- Discord Bot Token
- Finnhub API Keys
- Marketaux API Keys

### Installation

1. Clone the repository:
```bash
git clone https://github.com/YOUR_USERNAME/discord-stock-bot.git
cd discord-stock-bot
```

2. Create a virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate 

```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Create a `.env` file in the project root (copy from `.env.example`):
```bash
cp .env.example .env
```

5. Edit `.env` and add your actual API keys

6. Run the bot:
```bash
python main.py
```

## Required Discord Bot Permissions
- Read Messages/View Channels
- Send Messages
- Manage Channels
- Manage Messages
- Embed Links
- Use Slash Commands

## Commands
- `/watchlist` - Create a private watchlist channel
- `/add_company` - Add a stock to your watchlist
- `/remove_company` - Remove a stock from your watchlist
- `/show_watchlist` - Display your watchlist with interactive buttons
- `/delete_watchlist` - Delete your private watchlist channel

## Twitter API
- The api keys for twitter are the BEARER TOKENS
- Free Twitter API has a 15 min cooldown time for each dev account 