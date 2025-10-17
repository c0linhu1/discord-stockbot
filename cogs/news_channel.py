import discord
from discord.ext import commands, tasks
import aiohttp
from datetime import datetime, timedelta, timezone
import hashlib
from database import db_manager
import os
from dotenv import load_dotenv

load_dotenv()

FINNHUB_API_KEYS = [
    os.getenv("FINNHUB_API_KEY_1"),
    os.getenv("FINNHUB_API_KEY_2"),
    os.getenv("FINNHUB_API_KEY_3"),
    os.getenv("FINNHUB_API_KEY_4")
]

MARKETAUX_API_KEYS = [
    os.getenv("MARKETAUX_API_KEY_1"),
    os.getenv("MARKETAUX_API_KEY_2")
]

FINNHUB_URL = "https://finnhub.io/api/v1/news?category={category}&token={token}"
FINNHUB_CATEGORIES = ["general", "forex", "crypto", "merger"]

FINNHUB_FETCH_INTERVAL = 2   # minutes
MARKETAUX_FETCH_INTERVAL = 8
HEARTBEAT_COOLDOWN = timedelta(minutes=15)


def make_identifier(article, prefix=""):
    """Generate a unique identifier for each article."""
    headline = article.get("headline") or article.get("title") or ""
    timestamp = str(article.get("datetime") or article.get("published_at") or "")
    url = article.get("url", "")
    raw = f"{prefix}{headline}-{timestamp}-{url}"
    return hashlib.sha256(raw.encode()).hexdigest()


class NewsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.fetch_finnhub.start()
        self.fetch_marketaux.start()

    def cog_unload(self):
        self.fetch_finnhub.cancel()
        self.fetch_marketaux.cancel()

    async def send_articles(self, guild, articles, source):
        """Send new articles or heartbeat if none."""
        channel = discord.utils.get(guild.text_channels, name="news")
        if channel is None:
            return

        sent_any = False

        for article in reversed(articles):
            identifier = make_identifier(article, prefix=f"{source}-")
            
            # Check if article has been seen using database
            if not db_manager.is_article_seen(guild.id, identifier):
                embed = self.build_embed(article, source)
                await channel.send(embed=embed)
                
                # Mark article as seen in database
                db_manager.mark_article_seen(guild.id, identifier, source)
                sent_any = True

        # 🔄 Heartbeat if no new news
        if not sent_any:
            now = datetime.utcnow()
            last_sent = db_manager.get_last_heartbeat(guild.id)

            if not last_sent or now - last_sent >= HEARTBEAT_COOLDOWN:
                await channel.send(
                    "🔄 No new news at this time.\n"
                    "⚠️ ATTENTION ⚠️ StockBot can miss news. News may be delayed from 1 minute up to 24 hours. "
                    "Do your own research for faster or equity-specific news.\n"
                )
                # Update heartbeat in database
                db_manager.update_heartbeat(guild.id, now)

    @tasks.loop(minutes=FINNHUB_FETCH_INTERVAL)
    async def fetch_finnhub(self):
        """Fetch from Finnhub (last 2 days) cycling through all API keys."""
        async def fetch_with_key(api_key, key_index):
            cutoff = int((datetime.utcnow() - timedelta(days=2)).timestamp())
            all_news_items = []
            
            async with aiohttp.ClientSession() as session:
                for category in FINNHUB_CATEGORIES:
                    url = FINNHUB_URL.format(category=category, token=api_key)
                    async with session.get(url) as resp:
                        if resp.status == 200:
                            news_items = await resp.json()
                            # Filter: only include from last 2 days
                            filtered = [n for n in news_items if n.get("datetime", 0) >= cutoff]
                            all_news_items.extend(filtered)
                        elif resp.status == 429:  # Rate limit exceeded
                            text = await resp.text()
                            print(f"Finnhub API key {key_index + 1} rate limited for {category}: {text}")
                            return None
                        else:
                            text = await resp.text()
                            print(f"Finnhub error {resp.status} for {category} with key {key_index + 1}: {text}")
                            return None
            
            return all_news_items

        try:
            all_news_items = None
            successful_key = None
            
            # Try each API key in order until one works
            for i, api_key in enumerate(FINNHUB_API_KEYS):
                print(f"Trying Finnhub API key {i + 1}...")
                all_news_items = await fetch_with_key(api_key, i)
                
                if all_news_items is not None:
                    successful_key = i + 1
                    print(f"✅ Successfully fetched news with Finnhub API key {successful_key}")
                    break
                else:
                    print(f"Finnhub API key {i + 1} failed, trying next key...")

            if all_news_items is None:
                print("All Finnhub API keys failed or reached limits.")
                return

        except Exception as e:
            print(f"Error fetching Finnhub: {e}")
            return

        for guild in self.bot.guilds:
            await self.send_articles(guild, all_news_items, "finnhub")

    @tasks.loop(minutes=MARKETAUX_FETCH_INTERVAL)
    async def fetch_marketaux(self):
        """Fetch from Marketaux (last 2 days) and filter locally."""
        async def fetch_with_key(api_key, key_index):
            url = f"https://api.marketaux.com/v1/news/all?api_token={api_key}&language=en&limit=50"
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    if resp.status == 429:  # Rate limit exceeded
                        text = await resp.text()
                        print(f"Marketaux API key {key_index + 1} rate limited: {text}")
                        return None
                    elif resp.status != 200:
                        text = await resp.text()
                        print(f"Marketaux error {resp.status} with key {key_index + 1}: {text}")
                        return None
                    data = await resp.json()

            # Filter locally for last 2 days
            cutoff = datetime.now(timezone.utc) - timedelta(days=2)
            filtered = [
                article for article in data.get("data", [])
                if article.get("language") == "en" and
                datetime.fromisoformat(article["published_at"].replace("Z", "+00:00")) >= cutoff
            ]

            return {"data": filtered}

        try:
            data = None
            successful_key = None
            
            # Try each API key in order until one works
            for i, api_key in enumerate(MARKETAUX_API_KEYS):
                print(f"Trying Marketaux API key {i + 1}...")
                data = await fetch_with_key(api_key, i)
                
                if data is not None:
                    successful_key = i + 1
                    print(f"✅ Successfully fetched news with Marketaux API key {successful_key}")
                    break
                else:
                    print(f"❌ Marketaux API key {i + 1} failed, trying next key...")

            if data is None:
                print("❌ All Marketaux API keys failed or reached limits.")
                return

            news_items = data.get("data", [])

        except Exception as e:
            print(f"Error fetching Marketaux: {e}")
            return

        for guild in self.bot.guilds:
            await self.send_articles(guild, news_items, "marketaux")

    @fetch_finnhub.before_loop
    @fetch_marketaux.before_loop
    async def before_loop(self):
        await self.bot.wait_until_ready()

    def build_embed(self, article, source):
        """Build a Discord embed for an article."""
        if source == "finnhub":
            headline = article.get("headline", "No title")
            summary = article.get("summary", "")
            timestamp = article.get("datetime")
            color = discord.Color.blue()
        else:
            headline = article.get("title", "No title")
            summary = article.get("description", "")
            timestamp = article.get("published_at")
            color = discord.Color.green()

        url = article.get("url", "")
        embed = discord.Embed(
            title=headline,
            url=url,
            description=(summary[:200] + "...") if summary else "No description",
            color=color
        )

        if timestamp:
            try:
                if source == "finnhub":
                    embed.timestamp = datetime.fromtimestamp(timestamp)
                else:
                    embed.timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            except Exception:
                pass

        embed.set_footer(text=article.get("source", source.capitalize()))
        return embed


async def setup(bot):
    await bot.add_cog(NewsCog(bot))