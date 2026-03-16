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


def launch_company_search(search_url: str):
    payload = {
        "id": PHANTOM_AGENT_ID,
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
        return _safe_json(r)
    except Exception as e:
        return {"error": str(e), "payload": payload}


def stop_agent():
    payload = {"id": PHANTOM_AGENT_ID}
    try:
        r = requests.post(
            f"{BASE_URL}/agents/stop",
            json=payload,
            headers=HEADERS,
            timeout=30,
        )
        if 200 <= r.status_code < 300:
            return _safe_json(r)
        return {"warning": "Unable to stop Phantom agent", "details": r.text}
    except Exception as e:
        return {"warning": "Unable to stop Phantom agent", "details": str(e)}


def get_container_status(container_id: str):
    r = requests.get(
        f"{BASE_URL}/containers/fetch",
        params={"id": container_id},
        headers=HEADERS,
        timeout=30,
    )
    r.raise_for_status()
    return _safe_json(r)


def fetch_container_result_object(container_id: str):
    try:
        r = requests.get(
            f"{BASE_URL}/containers/fetch-result-object",
            params={"id": container_id},
            headers=HEADERS,
            timeout=30,
        )
        if 200 <= r.status_code < 300:
            return _safe_json(r)
        return None
    except Exception:
        return None


def fetch_container_output(container_id: str):
    r = requests.get(
        f"{BASE_URL}/containers/fetch-output",
        params={"id": container_id},
        headers=HEADERS,
        timeout=30,
    )
    r.raise_for_status()
    return _safe_json(r)


def _parse_as_json_or_table(content_text: str) -> List[Dict[str, Any]]:
    if not isinstance(content_text, str):
        return []

    text = content_text.strip()
    if not text:
        return []

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

    delimiter = "\t" if "\t" in text else ","

    try:
        rows = list(csv.DictReader(StringIO(text), delimiter=delimiter))
        return [row for row in rows if isinstance(row, dict) and any(v not in [None, ""] for v in row.values())]
    except Exception:
        return []


def _from_string_or_url(raw_value: Any) -> List[Dict[str, Any]]:
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
        except Exception:
            return []

    return _parse_as_json_or_table(text)


def _extract_rows(payload: Any) -> List[Dict[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]

    if not isinstance(payload, dict):
        return []

    for key in ["data", "results", "items", "rows"]:
        candidate = payload.get(key)

        if isinstance(candidate, list):
            return [row for row in candidate if isinstance(row, dict)]

        if isinstance(candidate, str):
            parsed = _from_string_or_url(candidate)
            if parsed:
                return parsed

        if isinstance(candidate, dict):
            nested = _extract_rows(candidate)
            if nested:
                return nested

    for key in ["output", "outputUrl", "resultObject", "result", "csv", "json", "fileUrl", "downloadUrl", "content", "text"]:
        candidate = payload.get(key)

        if isinstance(candidate, list):
            return [row for row in candidate if isinstance(row, dict)]

        if isinstance(candidate, str):
            parsed = _from_string_or_url(candidate)
            if parsed:
                return parsed

        if isinstance(candidate, dict):
            nested = _extract_rows(candidate)
            if nested:
                return nested

    for _, value in payload.items():
        if isinstance(value, dict):
            nested = _extract_rows(value)
            if nested:
                return nested
        elif isinstance(value, str):
            parsed = _from_string_or_url(value)
            if parsed:
                return parsed

    return []


def fetch_container_results(container_id: str) -> List[Dict[str, Any]]:
    result_object = fetch_container_result_object(container_id)
    rows = _extract_rows(result_object) if result_object else []

    if rows:
        return rows

    output_payload = fetch_container_output(container_id)
    return _extract_rows(output_payload)
