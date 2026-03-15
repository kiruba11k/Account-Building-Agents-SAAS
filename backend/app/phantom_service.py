import os
import re
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


def _post_to_first_success(endpoint_candidates, payload, action_name):

    errors = []

    for endpoint in endpoint_candidates:
        try:
            r = requests.post(
                f"{BASE_URL}{endpoint}",
                json=payload,
                headers=HEADERS,
                timeout=30
            )

            if 200 <= r.status_code < 300:
                response = r.json() if r.content else {"ok": True}
                print(f"Phantom {action_name} response:", response)
                return response

            errors.append({
                "endpoint": endpoint,
                "status_code": r.status_code,
                "body": r.text
            })
        except Exception as e:
            errors.append({
                "endpoint": endpoint,
                "error": str(e)
            })

    only_not_found = errors and all(
        isinstance(item.get("status_code"), int) and item.get("status_code") == 404
        for item in errors
    )

    if only_not_found:
        print(f"Phantom {action_name} info: clear endpoint not available on this API version")
        return {
            "info": f"No supported endpoint found to {action_name}",
            "details": errors
        }

    print(f"Phantom {action_name} warning:", errors)

    return {
        "warning": f"Unable to {action_name} on Phantom agent",
        "details": errors
    }


def extract_container_id(response):

    if not isinstance(response, dict):
        return None

    candidates = [
        response.get("containerId"),
        (response.get("data") or {}).get("containerId"),
        (response.get("container") or {}).get("id"),
        (response.get("data") or {}).get("id") if isinstance(response.get("data"), dict) else None,
    ]

    for candidate in candidates:
        if candidate is None:
            continue

        candidate_str = str(candidate).strip()

        if re.fullmatch(r"\d+", candidate_str):
            return candidate_str

    return None


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

    # Phantombuster has used different endpoint names over time.
    # Try known variants so a stale output object does not leak into new launches.
    endpoints = [
        "/agents/clear-output",
        "/agent/clear-output",
        "/agents/delete-output",
        "/agent/delete-output"
    ]

    return _post_to_first_success(endpoints, payload, "clear output")


def clear_agent_cache():

    payload = {"id": PHANTOM_AGENT_ID}

    # Cache reset endpoint names may vary by API version.
    endpoints = [
        "/agents/clear-cache",
        "/agent/clear-cache",
        "/agents/delete-cache",
        "/agent/delete-cache"
    ]

    return _post_to_first_success(endpoints, payload, "clear cache")


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
