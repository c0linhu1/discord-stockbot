import discord
from discord.ext import commands

class ResponseHandler(commands.Cog):
    """Utility cog for handling responses - DM vs private channel logic"""
    
    def __init__(self, bot):
        self.bot = bot

    def is_user_private_channel(self, channel, user):
        """Check if the channel is the user's private watchlist channel"""
        if not isinstance(channel, discord.TextChannel):
            return False
        
        expected_name = f"private_watchlist-{user.name.lower()}"
        return channel.name == expected_name

    async def send_response(self, interaction: discord.Interaction, message: str, ephemeral: bool = True):
        """
        Send response to DM if user is not in their private channel, otherwise respond in channel
        For slash commands (interactions)
        """
        user = interaction.user
        channel = interaction.channel
        
        if self.is_user_private_channel(channel, user):
            # User is in their private channel, respond here
            await interaction.response.send_message(message, ephemeral=ephemeral)
        else:
            # User is not in their private channel, send to DM
            await interaction.response.send_message("✅ Command processed - check your DMs!", ephemeral=True)
            try:
                await user.send(message)
            except discord.Forbidden:
                # If DM fails, edit the interaction response
                await interaction.edit_original_response(content=message)

    async def send_response_ctx(self, ctx: commands.Context, message: str):
        """
        Send response to DM if user is not in their private channel, otherwise respond in channel
        For prefix commands (ctx)
        """
        user = ctx.author
        channel = ctx.channel
        
        if self.is_user_private_channel(channel, user):
            # User is in their private channel, respond here
            await ctx.send(message)
        else:
            # User is not in their private channel, send to DM
            try:
                await user.send(message)
            except discord.Forbidden:
                # If DM fails, respond in channel
                await ctx.send(message)

async def setup(bot):
    await bot.add_cog(ResponseHandler(bot))