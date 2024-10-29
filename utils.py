import os
import json
import requests
import sqlite3
from datetime import datetime

CLAN_TAGS_FILE = "clan_tags.json"

# Load clan tags
def load_clan_tags():
    if os.path.exists(CLAN_TAGS_FILE):
        with open(CLAN_TAGS_FILE, 'r') as f:
            return json.load(f)
    return {}

# Save clan tags w/ guild id
def save_clan_tag(guild_id, clan_tag):
    clan_tags = load_clan_tags()
    clan_tags[str(guild_id)] = {
        "clan_tag": clan_tag,
        "auto_polling": False 
    }
    
    with open(CLAN_TAGS_FILE, 'w') as f:
        json.dump(clan_tags, f, indent=4)

# Get clan tag for guild
def get_clan_tag(guild_id):
    clan_tags = load_clan_tags()
    return clan_tags.get(str(guild_id), {}).get('clan_tag', None)

def save_auto_polling(guild_id, clan_tag, enable):
    guild_data = load_guild_data()

    if str(guild_id) not in guild_data:
        guild_data[str(guild_id)] = {"clan_tag": clan_tag, "auto_polling": False}

    # Update the auto-polling state
    guild_data[str(guild_id)]["auto_polling"] = enable

    save_guild_data(guild_data)

def is_auto_polling_enabled(clan_tag):
    guild_data = load_guild_data()
    for guild_id, info in guild_data.items():
        if info["clan_tag"] == clan_tag and info.get("auto_polling", False):
            return True
    return False

def get_auto_polling_clans():
    guild_data = load_guild_data()
    return {guild_id: info["clan_tag"] for guild_id, info in guild_data.items() if info.get("auto_polling", False)}

def is_admin_or_owner(interaction):
    return (interaction.user.guild_permissions.administrator or 
            interaction.guild.owner_id == interaction.user.id)

def format_time(coc_time, type=1, timezone='UTC'):
    # Parse the time string from the format "YYYYMMDDTHHMMSS.sssZ"
    parsed_time = datetime.strptime(coc_time, "%Y%m%dT%H%M%S.%fZ")
    
    # Format the date (Month Day, Year)
    formatted_date = parsed_time.strftime("%b %d, %Y")
    
    # Format the time (12-hour format with AM/PM and include the time zone)
    formatted_time = parsed_time.strftime("%I:%M %p") + f" {timezone}"
    if type == 1:
        return f"{formatted_date}\n{formatted_time}"
    elif type == 2:
        return f"{formatted_date} {formatted_time}"
    
def load_guild_data():
    try:
        with open('clan_tags.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

# Save the guilds and their set_tags to the JSON file
def save_guild_data(data):
    with open('clan_tags.json', 'w') as f:
        json.dump(data, f, indent=4)


