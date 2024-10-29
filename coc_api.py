import requests
import os
from dotenv import load_dotenv
load_dotenv()
CLASH_TOKEN = os.getenv('CLASH_TOKEN')


def validate_tag(clan_tag: str) -> bool:
    #print(f'{CLASH_TOKEN}')
    url = f'https://api.clashofclans.com/v1/clans/{clan_tag.replace("#", "%23")}'
    headers = {
        'Authorization': f'Bearer {CLASH_TOKEN}'
    }
    response = requests.get(url, headers=headers)

    #print(f"Request URL: {url}")
    #print(f"Response Status Code: {response.status_code}")
    #print(f"Response Content: {response.text}") 
    return response.status_code == 200

def get_clan_info(clan_tag: str) -> dict:
    url = f'https://api.clashofclans.com/v1/clans/{clan_tag.replace("#", "%23")}'
    headers = {
        'Authorization': f'Bearer {CLASH_TOKEN}'
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json()
    return {"error": "Failed to fetch clan info"}

def get_player_info(player_tag: str) -> dict:
    url = f'https://api.clashofclans.com/v1/players/{player_tag.replace("#", "%23")}'
    headers = {
        'Authorization': f'Bearer {CLASH_TOKEN}'
    }
    
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json()
    return {"error": "Failed to fetch player info"}

def get_current_war(clan_tag: str) -> dict:
    url = f'https://api.clashofclans.com/v1/clans/{clan_tag.replace("#", "%23")}/currentwar'
    headers = {
        'Authorization': f'Bearer {CLASH_TOKEN}'
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json()
    return {"error": "Failed to fetch war info"}