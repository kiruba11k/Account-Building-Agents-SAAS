import os
import requests

# --------------------------------------------------
# ENV VARIABLES
# --------------------------------------------------

PHANTOM_API_KEY = os.getenv("PHANTOM_API_KEY")
PHANTOM_AGENT_ID = os.getenv("PHANTOM_AGENT_ID")

# LinkedIn cookie (li_at)
PHANTOM_SESSION_COOKIE = os.getenv("PHANTOM_SESSION_COOKIE")

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

            # Sales Navigator search URL
            "searches": [search_url],

            # LinkedIn auth cookie
            "sessionCookie": PHANTOM_SESSION_COOKIE,

            # optional but recommended
            "numberOfResultsPerLaunch": 100
        }
    }

    try:

        response = requests.post(
            f"{BASE_URL}/agents/launch",
            json=payload,
            headers=HEADERS,
            timeout=30
        )

        response.raise_for_status()

        data = response.json()

    except Exception as e:

        data = {
            "error": str(e),
            "payload": payload
        }

    print("Phantom launch response:", data)

    return data


# --------------------------------------------------
# Get Container Status
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
# Fetch Container Output
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
