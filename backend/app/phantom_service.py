import os
import re
import json
import csv
from io import StringIO
import requests


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
        (response.get("data") or {}).get("containerId") if isinstance(response.get("data"), dict) else None,
        (response.get("container") or {}).get("id") if isinstance(response.get("container"), dict) else None,
        (response.get("data") or {}).get("id") if isinstance(response.get("data"), dict) else None,
    ]

    for candidate in candidates:
        if candidate is None:
            continue

        candidate_str = str(candidate).strip()
        if re.fullmatch(r"\d+", candidate_str):
            return candidate_str

    return None


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
        response = {"error": str(e), "payload": payload}

    print("Phantom launch response:", response)
    return response


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


def _looks_like_company_row(row: dict) -> bool:
    if not isinstance(row, dict) or not row:
        return False

    keys_lower = {str(k).strip().lower() for k in row.keys() if k is not None}

    expected_signals = {
        "companyurl",
        "companyname",
        "regularcompanyurl",
        "industry",
        "employeescount",
        "employeecountrange",
        "companyid",
        "description",
        "logourl",
        "ishiring",
        "query",
        "timestamp",
        "searchaccountprofileid",
        "searchaccountprofilename",
    }

    matched = len(keys_lower.intersection(expected_signals))

    if matched >= 2:
        return True

    company_name = row.get("companyName") or row.get("companyname")
    company_url = row.get("companyUrl") or row.get("companyurl")
    regular_url = row.get("regularCompanyUrl") or row.get("regularcompanyurl")

    if company_name and (company_url or regular_url):
        return True

    return False


def _is_log_text(text: str) -> bool:
    if not text:
        return False

    lowered = text.lower()

    log_markers = [
        "(node:",
        "aws sdk for javascript",
        "maintenance mode",
        "please migrate your code",
        "[info_]",
        "process finished successfully",
        "this search has already been processed",
        "number of results to scrape",
        "warning",
    ]

    return any(marker in lowered for marker in log_markers)


def _clean_rows(rows):
    cleaned = []

    for row in rows:
        if not isinstance(row, dict):
            continue

        # drop rows that are clearly logs
        joined = " | ".join(
            f"{k}:{v}" for k, v in row.items()
            if v is not None
        )

        if _is_log_text(joined):
            continue

        if _looks_like_company_row(row):
            cleaned.append(row)

    return cleaned


def _parse_text_as_json(content_text: str):
    try:
        parsed = json.loads(content_text)
    except Exception:
        return []

    if isinstance(parsed, list):
        return _clean_rows(parsed)

    if isinstance(parsed, dict):
        for nested_key in ["data", "results", "items", "rows"]:
            nested = parsed.get(nested_key)
            if isinstance(nested, list):
                return _clean_rows(nested)

    return []


def _parse_text_as_csv(content_text: str):
    if not content_text or _is_log_text(content_text):
        return []

    delimiter = "\t" if "\t" in content_text else ","

    try:
        rows = list(csv.DictReader(StringIO(content_text), delimiter=delimiter))
        rows = [row for row in rows if isinstance(row, dict) and any(row.values())]
        return _clean_rows(rows)
    except Exception:
        return []


def _fetch_url_rows(url: str):
    try:
        fetched = requests.get(url, timeout=30)
        fetched.raise_for_status()
        text = fetched.text

        rows = _parse_text_as_json(text)
        if rows:
            return rows

        rows = _parse_text_as_csv(text)
        if rows:
            return rows

        return []
    except Exception as e:
        print("Failed to fetch Phantom output URL:", e)
        return []


def _extract_rows(payload):
    if isinstance(payload, list):
        return _clean_rows(payload)

    if not isinstance(payload, dict):
        return []

    # 1. Best case: structured list fields
    for key in ["data", "results", "items", "rows"]:
        candidate = payload.get(key)

        if isinstance(candidate, list):
            rows = _clean_rows(candidate)
            if rows:
                return rows

        if isinstance(candidate, dict):
            rows = _extract_rows(candidate)
            if rows:
                return rows

    # 2. Try URL-based outputs first
    for key in ["outputUrl", "fileUrl", "downloadUrl"]:
        candidate = payload.get(key)
        if isinstance(candidate, str) and candidate.startswith(("http://", "https://")):
            rows = _fetch_url_rows(candidate)
            if rows:
                return rows

    # 3. Try nested result objects
    for key in ["resultObject", "result", "output"]:
        candidate = payload.get(key)

        if isinstance(candidate, dict):
            rows = _extract_rows(candidate)
            if rows:
                return rows

        if isinstance(candidate, str):
            if candidate.startswith(("http://", "https://")):
                rows = _fetch_url_rows(candidate)
                if rows:
                    return rows

            rows = _parse_text_as_json(candidate)
            if rows:
                return rows

            rows = _parse_text_as_csv(candidate)
            if rows:
                return rows

    return []


def fetch_container_results(container_id):
    output = fetch_container_output(container_id)
    rows = _extract_rows(output)
    print("Filtered company rows count:", len(rows))
    print("Filtered company rows sample:", rows[:2] if rows else [])
    return rows
