import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

FINNHUB_API_KEYS = [os.getenv(f"FINNHUB_API_KEY_{i}") for i in range(1, 11)]

class StockInfo(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def get_stock_data_finnhub(self, symbol: str):
        """Fetch stock data from Finnhub API with backup key fallback"""
        for i, api_key in enumerate(FINNHUB_API_KEYS):
            if not api_key:  # Skip empty keys
                continue
                
            try:
                async with aiohttp.ClientSession() as session:
                    # Fetch both quote and profile data concurrently
                    quote_url = f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={api_key}"
                    profile_url = f"https://finnhub.io/api/v1/stock/profile2?symbol={symbol}&token={api_key}"
                    
                    async with session.get(quote_url) as quote_resp, \
                               session.get(profile_url) as profile_resp:
                        
                        if quote_resp.status == 429:
                            print(f"--Finnhub stock API key {i + 1} rate limited")
                            continue  
                        
                        if quote_resp.status != 200:
                            print(f"--Finnhub stock API key {i + 1} returned status {quote_resp.status}")
                            continue 
                        
                        quote_data = await quote_resp.json()
                        profile_data = {}
                        if profile_resp.status == 200:
                            profile_data = await profile_resp.json()
                
                # Process the data
                current_price = quote_data.get('c', 0)
                if current_price == 0:  # Invalid data
                    print(f"--Invalid price data for {symbol} with API key {i + 1}")
                    continue
                
                print(f"*** Successfully fetched stock data for {symbol} with API key {i + 1}")
                
                return {
                    'symbol': symbol.upper(),
                    'current_price': current_price,
                    'change': quote_data.get('d', 0),
                    'percent_change': quote_data.get('dp', 0),
                    'high': quote_data.get('h', 0),
                    'low': quote_data.get('l', 0),
                    'open': quote_data.get('o', 0),
                    'previous_close': quote_data.get('pc', 0),
                    'company_name': profile_data.get('name', symbol),
                    'performance': {
                        '1D': {
                            'change_percent': quote_data.get('dp', 0),
                            'change_value': quote_data.get('d', 0)
                        }
                    }
                }
            except Exception as e:
                print(f"--Error fetching stock data with API key {i + 1}: {e}")
                continue  # Try next API key
        
        print(f"---All Finnhub API keys failed for stock {symbol}")
        return None  # All keys failed

    def create_stock_info_embed(self, stock_data):
        """Create a Discord embed with stock information"""
        if not stock_data:
            return None
        
        symbol = stock_data['symbol']
        current_price = stock_data['current_price']
        change = stock_data['change']
        percent_change = stock_data['percent_change']
        company_name = stock_data.get('company_name', symbol)
        
        # Determine color and trend
        if percent_change > 0:
            color = discord.Color.green()
            trend_emoji = "📈"
            change_sign = "+"
        elif percent_change < 0:
            color = discord.Color.red()
            trend_emoji = "📉"
            change_sign = ""
        else:
            color = discord.Color.grey()
            trend_emoji = "➡️"
            change_sign = ""
        
        embed = discord.Embed(
            title=f"{trend_emoji} {symbol} - {company_name}",
            color=color,
        )
        
        # Add fields efficiently
        fields = [
            ("Current Price", f"${current_price:.2f}", True),
            ("Change", f"{change_sign}${change:.2f} ({change_sign}{percent_change:.2f}%)", True),
            ("Day Range", f"${stock_data['low']:.2f} - ${stock_data['high']:.2f}", True),
            ("Open", f"${stock_data['open']:.2f}", True),
            ("Previous Close", f"${stock_data['previous_close']:.2f}", True),
            ("‎", "‎", True)  # Spacing
        ]
        
        for name, value, inline in fields:
            embed.add_field(name=name, value=value, inline=inline)
        
        embed.set_footer(text="DATA PROVIDED BY FINNHUB • MAY BE DELAYED • ONLY POSTS DATA FROM NEW YORK REGULAR TRADING SESSION")
        return embed



async def setup(bot):
    await bot.add_cog(StockInfo(bot))