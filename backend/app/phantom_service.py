import os
import re
import json
import csv
from io import StringIO
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

    last_error = None

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

            last_error = f"{endpoint} returned {r.status_code}: {r.text}"
        except Exception as e:
            last_error = f"{endpoint} failed: {str(e)}"

    print(f"Phantom {action_name} warning:", last_error)

    return {
        "warning": f"Unable to {action_name} on Phantom agent",
        "details": last_error
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
                    # Reuse the authenticated PhantomBuster identity that was
                    # connected manually once. Passing empty session cookies can
                    # override stored identity sessions and force re-auth.
                    "identityId": PHANTOM_IDENTITY_ID,
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
        "/agent/delete-output",
    ]

    return _post_to_first_success(endpoints, payload, "clear output")


def clear_agent_cache():

    payload = {"id": PHANTOM_AGENT_ID}

    # Cache reset endpoint names may vary by API version.
    endpoints = [
        "/agents/clear-cache",
        "/agent/clear-cache",
        "/agents/delete-cache",
        "/agent/delete-cache",
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

    def _from_tabular_string(raw_value):

        if not isinstance(raw_value, str):
            return []

        text = raw_value.strip()

        if not text:
            return []

        try:
            parsed = json.loads(text)

            if isinstance(parsed, list):
                return parsed

            if isinstance(parsed, dict):
                for nested_key in ["data", "results", "items", "rows"]:
                    nested = parsed.get(nested_key)

                    if isinstance(nested, list):
                        return nested
        except Exception:
            pass

        delimiter = "\t" if "\t" in text else ","

        try:
            rows = list(csv.DictReader(StringIO(text), delimiter=delimiter))
            return [row for row in rows if any(row.values())]
        except Exception:
            return []

    def _extract_rows(payload):

        if isinstance(payload, list):
            return payload

        if not isinstance(payload, dict):
            return []

        for key in ["data", "results", "items", "rows"]:
            candidate = payload.get(key)

            if isinstance(candidate, list):
                return candidate

            if isinstance(candidate, str):
                parsed_rows = _from_tabular_string(candidate)

                if parsed_rows:
                    return parsed_rows

            if isinstance(candidate, dict):
                nested_rows = _extract_rows(candidate)

                if nested_rows:
                    return nested_rows

        for key in ["output", "resultObject", "result", "csv", "json"]:
            candidate = payload.get(key)

            if isinstance(candidate, str):
                parsed_rows = _from_tabular_string(candidate)

                if parsed_rows:
                    return parsed_rows

            if isinstance(candidate, dict):
                nested_rows = _extract_rows(candidate)

                if nested_rows:
                    return nested_rows

        return []

    return _extract_rows(output)
