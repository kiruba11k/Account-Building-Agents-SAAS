

import requests
import os

PHANTOM_API_KEY = os.getenv("PHANTOM_API_KEY")

BASE_URL = "https://api.phantombuster.com/api/v2"

HEADERS = {
    "X-Phantombuster-Key-1": PHANTOM_API_KEY,
    "Content-Type": "application/json"
}

SEARCH_AGENT_ID = os.getenv("PHANTOM_AGENT_ID")


def _extract_output_url(payload):
    """Get downloadable output URL from various Phantombuster response shapes."""
    if not isinstance(payload, dict):
        return None

    for key in ("url", "output", "outputUrl", "downloadUrl"):
        value = payload.get(key)
        if isinstance(value, str) and value.startswith("http"):
            return value

    for key in ("data", "result", "container"):
        nested = payload.get(key)
        if isinstance(nested, dict):
            url = _extract_output_url(nested)
            if url:
                return url

    return None


def _download_json_output(url):
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    data = r.json()
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("data", "results", "items"):
            value = data.get(key)
            if isinstance(value, list):
                return value
    return []


def fetch_container_results(container_id):
    """Return normalized list of result items from Phantombuster output."""
    response = fetch_container_output(container_id)

    if isinstance(response, dict):
        direct_data = response.get("data")
        if isinstance(direct_data, list):
            return direct_data

        for key in ("results", "items"):
            value = response.get(key)
            if isinstance(value, list):
                return value

    output_url = _extract_output_url(response)
    if output_url:
        try:
            return _download_json_output(output_url)
        except Exception as e:
            print("Failed to download Phantom output URL:", e)

    return []


# --------------------------------------------------
# Launch Phantom Agent
# --------------------------------------------------

def launch_company_search(search_url, runtime_options=None):

    payload = {
        "id": SEARCH_AGENT_ID,
        "argument": {
            # Different Sales Navigator Phantoms use different field names.
            # Provide both compatible shapes to satisfy schema variants.
            "searches": search_url,
            "queries": [search_url],
            "numberOfResultsPerLaunch": 100
        }
    }

    has_auth = any(
        payload["argument"].get(k)
        for k in ("sessionCookie", "identityId", "identities")
    )
    if not has_auth:
        return {
            "error": "Missing Phantom auth argument. Provide sessionCookie, identityId, or identities.",
            "payload": payload,
        }

    r = requests.post(
        f"{BASE_URL}/agents/launch",
        json=payload,
        headers=HEADERS,
        timeout=30
    )
    r.raise_for_status()

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
