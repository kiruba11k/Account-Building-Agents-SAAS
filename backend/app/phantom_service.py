import os
import requests

# --------------------------------------------------
# ENV VARIABLES
# --------------------------------------------------

PHANTOM_API_KEY = os.getenv("PHANTOM_API_KEY")
PHANTOM_AGENT_ID = os.getenv("PHANTOM_AGENT_ID")
PHANTOM_IDENTITY_ID = os.getenv("PHANTOM_IDENTITY_ID")

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
        "clearCache": True,
        "clearOutput": True,
        "argument": {

            "inputType": "salesNavigatorSearchUrl",

            "salesNavigatorSearchUrl": search_url,

            "numberOfProfiles": 2500,
            "numberOfResultsPerSearch": 2500,
            "numberOfLinesPerLaunch": 10,
            "removeDuplicateProfiles": False,

            "identities": [
                {
                    "identityId": PHANTOM_IDENTITY_ID,
                    "sessionCookie": "",
                    "userAgent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36"
                }
            ]
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
# Clear previous Phantom output
# --------------------------------------------------

def clear_agent_output():

    payload = {"id": PHANTOM_AGENT_ID}

    # Phantombuster endpoints/parameter styles may differ across API versions.
    attempts = [
        ("post", "/agents/clear-output", {"json": payload}),
        ("post", "/agents/delete-output", {"json": payload}),
        ("post", "/agents/clearOutput", {"json": payload}),
        ("post", "/agents/clear-output", {"params": payload}),
        ("post", "/agents/delete-output", {"params": payload}),
        ("post", "/agents/clearOutput", {"params": payload}),
    ]

    last_error = None

    for method, endpoint, kwargs in attempts:
        try:
            request_fn = getattr(requests, method)
            r = request_fn(f"{BASE_URL}{endpoint}", headers=HEADERS, timeout=30, **kwargs)

            if 200 <= r.status_code < 300:
                response = r.json() if r.content else {"ok": True}
                print("Phantom clear output response:", response)
                return response

            last_error = f"{method.upper()} {endpoint} returned {r.status_code}: {r.text}"
        except Exception as e:
            last_error = f"{method.upper()} {endpoint} failed: {str(e)}"

    print("Phantom clear output warning:", last_error)

    return {
        "warning": "Unable to clear previous Phantom output",
        "details": last_error
    }


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
# Normalize Results
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
