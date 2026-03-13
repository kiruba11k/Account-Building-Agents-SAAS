import os
import requests

# --------------------------------------------------
# ENV VARIABLES
# --------------------------------------------------

PHANTOM_API_KEY = os.getenv("PHANTOM_API_KEY")
PHANTOM_AGENT_ID = os.getenv("PHANTOM_AGENT_ID")

BASE_URL = "https://api.phantombuster.com/api/v2"

HEADERS = {
    "X-Phantombuster-Key-1": PHANTOM_API_KEY,
    "Content-Type": "application/json"
}


# --------------------------------------------------
# Launch Phantom Agent
# --------------------------------------------------

def launch_company_search(search_url):

    payload = {
        "id": PHANTOM_AGENT_ID,
        "argument": {
            # Most Sales Navigator phantoms expect this field
            "searches": [search_url]
        }
    }

    try:
        r = requests.post(
            f"{BASE_URL}/agents/launch",
            json=payload,
            headers=HEADERS,
            timeout=30
        )

        r.raise_for_status()

        response = r.json()

    except Exception as e:

        response = {
            "error": str(e),
            "payload": payload
        }

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

    r.raise_for_status()

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

    r.raise_for_status()

    response = r.json()

    print("Container output:", response)

    return response


# --------------------------------------------------
# Normalize Phantom Results
# --------------------------------------------------

def fetch_container_results(container_id):

    output = fetch_container_output(container_id)

    if isinstance(output, dict):

        if isinstance(output.get("data"), list):
            return output["data"]

        if isinstance(output.get("results"), list):
            return output["results"]

        if isinstance(output.get("items"), list):
            return output["items"]

    return []
