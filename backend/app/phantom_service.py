import requests
import os

PHANTOM_API_KEY = os.getenv("PHANTOM_API_KEY")
PHANTOM_AGENT_ID = os.getenv("PHANTOM_AGENT_ID")

BASE_URL = "https://api.phantombuster.com/api/v2"

headers = {
    "X-Phantombuster-Key-1": PHANTOM_API_KEY,
    "Content-Type": "application/json"
}

def launch_agent(filters):
    url = f"{BASE_URL}/agents/launch"
    payload = {
        "id": PHANTOM_AGENT_ID,
        "argument": filters
    }
    response = requests.post(url, json=payload, headers=headers)
    return response.json()

def get_container_status(container_id):
    url = f"{BASE_URL}/containers/fetch"
    response = requests.get(url, headers=headers, params={"id": container_id})
    return response.json()

def fetch_container_output(container_id):
    url = f"{BASE_URL}/containers/fetch-output"
    response = requests.get(url, headers=headers, params={"id": container_id})
    return response.json()
