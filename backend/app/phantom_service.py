import os
import re
import csv
import json
from io import StringIO
from typing import Any, Dict, List

import requests

PHANTOM_API_KEY = os.getenv("PHANTOM_API_KEY")
PHANTOM_AGENT_ID = os.getenv("PHANTOM_AGENT_ID")
PHANTOM_IDENTITY_ID = os.getenv("PHANTOM_IDENTITY_ID")

BASE_URL = "https://api.phantombuster.com/api/v2"

HEADERS = {
    "X-Phantombuster-Key-1": PHANTOM_API_KEY,
    "Content-Type": "application/json",
}


def _safe_json(response):
    try:
        return response.json()
    except Exception:
        return {"raw_text": response.text}


def _post_to_first_success(endpoint_candidates, payload, action_name):
    last_error = None

    for endpoint in endpoint_candidates:
        try:
            r = requests.post(
                f"{BASE_URL}{endpoint}",
                json=payload,
                headers=HEADERS,
                timeout=30,
            )

            if 200 <= r.status_code < 300:
                response = _safe_json(r) if r.content else {"ok": True}
                print(f"[Phantom] {action_name} response:", response)
                return response

            last_error = f"{endpoint} returned {r.status_code}: {r.text}"
        except Exception as e:
            last_error = f"{endpoint} failed: {str(e)}"

    print(f"[Phantom] {action_name} warning:", last_error)

    return {
        "warning": f"Unable to {action_name} on Phantom agent",
        "details": last_error,
    }


def extract_container_id(response):
    if not isinstance(response, dict):
        return None

    candidates = [
        response.get("containerId"),
        (response.get("data") or {}).get("containerId") if isinstance(response.get("data"), dict) else None,
        (response.get("container") or {}).get("id") if isinstance(response.get("container"), dict) else None,
        (response.get("data") or {}).get("id") if isinstance(response.get("data"), dict) else None,
        response.get("id"),
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
                }
            ],
        },
    }

    try:
        r = requests.post(
            f"{BASE_URL}/agents/launch",
            json=payload,
            headers=HEADERS,
            timeout=30,
        )
        r.raise_for_status()
        response = _safe_json(r)
    except Exception as e:
        response = {
            "error": str(e),
            "payload": payload,
        }

    print("[Phantom] launch response:", response)
    return response


# --------------------------------------------------
# Optional cleanup endpoints
# not relied upon
# --------------------------------------------------

def clear_agent_output():
    payload = {"id": PHANTOM_AGENT_ID}

    endpoints = [
        "/agents/clear-output",
        "/agent/clear-output",
        "/agents/delete-output",
        "/agent/delete-output",
    ]

    return _post_to_first_success(endpoints, payload, "clear output")


def clear_agent_cache():
    payload = {"id": PHANTOM_AGENT_ID}

    endpoints = [
        "/agents/clear-cache",
        "/agent/clear-cache",
        "/agents/delete-cache",
        "/agent/delete-cache",
    ]

    return _post_to_first_success(endpoints, payload, "clear cache")


# --------------------------------------------------
# Container status
# --------------------------------------------------

def get_container_status(container_id):
    r = requests.get(
        f"{BASE_URL}/containers/fetch",
        params={"id": container_id},
        headers=HEADERS,
        timeout=30,
    )
    r.raise_for_status()
    response = _safe_json(r)
    print("[Phantom] container status:", response)
    return response


# --------------------------------------------------
# Container result object
# --------------------------------------------------

def fetch_container_result_object(container_id):
    """
    Prefer this over fetch-output if available.
    """
    candidate_endpoints = [
        "/containers/fetch-result-object",
        "/container/fetch-result-object",
    ]

    last_error = None

    for endpoint in candidate_endpoints:
        try:
            r = requests.get(
                f"{BASE_URL}{endpoint}",
                params={"id": container_id},
                headers=HEADERS,
                timeout=30,
            )

            if 200 <= r.status_code < 300:
                response = _safe_json(r)
                print("[Phantom] result object:", response)
                return response

            last_error = f"{endpoint} returned {r.status_code}: {r.text}"
        except Exception as e:
            last_error = f"{endpoint} failed: {e}"

    print("[Phantom] fetch-result-object warning:", last_error)
    return None


# --------------------------------------------------
# Container output
# --------------------------------------------------

def fetch_container_output(container_id):
    r = requests.get(
        f"{BASE_URL}/containers/fetch-output",
        params={"id": container_id},
        headers=HEADERS,
        timeout=30,
    )
    r.raise_for_status()
    response = _safe_json(r)
    print("[Phantom] container output:", response)
    return response


# --------------------------------------------------
# Parsing helpers
# --------------------------------------------------

def _parse_as_json_or_table(content_text: str) -> List[Dict[str, Any]]:
    if not isinstance(content_text, str):
        return []

    text = content_text.strip()
    if not text:
        return []

    # 1. Try JSON
    try:
        parsed = json.loads(text)

        if isinstance(parsed, list):
            return [row for row in parsed if isinstance(row, dict)]

        if isinstance(parsed, dict):
            for nested_key in ["data", "results", "items", "rows"]:
                nested = parsed.get(nested_key)
                if isinstance(nested, list):
                    return [row for row in nested if isinstance(row, dict)]
    except Exception:
        pass

    # 2. Try CSV / TSV
    delimiter = "\t" if "\t" in text else ","

    try:
        rows = list(csv.DictReader(StringIO(text), delimiter=delimiter))
        return [row for row in rows if isinstance(row, dict) and any(v not in [None, ""] for v in row.values())]
    except Exception:
        return []


def _from_tabular_string_or_url(raw_value: Any) -> List[Dict[str, Any]]:
    if not isinstance(raw_value, str):
        return []

    text = raw_value.strip()
    if not text:
        return []

    if text.startswith("http://") or text.startswith("https://"):
        try:
            fetched = requests.get(text, timeout=30)
            fetched.raise_for_status()
            return _parse_as_json_or_table(fetched.text)
        except Exception as e:
            print(f"[Phantom] failed to fetch output URL: {e}")
            return []

    return _parse_as_json_or_table(text)


def _extract_rows(payload: Any) -> List[Dict[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]

    if not isinstance(payload, dict):
        return []

    # direct known list containers
    for key in ["data", "results", "items", "rows"]:
        candidate = payload.get(key)

        if isinstance(candidate, list):
            return [row for row in candidate if isinstance(row, dict)]

        if isinstance(candidate, str):
            parsed = _from_tabular_string_or_url(candidate)
            if parsed:
                return parsed

        if isinstance(candidate, dict):
            nested = _extract_rows(candidate)
            if nested:
                return nested

    # other output-bearing fields
    for key in [
        "output",
        "outputUrl",
        "resultObject",
        "result",
        "csv",
        "json",
        "fileUrl",
        "downloadUrl",
        "content",
        "text",
    ]:
        candidate = payload.get(key)

        if isinstance(candidate, list):
            return [row for row in candidate if isinstance(row, dict)]

        if isinstance(candidate, str):
            parsed = _from_tabular_string_or_url(candidate)
            if parsed:
                return parsed

        if isinstance(candidate, dict):
            nested = _extract_rows(candidate)
            if nested:
                return nested

    # last fallback: inspect nested dicts
    for _, candidate in payload.items():
        if isinstance(candidate, dict):
            nested = _extract_rows(candidate)
            if nested:
                return nested
        elif isinstance(candidate, str):
            parsed = _from_tabular_string_or_url(candidate)
            if parsed:
                return parsed

    return []


# --------------------------------------------------
# Public normalized fetch
# --------------------------------------------------

def fetch_container_results(container_id):
    """
    Prefer result object first.
    Fallback to fetch-output.
    """
    result_object_payload = fetch_container_result_object(container_id)
    rows = _extract_rows(result_object_payload) if result_object_payload else []

    if rows:
        print(f"[Phantom] rows extracted from result object: {len(rows)}")
        return rows

    output_payload = fetch_container_output(container_id)
    rows = _extract_rows(output_payload)

    print(f"[Phantom] rows extracted from output: {len(rows)}")
    return rows
