import requests
import os

PHANTOM_API_KEY = os.getenv("PHANTOM_API_KEY")

BASE_URL = "https://api.phantombuster.com/api/v2"

HEADERS = {
    "X-Phantombuster-Key-1": PHANTOM_API_KEY,
    "Content-Type": "application/json"
}

SEARCH_AGENT_ID = os.getenv("PHANTOM_AGENT_ID")


def launch_company_search(search_url):

    payload = {
        "id": SEARCH_AGENT_ID,
        "argument": {
            "searches": [search_url]
        }
    }

    r = requests.post(
        f"{BASE_URL}/agents/launch",
        json=payload,
        headers=HEADERS,
        timeout=30
    )
    print("Phantom launch response:", r.text)
    return r.json()


def get_container_status(container_id):

    r = requests.get(
        f"{BASE_URL}/containers/fetch",
        params={"id": container_id},
        headers=HEADERS,
        timeout=30
    )

    return r.json()


def fetch_container_output(container_id):

    r = requests.get(
        f"{BASE_URL}/containers/fetch-output",
        params={"id": container_id},
        headers=HEADERS,
        timeout=30
    )

    return r.json()
