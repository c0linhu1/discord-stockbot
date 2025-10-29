import discord
from discord.ext import commands
from discord import app_commands
from database import db_manager
import aiohttp
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

FINNHUB_API_KEYS = [os.getenv(f"FINNHUB_API_KEY_{i}") for i in range (1,11)]

class Portfolio(commands.Cog):
    def _init_(self, bot):
        self.bot = bot

    async def get_current_price(self, ticker):
        """Getting current price for specific stock"""
        for api_key in FINNHUB_API_KEYS:
            url = f"https://finnhub.io/api/v1/quote?symbol={ticker}&token={api_key}"
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url) as resp:
                        # if successful pull
                        if resp.status == 200:
                            data = await resp.json()
                            current_price = data.get('c', 0)
                            if current_price > 0:
                                return current_price
                        elif resp.status == 429:
                            continue
            except Exception as e:
                print(f"Error fetching price for {ticker}: {e}")
                continue
        
        return None
    
    @app_commands.command(name = "portfolio", description = "Creates a private portfolio for the user")
    async def private_portfolio(self, interaction: discord.Interaction):
        guild = interaction.guild
        user = interaction.user

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            user: discord.PermissionOverwrite(view_channel=True, send_messages = True),
            guild.me: discord.PermissionOverwrite(view_channel=False)

        }




async def setup(bot):
    await bot.add_cog(Portfolio(bot))