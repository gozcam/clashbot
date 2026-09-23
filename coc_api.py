import os

import requests
from dotenv import load_dotenv

load_dotenv()
CLASH_TOKEN = os.getenv('CLASH_TOKEN')
API_BASE_URL = 'https://api.clashofclans.com/v1'
REQUEST_TIMEOUT = 10


def _get(path: str) -> dict:
    if not CLASH_TOKEN:
        return {"error": "CLASH_TOKEN is not configured"}

    try:
        response = requests.get(
            f'{API_BASE_URL}/{path}',
            headers={'Authorization': f'Bearer {CLASH_TOKEN}'},
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException as error:
        return {"error": f"Clash of Clans API request failed: {error}"}
    except ValueError:
        return {"error": "Clash of Clans API returned invalid JSON"}


def validate_tag(clan_tag: str) -> bool:
    return 'error' not in get_clan_info(clan_tag)

def get_clan_info(clan_tag: str) -> dict:
    return _get(f'clans/{clan_tag.replace("#", "%23")}')

def get_player_info(player_tag: str) -> dict:
    return _get(f'players/{player_tag.replace("#", "%23")}')

def get_current_war(clan_tag: str) -> dict:
    return _get(f'clans/{clan_tag.replace("#", "%23")}/currentwar')
