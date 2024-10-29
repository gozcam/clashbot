import json
from utils import format_time
import os
from filelock import FileLock
# Path to the JSON file where player stats are stored
STATS_FILE = 'player_stats.json'
LOCK_FILE = '.lock'

# Load player data from JSON
def load_player_data():
    lock = FileLock(LOCK_FILE)
    with lock: 
        if os.path.exists(STATS_FILE):
            with open(STATS_FILE, 'r') as f:
                return json.load(f)
        return {"players": {}}

# Save player data to JSON
def save_player_data(data):
    lock = FileLock(LOCK_FILE)
    with lock:
        with open(STATS_FILE, 'w') as f:
            json.dump(data, f, indent=4)

# Check if an attack already exists for a player
def is_duplicate_attack(player_data, war_id, attack_time):
    for attack in player_data.get('attacks', []):
        if attack['war_id'] == war_id and attack['attack_time'] == attack_time:
            return True
    return False
            
def remove_oldest_attack(player_data):
    if len(player_data['attacks']) > 4:
        player_data['attacks'].pop(0)

# Update player stats after a war attack
def update_player_stats(player_tag, player_name, war_id, attack_time, stars, destruction_percentage, war_attacks):
    data = load_player_data()

    if player_tag not in data['players']:
        data['players'][player_tag] = {
            "name": player_name,
            "total_attacks": 0,
            "total_stars": 0,
            "total_destruction_percentage": 0.0,
            "average_stars": 0.0,
            "average_destruction_percentage": 0.0,
            "three_stars": 0,
            "two_stars": 0,
            "one_stars": 0,
            "total_possible_attacks": 0,
            "wars_attacked": 0,
            "used_all_attacks": 0,
            "attacked_this_war": 0,
            "wars": [],
            "attacks": [] 
        }

    player_data = data['players'][player_tag]
    
    # Check if this attack has already been recorded to avoid duplicates
    if is_duplicate_attack(player_data, war_id, attack_time):
        print(f"Duplicate attack detected for player {player_name} in war {war_id}. Skipping...")
        return  # Skip this attack if it's already recorded

    # Add attack to player's attack list
    player_data['attacks'].append({
        "war_id": war_id,
        "attack_time": attack_time,
        "stars": stars,
        "destruction_percentage": destruction_percentage
    })

    # Remove oldest attack if the player has more than 4 attacks recorded
    remove_oldest_attack(player_data)
    # Add war to war list if not there, and also add to possible attacks
    if war_id not in player_data['wars']:
        if len(player_data['wars']) > 8:
            player_data['attacks'].pop(0)
        player_data['wars'].append(war_id)
        player_data['wars_attacked'] += 1
        player_data['total_possible_attacks'] += war_attacks
        player_data['attacked_this_war'] = 1
    else:
        player_data['attacked_this_war'] += 1

    # Update player stats
    if player_data['attacked_this_war'] == war_attacks:
        player_data['used_all_attacks'] += 1
        # Set attacked this war = 3 in case cloning issue: label already added to used all attacks
        player_data['attacked_this_war'] = 3
    player_data['total_attacks'] += 1
    player_data['total_stars'] += stars
    player_data['total_destruction_percentage'] += destruction_percentage
    if stars == 3:
        player_data['three_stars'] += 1
    elif stars == 2:
        player_data['two_stars'] += 1   
    elif stars == 1:
        player_data['one_stars'] += 1 

    # Recalculate rates
    player_data['average_stars'] = player_data['total_stars'] / player_data['total_attacks']
    player_data['average_destruction_percentage'] = player_data['total_destruction_percentage'] / player_data['total_attacks']

    save_player_data(data)


# Fetch stats for a player (for /playerinfo command)
def get_player_stats(player_tag):
    data = load_player_data()

    return data['players'].get(player_tag, None)

