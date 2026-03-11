

import requests
import os
import time

PHANTOM_API_KEY = os.getenv("PHANTOM_API_KEY")

BASE_URL = "https://api.phantombuster.com/api/v2"

HEADERS = {
    "X-Phantombuster-Key-1": PHANTOM_API_KEY,
    "Content-Type": "application/json"
}

SEARCH_AGENT_ID = os.getenv("PHANTOM_AGENT_ID")


# --------------------------------------------------
# Launch Phantom Agent
# --------------------------------------------------

def launch_company_search(search_url):

    payload = {
        "id": SEARCH_AGENT_ID,
        "argument": {
            "searches": [search_url],
            "numberOfResultsPerLaunch": 100
        }
    }

    r = requests.post(
        f"{BASE_URL}/agents/launch",
        json=payload,
        headers=HEADERS,
        timeout=30
    )

    response = r.json()

    print("Phantom launch response:", response)

    return response


# --------------------------------------------------
# Check Container Status
# --------------------------------------------------

def get_container_status(container_id):

    r = requests.get(
        f"{BASE_URL}/containers/fetch",
        params={"id": container_id},
        headers=HEADERS,
        timeout=30
    )

    response = r.json()

    print("Container status:", response)

    return response


# --------------------------------------------------
# Fetch Phantom Output
# --------------------------------------------------

def fetch_container_output(container_id):

    r = requests.get(
        f"{BASE_URL}/containers/fetch-output",
        params={"id": container_id},
        headers=HEADERS,
        timeout=30
    )

    response = r.json()

    print("Container output:", response)

    return response
