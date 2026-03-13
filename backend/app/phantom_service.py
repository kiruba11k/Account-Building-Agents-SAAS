import os

import requests

PHANTOM_API_KEY = os.getenv("PHANTOM_API_KEY")

BASE_URL = "https://api.phantombuster.com/api/v2"

HEADERS = {
    "X-Phantombuster-Key-1": PHANTOM_API_KEY,
    "Content-Type": "application/json",
}

SEARCH_AGENT_ID = os.getenv("PHANTOM_AGENT_ID")


def _clean_runtime_options(runtime_options):
    return runtime_options if isinstance(runtime_options, dict) else {}


def _truthy(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _find_first_value_by_keys(payload, keys):
    """Depth-first lookup for first non-empty value of keys in nested payloads."""
    if isinstance(payload, dict):
        for key in keys:
            value = payload.get(key)
            if value:
                return value
        for value in payload.values():
            found = _find_first_value_by_keys(value, keys)
            if found:
                return found
    elif isinstance(payload, list):
        for item in payload:
            found = _find_first_value_by_keys(item, keys)
            if found:
                return found
    return None


def _extract_auth_from_agent_payload(agent_payload):
    """Extract auth args from /agents/fetch response when present."""
    if not isinstance(agent_payload, dict):
        return {}

    auth = {}

    identity_id = _find_first_value_by_keys(agent_payload, ("identityId", "identity_id"))
    if identity_id:
        auth["identityId"] = str(identity_id)

    identities = _find_first_value_by_keys(agent_payload, ("identities", "identityIds"))
    if isinstance(identities, list) and identities:
        auth["identities"] = identities

    session_cookie = _find_first_value_by_keys(
        agent_payload,
        ("sessionCookie", "session_cookie", "li_at", "liAt"),
    )
    if session_cookie:
        auth["sessionCookie"] = str(session_cookie)

    return auth


def _lookup_identity_from_endpoint(path):
    """Best-effort call to identity endpoints that vary by API version/workspace."""
    try:
        resp = requests.get(
            f"{BASE_URL}/{path}",
            headers=HEADERS,
            timeout=30,
        )
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        payload = resp.json()

        identity_id = _find_first_value_by_keys(payload, ("identityId", "id"))
        if identity_id:
            return str(identity_id)
    except Exception as e:
        print(f"Phantom identity lookup via /{path} failed:", e)

    return None


def _get_fallback_auth_args():
    """Try to infer usable launch auth fields from env and Phantom account data."""
    auth = {}

    env_identity_id = os.getenv("PHANTOM_IDENTITY_ID") or os.getenv("PHANTOMBUSTER_IDENTITY_ID")
    if env_identity_id:
        auth["identityId"] = env_identity_id
        return auth

    try:
        agent_response = requests.get(
            f"{BASE_URL}/agents/fetch",
            params={"id": SEARCH_AGENT_ID},
            headers=HEADERS,
            timeout=30,
        )
        agent_response.raise_for_status()
        auth.update(_extract_auth_from_agent_payload(agent_response.json()))
        if any(auth.get(k) for k in ("sessionCookie", "identityId", "identities")):
            return auth
    except Exception as e:
        print("Phantom identity lookup via /agents/fetch failed:", e)

    # Identity endpoint names differ across tenants/API versions.
    for endpoint in ("identities/fetch-all", "identity/fetch-all"):
        identity_id = _lookup_identity_from_endpoint(endpoint)
        if identity_id:
            auth["identityId"] = identity_id
            return auth

    return auth


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
    runtime_options = _clean_runtime_options(runtime_options)

    argument = {
        "searches": search_url,
        "numberOfResultsPerLaunch": runtime_options.get("numberOfResultsPerLaunch", 100),
    }

    # Keep old behavior available without forcing queries in every launch payload.
    use_queries = _truthy(runtime_options.get("use_queries"))
    if use_queries:
        queries = runtime_options.get("queries")
        if not isinstance(queries, list) or not queries:
            queries = [search_url]
        argument["queries"] = queries

    for key in ("sessionCookie", "identityId", "identities"):
        value = runtime_options.get(key)
        if value:
            argument[key] = value

    if not any(argument.get(k) for k in ("sessionCookie", "identityId", "identities")):
        fallback_auth_getter = globals().get("_get_fallback_auth_args")
        if callable(fallback_auth_getter):
            try:
                argument.update(fallback_auth_getter())
            except Exception as e:
                print("Phantom fallback auth resolution failed:", e)
        else:
            print("Phantom fallback auth resolver is unavailable; continuing without inferred auth")

    payload = {
        "id": SEARCH_AGENT_ID,
        "argument": argument,
    }

    has_auth = any(payload["argument"].get(k) for k in ("sessionCookie", "identityId", "identities"))
    if not has_auth:
        return {
            "error": "Missing Phantom auth argument. Provide sessionCookie, identityId, or identities.",
            "hint": "Set PHANTOM_IDENTITY_ID in backend env if your workspace API does not expose identities.",
            "payload": payload,
        }

    try:
        r = requests.post(
            f"{BASE_URL}/agents/launch",
            json=payload,
            headers=HEADERS,
            timeout=30,
        )
        r.raise_for_status()
        response = r.json()
    except requests.HTTPError as e:
        error_payload = {}
        try:
            error_payload = e.response.json() if e.response is not None else {}
        except Exception:
            error_payload = {"raw": e.response.text if e.response is not None else str(e)}

        response = {
            "error": "Phantom launch request failed",
            "status_code": e.response.status_code if e.response is not None else None,
            "details": error_payload,
            "payload": payload,
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
        timeout=30,
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
        timeout=30,
    )
    r.raise_for_status()

    response = r.json()

    print("Container output:", response)

    return response
