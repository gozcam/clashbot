import os

import discord
from discord.ext import commands
from dotenv import load_dotenv

from commands import setup_commands, resume_auto_polling

# Load environment variables
load_dotenv()

DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
CLASH_TOKEN = os.getenv('CLASH_TOKEN')


class ClashBot(commands.Bot):
    async def setup_hook(self):
        setup_commands(self)
        await self.tree.sync()
        await resume_auto_polling()


intents = discord.Intents.default()
bot = ClashBot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f'{bot.user} is now online!')

if __name__ == '__main__':
    missing_variables = [
        name
        for name, value in {
            'DISCORD_TOKEN': DISCORD_TOKEN,
            'CLASH_TOKEN': CLASH_TOKEN,
        }.items()
        if not value
    ]
    if missing_variables:
        raise RuntimeError(f"Missing required environment variables: {', '.join(missing_variables)}")
    bot.run(DISCORD_TOKEN)
