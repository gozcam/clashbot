import discord
from discord.ext import tasks, commands
from discord import app_commands
import coc_api
import utils
from json_manager import update_player_stats, get_player_stats
import asyncio
from datetime import datetime, timedelta, timezone

tracked_servers ={}
active_clan_polling = {}  # Structure: { "clan_tag": WarTracker instance }
async def resume_auto_polling():
    guild_data = utils.load_guild_data()  # Load the guild data from the JSON file

    for guild_id, info in guild_data.items():
        if isinstance(info, dict) and info.get("auto_polling", False):
            clan_tag = info.get("clan_tag")
            if clan_tag:
                print(f"Resuming auto-polling for clan {clan_tag} in guild {guild_id}")

                # Start the WarTracker for the clan
                if clan_tag not in tracked_servers:
                    war_tracker = WarTracker(clan_tag)
                    active_clan_polling[clan_tag] = war_tracker
                    war_tracker.automatic_poll.start()

                    # Track that this guild is polling this clan
                    tracked_servers[clan_tag] = [guild_id]
                else:
                    tracked_servers[clan_tag].append(guild_id)


# Setup claninfo view pages
class ClanInfoView(discord.ui.View):
    def __init__(self, clan_info, timeout = 180):
        super().__init__(timeout=timeout)  # No timeout for the buttons
        self.page = 0
        self.clan_info = clan_info
        self.embeds = self.generate_embeds()

    def generate_embeds(self):
        # Page 1: Basic Clan Info
        basic_info_embed = discord.Embed(
            title=self.clan_info['name'],
            description=self.clan_info['tag'],
            color=discord.Color.blurple()
        )
        
        basic_info_embed.add_field(name="Level", value=self.clan_info['clanLevel'], inline=False)
        basic_info_embed.add_field(name="Members", value=self.clan_info['members'], inline=False)
        basic_info_embed.add_field(name="Clan Trophies", value=self.clan_info['clanPoints'], inline=False)
        basic_info_embed.add_field(name="Location", value=self.clan_info['location']['name'], inline=False)
        basic_info_embed.set_thumbnail(url=self.clan_info['badgeUrls']['medium'])

        # Page 2: War Info
        war_info_embed = discord.Embed(
            title=f"{self.clan_info['name']}",
            description= "War Info",
            color=discord.Color.blurple()
        )
        
        # Calculate win rate (excludes ties)
        war_wins = self.clan_info.get('warWins', 0)
        war_losses = self.clan_info.get('warLosses', 0)
        if (war_wins + war_losses > 0) and self.clan_info.get('warLosses','Hidden') != 'Hidden':
            win_rate = war_wins / (war_wins + war_losses) * 100
            win_ratestr = f"{win_rate:.2f}%"
        else:
            win_ratestr = "N/A"

        
        war_info_embed.add_field(name="League", value=self.clan_info['warLeague']['name'], inline=False)
        war_info_embed.add_field(name="Wars Won", value=war_wins, inline=False)
        war_info_embed.add_field(name="Wars Lost", value=self.clan_info.get('warLosses', 'Hidden'), inline=False)
        war_info_embed.add_field(name="Wars Tied", value=self.clan_info.get('warTies', 'Hidden'), inline=False)
        
        war_info_embed.add_field(name="Win Rate", value=win_ratestr, inline=False)
        war_info_embed.set_thumbnail(url=self.clan_info['badgeUrls']['medium'])

        # Page 3: Capital Peak Info
        capital_info_embed = discord.Embed(
            title=f"{self.clan_info['name']}",
            description="Capital Peak Info",
            color=discord.Color.blurple()
        )
        capital_info_embed.add_field(name="Capital Hall Level", value=self.clan_info['clanCapital'].get('capitalHallLevel', 'Unknown'), inline=False)
        capital_info_embed.set_thumbnail(url=self.clan_info['badgeUrls']['medium'])

        # Return all the embeds in a list
        return [basic_info_embed, war_info_embed, capital_info_embed]

    @discord.ui.button(label="Basic Info", style=discord.ButtonStyle.primary, custom_id="basic_info")
    async def basic_info_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page = 0
        await interaction.response.edit_message(embed=self.embeds[self.page], view=self)

    @discord.ui.button(label="War Info", style=discord.ButtonStyle.primary, custom_id="war_info")
    async def war_info_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page = 1
        await interaction.response.edit_message(embed=self.embeds[self.page], view=self)

    @discord.ui.button(label="Capital Info", style=discord.ButtonStyle.primary, custom_id="capital_info")
    async def capital_info_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page = 2
        await interaction.response.edit_message(embed=self.embeds[self.page], view=self)

    async def on_timeout(self):
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True
    
class MembersView(discord.ui.View):
    def __init__(self, clan_info, members, per_page=10, timeout = 180):
        super().__init__(timeout=timeout)  # Changed timeout to None to prevent auto-expiration
        self.page = 0
        self.clan_info = clan_info
        self.members = members
        self.per_page = per_page
        self.embeds = self.generate_embeds()

    def generate_embeds(self):
        pages = [self.members[i:i + self.per_page] for i in range(0, len(self.members), self.per_page)]
        embeds = []

        for page_num, members_page in enumerate(pages):
            embed = discord.Embed(
                title=f"{self.clan_info['name']} Members",
                color=discord.Color.blurple()
            )

            if 'badgeUrls' in self.clan_info and 'medium' in self.clan_info['badgeUrls']:
                embed.set_thumbnail(url=self.clan_info['badgeUrls']['medium'])

            for member in members_page:
                embed.add_field(
                    name=f"{member['clanRank']}. {member['name']}",
                    value=f"{member['role'].capitalize()} | TH {member['townHallLevel']} | {member['tag']}",
                    inline=False
                )
            
            embed.set_footer(text=f"Page {page_num + 1}/{len(pages)}")
    
            embeds.append(embed)

        return embeds

    @discord.ui.button(label="Previous", style=discord.ButtonStyle.primary)
    async def previous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page > 0:
            self.page -= 1
            await interaction.response.edit_message(embed=self.embeds[self.page], view=self)

    @discord.ui.button(label="Next", style=discord.ButtonStyle.primary)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page < len(self.embeds) - 1:
            self.page += 1
            await interaction.response.edit_message(embed=self.embeds[self.page], view=self)

    async def on_timeout(self):
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True

class PlayerInfoView(discord.ui.View):
    def __init__(self, player_info, interaction, per_page=5, timeout = 180):
        super().__init__(timeout=timeout)
        self.page = 0
        self.player_info = player_info
        self.per_page = per_page
        self.guild = interaction.guild
        self.embeds = self.generate_embeds()

    def generate_embeds(self):
        embeds = []

        # Page 1: Basic Info
        home_info_embed = discord.Embed(
            title=f"{self.player_info['name']}",
            description=f"General Data",
            color=discord.Color.gold()
        )
        home_info_embed.add_field(name="Town Hall", value=self.player_info['townHallLevel'], inline=False)
        home_info_embed.add_field(name="Level", value=self.player_info['expLevel'], inline=False)
        home_info_embed.add_field(name="Clan Role", value=self.player_info.get('role', 'No Role').capitalize(), inline=False)
        home_info_embed.add_field(name="Donated -", value=self.player_info['donations'], inline=True)
        home_info_embed.add_field(name="Received", value=self.player_info['donationsReceived'], inline=True)
        home_info_embed.add_field(name="Player Tag", value=self.player_info['tag'], inline=False)
        if 'clan' in self.player_info and 'badgeUrls' in self.player_info['clan']:
            home_info_embed.set_thumbnail(url=self.player_info['clan']['badgeUrls']['medium'])
        home_info_embed.set_footer(text=f"Page 1/{len(embeds)}")
        embeds.append(home_info_embed)
        
        # Additional pages can be added here (e.g., attack statistics, etc.)
        
        # Page 2: League Info
        league_embed = discord.Embed(
            title=f"{self.player_info['name']}",
            description=f"League Data",
            color=discord.Color.gold()
        )
        league_embed.add_field(name="League", value=self.player_info['league']['name'], inline=False)
        league_embed.add_field(name="Trophies", value=self.player_info['trophies'], inline=False)
        league_embed.add_field(name="Peak", value=self.player_info['bestTrophies'], inline=False)
        if 'legendStatistics' in self.player_info:
            if 'legendTrophies' in self.player_info['legendStatistics']:
                league_embed.add_field(name="Legend Trophies", value=self.player_info['legendStatistics']['legendTrophies'], inline=False)
            if 'bestSeason' in self.player_info['legendStatistics']:
                league_embed.add_field(name="Best Season", value=f"{self.player_info['legendStatistics']['bestSeason']['id']} | {self.player_info['legendStatistics']['bestSeason']['trophies']}", inline=False)
            if 'previousSeason' in self.player_info['legendStatistics']:
                league_embed.add_field(name="Previous Season", value=f"{self.player_info['legendStatistics']['previousSeason']['id']} | {self.player_info['legendStatistics']['previousSeason']['trophies']}", inline=False)

        if 'league' in self.player_info and 'iconUrls' in self.player_info['league']:
            league_embed.set_thumbnail(url=self.player_info['league']['iconUrls']['medium'])
        
        embeds.append(league_embed)

        # Page 3: War Data
        war_embed = discord.Embed(
            title=f"{self.player_info['name']}",
            description=f"War Data",
            color=discord.Color.gold()
        )

        # Assuming 'warStars' is directly from the player_info
        war_embed.add_field(name="War Stars", value=self.player_info.get('warStars', 'Unknown'), inline=True)
        war_embed.add_field(name="War Preference", value=self.player_info.get('warPreference', 'Unknown'), inline=True)
        war_embed.add_field(name="**Clashbots Tracked Data**", value="------------------------", inline=False)
        # Fetch war stats from the JSON file
        player_tag = self.player_info['tag']
        player_stats = get_player_stats(player_tag)

        separator = "Clashbots Tracked Data"
        war_embed.add_field(name="🛡️ Wars", value=player_stats['wars_attacked'], inline=True)
        war_embed.add_field(name="✅ Completed", value=player_stats['used_all_attacks'], inline=True)
        war_embed.add_field(name="📈 Completion Rate", value=f"{player_stats['used_all_attacks'] / player_stats['wars_attacked']:.2f}" if player_stats['wars_attacked'] > 0 else "0.00", inline=True)

        war_embed.add_field(name="\u200b", value="\u200b", inline=False)  # Blank separator

        # Attack stats section
        war_embed.add_field(name="⚔️ Attacks", value=player_stats['total_attacks'], inline=True)
        war_embed.add_field(name="🏹 Possible Attacks", value=player_stats['total_possible_attacks'], inline=True)
        war_embed.add_field(name="📈 Attack Rate", value=f"{player_stats['total_attacks'] / player_stats['total_possible_attacks']:.2f}" if player_stats['total_possible_attacks'] > 0 else "0.00", inline=True)

        war_embed.add_field(name="\u200b", value="\u200b", inline=False)  # Blank separator

        # Star stats section
        war_embed.add_field(name="⭐ Stars", value=player_stats['total_stars'], inline=True)
        war_embed.add_field(name="✨ Average Stars", value=f"{player_stats['average_stars']:.2f}", inline=True)
        war_embed.add_field(name="📊 Star Efficiency", value=f"{(player_stats['total_stars'] / (player_stats['total_attacks'] * 3)) * 100:.2f}%" if player_stats['total_attacks'] > 0 else "0.00%", inline=True)

        war_embed.add_field(name="\u200b", value="\u200b", inline=False)  # Blank separator

        # Destruction stats section
        war_embed.add_field(name="🔥 Destruction", value=f"{player_stats['total_destruction_percentage']:.2f}%", inline=True)
        war_embed.add_field(name="💥 Average Destruction", value=f"{player_stats['average_destruction_percentage']:.2f}%", inline=True)
        war_embed.add_field(name="📊 Destruction Efficiency", value=f"{(player_stats['total_destruction_percentage'] / (player_stats['total_attacks'] * 100)) * 100:.2f}%" if player_stats['total_attacks'] > 0 else "0.00%", inline=True)

        war_embed.add_field(name="\u200b", value="\u200b", inline=False)  # Blank separator

        # Star type stats section
        war_embed.add_field(name="🌟🌟🌟", value=player_stats['three_stars'], inline=True)
        war_embed.add_field(name="⭐⭐", value=player_stats['two_stars'], inline=True)
        war_embed.add_field(name="⭐", value=player_stats['one_stars'], inline=True)

        war_embed.add_field(name="\u200b", value="\u200b", inline=False)  # Blank separator

        # Final stats section
        war_embed.add_field(name="🌟 3-Star Rate", value=f"{player_stats['three_stars'] / player_stats['total_attacks']:.2f}" if player_stats['total_stars'] > 0 else "0.00", inline=True)
        war_embed.add_field(name="🍩 Donuts", value=player_stats['total_attacks'] - (player_stats['three_stars'] + player_stats['two_stars'] + player_stats['one_stars']), inline=True)

        # Set thumbnail if league info exists
        if 'league' in self.player_info and 'iconUrls' in self.player_info['league']:
            war_embed.set_thumbnail(url=self.player_info['league']['iconUrls']['medium'])

        embeds.append(war_embed)
        # Page 4: Builder Data
        builder_embed = discord.Embed(
            title=f"{self.player_info['name']}",
            description=f"Builder Base Data",
            color=discord.Color.gold()
        )
        builder_embed.add_field(name="Builder Hall", value=self.player_info['builderHallLevel'], inline=False)
        builder_embed.add_field(name="League", value=self.player_info['builderBaseLeague']['name'], inline=False)
        builder_embed.add_field(name="Trophies", value=self.player_info['builderBaseTrophies'], inline=False)
        builder_embed.add_field(name="Peak", value=self.player_info['bestBuilderBaseTrophies'], inline=False)
        
        if 'league' in self.player_info and 'iconUrls' in self.player_info['league']:
            builder_embed.set_thumbnail(url=self.player_info['league']['iconUrls']['medium'])
        embeds.append(builder_embed)
        
        #Generate footers for embeds
        for i, embed in enumerate(embeds):
            embed.set_footer(text=f"Page {i + 1}/{len(embeds)}")
        return embeds

    @discord.ui.button(label="Previous", style=discord.ButtonStyle.primary)
    async def previous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page > 0:
            self.page -= 1
            await interaction.response.edit_message(embed=self.embeds[self.page], view=self)

    @discord.ui.button(label="Next", style=discord.ButtonStyle.primary)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page < len(self.embeds) - 1:
            self.page += 1
            await interaction.response.edit_message(embed=self.embeds[self.page], view=self)

    #Disable buttons upon timeout
    async def on_timeout(self):
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True

class WarTracker:
    def __init__(self, clan_tag):
        self.clan_tag = clan_tag
        self.war_end_time = None  # Track the war end time

    # Asynchronous polling function that runs automatically
    @tasks.loop(hours = 23)
    async def automatic_poll(self):
        print(f"Polling Clash of Clans API for war status for clan {self.clan_tag}")
        
        war_data = coc_api.get_current_war(self.clan_tag)
        
        # Check if there's no error and the war is in preparation or in progress
        if 'error' not in war_data and war_data['state'] == 'inWar':
            print(f"War detected for clan {self.clan_tag}, war state: {war_data['state']}")
            
            # Get war end time from API and convert it to datetime
            war_end_time_str = war_data['endTime']
            self.war_end_time = datetime.strptime(war_end_time_str, "%Y%m%dT%H%M%S.%fZ").replace(tzinfo=timezone.utc)
            
            # Calculate the exact time when to start frequent polling (15 minutes before war ends)
            time_until_frequent_poll = self.war_end_time - timedelta(minutes=15) - datetime.now(timezone.utc)
            
            # If the time until frequent polling is in the future, schedule the poll to begin
            if time_until_frequent_poll > timedelta(seconds=0):
                print(f"Scheduling frequent polling for {self.war_end_time - timedelta(minutes=15)}")
                await asyncio.sleep(time_until_frequent_poll.total_seconds())
                if not self.poll_war_end.is_running():
                    self.poll_war_end.start()  # Start frequent polling for the last 15 minutes
            else:
                print("War is already ending soon. Starting frequent polling now.")
                if not self.poll_war_end.is_running():
                    self.poll_war_end.start()
        else:
            print(f"No war in progress for clan {self.clan_tag}, checking again tomorrow.")
    
    # Poll every 5 minutes for the last 15 minutes of the war
    @tasks.loop(minutes=5)
    async def poll_war_end(self):
        time_remaining = self.war_end_time - datetime.now(timezone.utc)
        
        if time_remaining > timedelta(minutes=1):
            print(f"Polling API for final moments of war, time remaining: {time_remaining}")
            await self.manual_poll()
        else:
            # Once the war ends, stop frequent polling and switch back to daily polling
            print(f"War has ended for clan {self.clan_tag}. Stopping frequent polling.")
            self.poll_war_end.stop()  # Stop the frequent polling

            # Check if the automatic_poll is already running before starting it again
            if not self.automatic_poll.is_running():
                self.automatic_poll.start()  # Revert back to daily polling
            else:
                print("Daily polling is already running, no need to start again.")


    async def manual_poll(self):
        war_data = coc_api.get_current_war(self.clan_tag)
        war_attacks = war_data['attacksPerMember']
        if 'error' not in war_data and war_data['state'] == 'inWar':
            for member in war_data['clan']['members']:
                player_tag = member['tag']
                player_name = member['name']

                # For each attack, update player stats in JSON
                for attack in member.get('attacks', []):
                    war_id = war_data['endTime']  # Use war endTime as war_id
                    
                    attack_time = attack['order']  # The order of the attack
                    stars = attack['stars']
                    destruction = attack['destructionPercentage']
                    # Update player stats in JSON and avoid duplicates
                    update_player_stats(player_tag, player_name, war_id, attack_time, stars, destruction, war_attacks)

            return "War data updated successfully."
        return "No war in progress."
    

class WarStatusView(discord.ui.View):
    def __init__(self, war_info, timeout=180):
        super().__init__(timeout=timeout)
        self.embeds = self.generate_embeds(war_info)

    # Generate embeds for war information
    def generate_embeds(self, war_info):
        embeds = []
        war_state = war_info.get('state', 'No war in progress')
        
        # War in progress embed
        if war_state == 'inWar':
            embed = discord.Embed(
                title="Current War Status",
                description=f"Clan: {war_info['clan']['name']}\nOpponent: {war_info['opponent']['name']}",
                color=discord.Color.red()
            )
            embed.add_field(name="War Start Time", value=utils.format_time(war_info['startTime']), inline=True)
            embed.add_field(name="War End Time", value=utils.format_time(war_info['endTime']), inline=True)
            embed.add_field(name=" ", value=" ", inline=False)
            embed.add_field(name="Your Stars", value=war_info['clan']['stars'], inline=True)
            embed.add_field(name="Opponent Stars", value=war_info['opponent']['stars'], inline=True)
            embed.add_field(name=" ", value=" ", inline=False)
            embed.add_field(name="Your Destruction", value=f"{war_info['clan']['destructionPercentage']:.2f}%", inline=True)
            embed.add_field(name="Opponent Destruction", value=f"{war_info['opponent']['destructionPercentage']:.2f}%", inline=True)
            embed.add_field(name=" ", value=" ", inline=False)
            embed.set_thumbnail(url=war_info['clan']['badgeUrls']['medium'])
            embeds.append(embed)

        else:
            # Embed for no war or war not started
            embed = discord.Embed(
                title="No Current War",
                description="There is no war currently in progress for this clan.",
                color=discord.Color.gray()
            )
            embeds.append(embed)

        return embeds

def setup_commands(bot):
    #Register slash commands to bot
    @bot.tree.command(name="set_tag", description="Set the clan tag for this server")
    @commands.cooldown(rate=1, per=30, type=commands.BucketType.user)
    async def set_tag(interaction: discord.Interaction, clan_tag: str):
        user = interaction.user
        guild = interaction.guild
        guild_id = str(guild.id)

        # Load existing guild data
        guild_data = utils.load_guild_data()
        old_clan_tag = guild_data.get(guild_id, {}).get('clan_tag')

        # Check if the user is the server owner or an admin
        if guild.owner_id == user.id or user.guild_permissions.administrator:
            # Validate the new clan tag
            if not coc_api.validate_tag(clan_tag):
                await interaction.response.send_message(f"Invalid clan tag '{clan_tag}', try again.", ephemeral=True)
                return

            # Stop tracking for the old clan tag if it was enabled
            if old_clan_tag and old_clan_tag in tracked_servers and guild_id in tracked_servers[old_clan_tag]:
                tracked_servers[old_clan_tag].remove(guild_id)
                if not tracked_servers[old_clan_tag]:
                    print(f"Stopping auto-polling for old clan tag {old_clan_tag}")
                    active_clan_polling[old_clan_tag].automatic_poll.stop()
                    del active_clan_polling[old_clan_tag]
                    del tracked_servers[old_clan_tag]

            # Save the new clan tag
            utils.save_clan_tag(guild_id, clan_tag)

            # Inform the user they need to manually re-enable tracking if it was enabled for the old tag
            if old_clan_tag and old_clan_tag in tracked_servers:
                await interaction.response.send_message(
                    f"Clan tag '{clan_tag}' set. Must manually re-enable auto tracking if desired.",
                    ephemeral=False
                )
            else:
                await interaction.response.send_message(f"Clan tag '{clan_tag}' set.", ephemeral=False)
                return

        else:
            # Deny access if the user is not the server owner or an admin
            await interaction.response.send_message(
                "You do not have permission to use this command. Only the server owner or admins can set the clan tag.",
                ephemeral=True
            )
        
    
    # Get clan info
    @bot.tree.command(name="claninfo", description="Get basic clan information")
    @commands.cooldown(rate=1, per=30, type=commands.BucketType.user) 
    async def claninfo(interaction: discord.Interaction, clan_tag: str = None):
        if clan_tag is None:
            clan_tag = utils.get_clan_tag(interaction.guild_id)
        
        if clan_tag:
            clan_info = coc_api.get_clan_info(clan_tag)
            if 'error' in clan_info:
                await interaction.response.send_message("Could not retrieve clan info")
                return
            
            # Create an embed view for navigation
            view = ClanInfoView(clan_info)
            await interaction.response.send_message(embed=view.embeds[0], view=view)
        else:
            await interaction.response.send_message("No clan tag is set for this server. Use /set_tag <tag> to set one")
    
    # Get member list
    @bot.tree.command(name="members", description="Get list of members")
    @commands.cooldown(rate=1, per=30, type=commands.BucketType.user) 
    async def members(interaction: discord.Interaction):
        clan_tag = utils.get_clan_tag(interaction.guild_id)
        if clan_tag:
            clan_info = coc_api.get_clan_info(clan_tag)
            if 'error' in clan_info:
                await interaction.response.send_message("Could not retrieve clan info")
                return

            members = clan_info.get('memberList', [])
            if not members:
                await interaction.response.send_message("No members found in the clan")
                return

            # Create the view with pagination
            view = MembersView(clan_info, members)
            await interaction.response.send_message(embed=view.embeds[0], view=view)
        else:
            await interaction.response.send_message("No clan tag is set for this server. Use /set_tag <tag> to set one")
    
    # Get player info
    @bot.tree.command(name="player", description="Get player data with player tag")
    @commands.cooldown(rate=1, per=30, type=commands.BucketType.user) 
    async def player(interaction: discord.Interaction, player_input: str):
        # If input starts with '#', treat it as a player tag
        if player_input.startswith("#"):
            player_tag = player_input
        else:
            # Otherwise, treat it as a username and try to find the player in the clan
            clan_tag = utils.get_clan_tag(interaction.guild_id)
            if not clan_tag:
                await interaction.response.send_message("No clan tag is set for this server. Use /set_tag <tag> to set one.")
                return

            # Fetch clan information
            clan_info = coc_api.get_clan_info(clan_tag)
            if 'error' in clan_info:
                await interaction.response.send_message("Could not retrieve clan info")
                return

            # Search for the player in the clan by name
            members = clan_info.get('memberList', [])
            matching_member = next((member for member in members if member['name'].lower() == player_input.lower()), None)

            if not matching_member:
                await interaction.response.send_message(f"No player with the name '{player_input}' found in the clan.")
                return

            # Get the player tag from the matching member
            player_tag = matching_member['tag']

        # Fetch player info from the API
        player_info = coc_api.get_player_info(player_tag)

        if 'error' in player_info:
            await interaction.response.send_message(f"Could not retrieve data for player with tag {player_tag}")
            return

        
        view = PlayerInfoView(player_info, interaction)
        await interaction.response.send_message(embed=view.embeds[0], view=view)
    
    @bot.tree.command(name="pollwar", description="Manually poll for current war data")
    @commands.cooldown(rate=1, per=600, type=commands.BucketType.user)  # 1 use per 10 minutes per user
    async def poll_war(interaction: discord.Interaction):
        clan_tag = utils.get_clan_tag(interaction.guild_id)
        war_tracker = WarTracker(clan_tag)
        result_message = await war_tracker.manual_poll()
        await interaction.response.send_message(result_message) 

    @bot.tree.command(name="warstats", description="Get player war statistics by player name (in clan) or tag")
    @commands.cooldown(rate=1, per=30, type=commands.BucketType.user) 
    async def warstats(interaction: discord.Interaction, player_input: str):
        # If input starts with '#', treat it as a player tag
        if player_input.startswith("#"):
            player_tag = player_input
        else:
            # Otherwise, treat it as a username and try to find the player in the clan
            clan_tag = utils.get_clan_tag(interaction.guild_id)
            if not clan_tag:
                await interaction.response.send_message("No clan tag is set for this server. Use /set_tag <tag> to set one.")
                return

            # Fetch clan information
            clan_info = coc_api.get_clan_info(clan_tag)
            if 'error' in clan_info:
                await interaction.response.send_message("Could not retrieve clan info")
                return

            # Search for the player in the clan by name
            members = clan_info.get('memberList', [])
            matching_member = next((member for member in members if member['name'].lower() == player_input.lower()), None)

            if not matching_member:
                await interaction.response.send_message(f"No player with the name '{player_input}' found in the clan.")
                return

            # Get the player tag from the matching member
            player_tag = matching_member['tag']

        # Fetch player info from the API
        player_stats = get_player_stats(player_tag)
        
        if player_stats is None:
            await interaction.response.send_message(f"No data found for player {player_tag}")
            return  # Exit early to avoid further interaction responses

        # Continue only if player_stats exists
        embed = discord.Embed(
            title=f"{player_stats['name']} | {player_tag}",
            description=f"Clashbots Tracked War Stats",
            color=discord.Color.red()
        )
        # War stats section
        embed.add_field(name="🛡️ Wars", value=player_stats['wars_attacked'], inline=True)
        embed.add_field(name="✅ Completed", value=player_stats['used_all_attacks'], inline=True)
        embed.add_field(name="📈 Completion Rate", value=f"{player_stats['used_all_attacks'] / player_stats['wars_attacked']:.2f}" if player_stats['wars_attacked'] > 0 else "0.00", inline=True)

        embed.add_field(name="\u200b", value="\u200b", inline=False)  # Blank separator

        # Attack stats section
        embed.add_field(name="⚔️ Attacks", value=player_stats['total_attacks'], inline=True)
        embed.add_field(name="🏹 Possible Attacks", value=player_stats['total_possible_attacks'], inline=True)
        embed.add_field(name="📈 Attack Rate", value=f"{player_stats['total_attacks'] / player_stats['total_possible_attacks']:.2f}" if player_stats['total_possible_attacks'] > 0 else "0.00", inline=True)

        embed.add_field(name="\u200b", value="\u200b", inline=False)  # Blank separator

        # Star stats section
        embed.add_field(name="⭐ Stars", value=player_stats['total_stars'], inline=True)
        embed.add_field(name="✨ Average Stars", value=f"{player_stats['average_stars']:.2f}", inline=True)
        embed.add_field(name="📊 Star Efficiency", value=f"{(player_stats['total_stars'] / (player_stats['total_attacks'] * 3)) * 100:.2f}%" if player_stats['total_attacks'] > 0 else "0.00%", inline=True)

        embed.add_field(name="\u200b", value="\u200b", inline=False)  # Blank separator

        # Destruction stats section
        embed.add_field(name="🔥 Destruction", value=f"{player_stats['total_destruction_percentage']:.2f}%", inline=True)
        embed.add_field(name="💥 Average Destruction", value=f"{player_stats['average_destruction_percentage']:.2f}%", inline=True)
        embed.add_field(name="📊 Destruction Efficiency", value=f"{(player_stats['total_destruction_percentage'] / (player_stats['total_attacks'] * 100)) * 100:.2f}%" if player_stats['total_attacks'] > 0 else "0.00%", inline=True)

        embed.add_field(name="\u200b", value="\u200b", inline=False)  # Blank separator

        # Star type stats section
        embed.add_field(name="🌟🌟🌟", value=player_stats['three_stars'], inline=True)
        embed.add_field(name="⭐⭐", value=player_stats['two_stars'], inline=True)
        embed.add_field(name="⭐", value=player_stats['one_stars'], inline=True)

        embed.add_field(name="\u200b", value="\u200b", inline=False)  # Blank separator

        # Final stats section
        embed.add_field(name="🌟 3-Star Rate", value=f"{player_stats['three_stars'] / player_stats['total_attacks']:.2f}" if player_stats['total_stars'] > 0 else "0.00", inline=True)
        embed.add_field(name="🍩 Donuts", value=player_stats['total_attacks'] - (player_stats['three_stars'] + player_stats['two_stars'] + player_stats['one_stars']), inline=True)

        await interaction.response.send_message(embed=embed)

    @bot.tree.command(name="currentwar", description="Get player war statistics by player name (in clan) or tag")
    @commands.cooldown(rate=1, per=30, type=commands.BucketType.user)
    async def currentwar(interaction: discord.Interaction, clan_tag: str = None):
        # Get the clan tag either from the argument or from the server's saved data
        if clan_tag is None:
            clan_tag = utils.get_clan_tag(interaction.guild_id)

        if clan_tag:
            war_info = coc_api.get_current_war(clan_tag)
            if 'error' in war_info:
                await interaction.response.send_message("Could not retrieve war info")
                return
            view = WarStatusView(war_info)
            await interaction.response.send_message(embed=view.embeds[0], view=view)
        else:
            await interaction.response.send_message("No clan tag is set for this server. Use /set_tag <tag> to set one or provide a tag manually.")


    @bot.tree.command(name="enablewartracking", description="Enable automatic polling for the server's set clan tag") 
    async def enable_wartracking(interaction: discord.Interaction):
        guild_id = str(interaction.guild_id)
        guild_data = utils.load_guild_data()

        # Ensure a clan tag is set
        if guild_id not in guild_data or not guild_data[guild_id]["clan_tag"]:
            await interaction.response.send_message("No clan tag is set for this server. Use /set_tag <tag> to set one.")
            return

        clan_tag = guild_data[guild_id]["clan_tag"]

        # Check if auto-polling is already enabled
        if guild_data[guild_id]["auto_polling"]:
            await interaction.response.send_message(f"Auto-polling for clan {clan_tag} is already enabled in this server.")
            return

        # Update the JSON file to enable auto-polling
        guild_data[guild_id]["auto_polling"] = True
        utils.save_guild_data(guild_data)

        # Start polling for the clan if it's not already being polled
        if clan_tag not in tracked_servers:
            war_tracker = WarTracker(clan_tag)
            active_clan_polling[clan_tag] = war_tracker
            war_tracker.automatic_poll.start()
            tracked_servers[clan_tag] = [guild_id]
        else:
            tracked_servers[clan_tag].append(guild_id)

        await interaction.response.send_message(f"Automatic war tracking enabled for clan {clan_tag} in this server.")

    @bot.tree.command(name="disablewartracking", description="Disable automatic polling for the server's set clan tag")
    async def disable_wartracking(interaction: discord.Interaction):
        guild_id = str(interaction.guild_id)
        guild_data = utils.load_guild_data()

        if guild_id not in guild_data or not guild_data[guild_id]["clan_tag"]:
            await interaction.response.send_message("No clan tag is set for this server.")
            return

        clan_tag = guild_data[guild_id]["clan_tag"]

        # Check if auto-polling is actually enabled
        if not guild_data[guild_id]["auto_polling"]:
            await interaction.response.send_message(f"Auto-polling for clan {clan_tag} is not enabled in this server.")
            return

        # Update the JSON file to disable auto-polling
        guild_data[guild_id]["auto_polling"] = False
        utils.save_guild_data(guild_data)

        # Remove the guild from the tracked_servers list for this clan
        tracked_servers[clan_tag].remove(guild_id)

        # If no more servers are tracking this clan, stop polling
        if not tracked_servers[clan_tag]:
            active_clan_polling[clan_tag].automatic_poll.stop()
            del active_clan_polling[clan_tag]
            del tracked_servers[clan_tag]
            print(f"Stopped all auto-polling for {clan_tag}")

        await interaction.response.send_message(f"Automatic war tracking disabled for clan {clan_tag} in this server.")