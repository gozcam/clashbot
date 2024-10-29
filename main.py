import os
import discord
from discord.ext import commands
from dotenv import load_dotenv
from commands import setup_commands, resume_auto_polling

# Load environment variables
load_dotenv()

DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
CLASH_TOKEN = os.getenv('CLASH_TOKEN')

# Define bot intents and object
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents, application_id=os.getenv('DISCORD_APPLICATION_ID'))

# Set up commands
setup_commands(bot)

from asyncio import create_task

@bot.event
async def on_ready():
    print(f'{bot.user} is now online!')
    await bot.tree.sync()
    create_task(resume_auto_polling())
if __name__ == '__main__':
    bot.run(DISCORD_TOKEN)
