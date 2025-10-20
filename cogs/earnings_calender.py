import discord
from discord.ext import commands, tasks
from discord import app_commands
import aiohttp
from datetime import datetime, timedelta, timezone
import os
from dotenv import load_dotenv
import asyncio

load_dotenv()

FINNHUB_API_KEYS = [os.getenv(f"FINNHUB_API_KEY_{i}") for i in range(1, 11)]
MIN_PRICE = 5
MAX_PRICE = 600

class EarningsCalendar(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.post_daily_earnings.start()
    
    def cog_unload(self):
        self.post_daily_earnings.cancel()
    
    async def get_stock_price(self, symbol):
        """Fetching current price of stocks from Finnhub"""
        for api_key in FINNHUB_API_KEYS:
            url = f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={api_key}"
            
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            # if current price doesnt exist - automatically assigned to 0
                            current_price = data.get('c', 0)
                            return current_price if current_price > 0 else None
                        elif resp.status == 429: # too many requests
                            continue
            except Exception:
                continue
        
        return None
    
    async def fetch_earnings_calendar(self, days_ahead=7):
        """Fetching earnings calendar from Finnhub with API key rotation"""
        today = datetime.now().strftime('%Y-%m-%d')
        future_date = (datetime.now() + timedelta(days=days_ahead)).strftime('%Y-%m-%d')
        
        for i, api_key in enumerate(FINNHUB_API_KEYS):                
            url = f"https://finnhub.io/api/v1/calendar/earnings?from={today}&to={future_date}&token={api_key}"
            
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url) as resp:
                        if resp.status == 200:
                            # convert json string to python dict
                            data = await resp.json()
                            print(f"*** Successfully fetched earnings calendar with API key {i + 1}")
                            return data
                        elif resp.status == 429:
                            print(f"--Finnhub earnings API key {i + 1} rate limited")
                            continue
                        else:
                            text = await resp.text()
                            print(f"-- {resp.status}:  key {i + 1}: {text}")
                            continue
            except Exception as e:
                print(f"--Error fetching earnings with key {i + 1}: {e}")
                continue
        
        print("---All Finnhub API keys failed for earnings calendar")
        return None
    
    async def filter_earnings_by_price(self, earnings_calendar):
        """Filtering the earnings to only include stocks in price range"""
        filtered_earnings = []
        
        for earning in earnings_calendar:
            symbol = earning.get('symbol')
            if not symbol:
                continue
            
            # getting the current price of stock
            price = await self.get_stock_price(symbol)
            
            if price and MIN_PRICE <= price <= MAX_PRICE:
                earning['current_price'] = price
                filtered_earnings.append(earning)
        
        # returning just the list of companies that are in price range
        return filtered_earnings
    
    def build_single_day_embed(self, date, earnings_list):
        """Building a Discord embed for a each days earnings"""
        # Format date nicely
        try:
            date_obj = datetime.strptime(date, '%Y-%m-%d')
            formatted_date = date_obj.strftime('%B %d, %Y (%A)')
        except:
            formatted_date = date
        
        embed = discord.Embed(
            title=f"📅 Earnings: {formatted_date}",
            description=f"**{len(earnings_list)} companies** reporting earnings",
            color=discord.Color.blue(),
            timestamp=datetime.now(timezone.utc)
        )
        
        chunk_size = 15  # testing 15 companies per field so no overload
        
        # looping by chunksize 
        for i in range(0, len(earnings_list), chunk_size):
            chunk = earnings_list[i:i + chunk_size]
            
            # Build the field value
            entries = []
            for earning in chunk:
                symbol = earning.get('symbol', 'N/A')
                # just adding eps 
                eps_estimate = earning.get('epsEstimate')
                current_price = earning.get('current_price')
                
                entry = f"**{symbol}**"
                if current_price is not None:
                    entry += f" • ${current_price:.2f}"
                if eps_estimate is not None:
                    entry += f" • EPS: ${eps_estimate}"
                
                # adding finalized string to list of stock w info of price and eps estimate
                entries.append(entry)
            
            # Determine field name
            if i == 0:
                field_name = "Companies"
            else:
                field_name = f"Companies (Part {i//chunk_size + 1})"
            
            # using fields so no overload
            embed.add_field(
                name=field_name,
                value="\n".join(entries),
                inline=False
            )
        
        embed.set_footer(text=f"Price Range: ${MIN_PRICE}-${MAX_PRICE} • Data from Finnhub")
        return embed
    
    @tasks.loop(hours=24)
    async def post_daily_earnings(self):
        """Post earnings calendar once daily - one embed per day"""
        await self.bot.wait_until_ready()
        
        # Fetch earnings data
        earnings_data = await self.fetch_earnings_calendar(days_ahead=7)
        
        if not earnings_data or 'earningsCalendar' not in earnings_data:
            print("Failed to fetch earnings calendar")
            return
        
        # Filtering by price range
        print(f"Filtering earnings by price range ${MIN_PRICE}-${MAX_PRICE}...")
        filtered_earnings = await self.filter_earnings_by_price(earnings_data['earningsCalendar'])
        
        # Group earnings by date
        earnings_by_date = {}
        for earning in filtered_earnings:
            date = earning.get('date', 'Unknown')
            # creating dict with keys as date and values of the companies earnings that are releasing on that date
            if date not in earnings_by_date:
                earnings_by_date[date] = []
            earnings_by_date[date].append(earning)
        
        # post to all servers
        for guild in self.bot.guilds:
            channel = discord.utils.get(guild.text_channels, name="earnings-calendar-dashboard")
            if not channel:
                continue
            
            try:
                # Cleariong channel first
                await channel.purge(limit=None)

                # Post summary embed after
                summary_embed = discord.Embed(
                    title="📊 Upcoming Earnings (Next 7 Days)",
                    description=f"**Total: {len(filtered_earnings)} companies** reporting earnings\n"
                                f"Price range: ${MIN_PRICE}-${MAX_PRICE}",
                    color=discord.Color.gold(),
                    timestamp=datetime.now(timezone.utc)
                )
                
                # Add summary of each day
                summary_lines = []
                for date in sorted(earnings_by_date.keys()):
                    try:
                        date_obj = datetime.strptime(date, '%Y-%m-%d')
                        day_name = date_obj.strftime('%a %m/%d')
                    except:
                        day_name = date
                    count = len(earnings_by_date[date])
                    summary_lines.append(f"• **{day_name}**: {count} companies")
                
                summary_embed.add_field(
                    name="Daily Breakdown",
                    value="\n".join(summary_lines) if summary_lines else "No earnings scheduled",
                    inline=False
                )
                
                await channel.send(embed=summary_embed)
                await asyncio.sleep(0.5)  # creating delay between messages
                
                # Post one embed per day
                for date in sorted(earnings_by_date.keys()):
                    earnings_list = earnings_by_date[date]
                    embed = self.build_single_day_embed(date, earnings_list)
                    await channel.send(embed=embed)
                    await asyncio.sleep(0.5)  # Rate limit protection
                
                print(f"Posted {len(earnings_by_date)} day(s) of earnings to {guild.name}")
                
            except discord.Forbidden:
                print(f"No permission to post in earnings-calendar-dashboard in {guild.name}")
            except discord.HTTPException as e:
                print(f"Failed to post earnings calendar in {guild.name}: {e}")
    
    @post_daily_earnings.before_loop
    async def before_daily_earnings(self):
        """Wait for bot to be ready before starting loop"""
        await self.bot.wait_until_ready()
    
async def setup(bot):
    await bot.add_cog(EarningsCalendar(bot))