import discord
from discord.ext import commands
from discord import app_commands
from database import db_manager

class Commands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot



async def setup(bot):
    await bot.add_cog(Commands(bot))