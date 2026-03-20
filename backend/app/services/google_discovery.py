import os
import time
from typing import Any, Dict, List, Tuple

from apify_client import ApifyClient

DEFAULT_GOOGLE_ACTOR = "compass/crawler-google-places"
GOOGLE_LANGUAGE_ALIASES = {
    "english": "en",
    "spanish": "es",
    "french": "fr",
    "german": "de",
    "italian": "it",
    "portuguese": "pt-BR",
    "portuguese (brazil)": "pt-BR",
    "portuguese (portugal)": "pt-PT",
    "hindi": "hi",
    "arabic": "ar",
    "japanese": "ja",
    "korean": "ko",
    "chinese (simplified)": "zh-CN",
    "chinese (traditional)": "zh-TW",
}
ALLOWED_GOOGLE_LANGUAGE_CODES = {
    "en", "af", "az", "id", "ms", "bs", "ca", "cs", "da", "de", "et", "es",
    "es-419", "eu", "fil", "fr", "gl", "hr", "zu", "is", "it", "sw", "lv",
    "lt", "hu", "nl", "no", "uz", "pl", "pt-BR", "pt-PT", "ro", "sq", "sk",
    "sl", "fi", "sv", "vi", "tr", "el", "bg", "ky", "kk", "mk", "mn", "ru",
    "sr", "uk", "ka", "hy", "iw", "ur", "ar", "fa", "am", "ne", "hi", "mr",
    "bn", "pa", "gu", "ta", "te", "kn", "ml", "si", "th", "lo", "my", "km",
    "ko", "ja", "zh-CN", "zh-TW",
}
LOWERCASE_GOOGLE_LANGUAGE_CODES = {code.lower(): code for code in ALLOWED_GOOGLE_LANGUAGE_CODES}
TERMINAL_RUN_STATUSES = {"SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"}


def _to_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return default


def _to_int(value: Any, default: int) -> int:
    try:
        return int(str(value).strip())
    except Exception:
        return default


def _first_present(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def _to_string_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        normalized = value.replace("\n", ";").replace(",", ";")
        return [part.strip() for part in normalized.split(";") if part.strip()]
    return []


def _normalize_actor_id(actor_id: str) -> str:
    raw = (actor_id or DEFAULT_GOOGLE_ACTOR).strip()
    return raw.replace("~", "/")


def _normalize_google_language(value: Any) -> str:
    if value is None:
        return "en"

    raw = str(value).strip()
    if not raw:
        return "en"

    alias_match = GOOGLE_LANGUAGE_ALIASES.get(raw.lower())
    if alias_match:
        return alias_match

    if raw in ALLOWED_GOOGLE_LANGUAGE_CODES:
        return raw

    lowercase_raw = raw.lower()
    if lowercase_raw in LOWERCASE_GOOGLE_LANGUAGE_CODES:
        # Preserve canonical casing for known locale-like values (e.g. zh-CN)
        return LOWERCASE_GOOGLE_LANGUAGE_CODES[lowercase_raw]

    return "en"


def _wait_for_run_finish(client: ApifyClient, run_id: str, timeout_secs: int) -> Dict[str, Any]:
    run_client = client.run(run_id)
    deadline = time.monotonic() + max(1, timeout_secs)

    while time.monotonic() < deadline:
        latest = run_client.get() or {}

        status = str((latest or {}).get("status") or "").upper()
        if status in TERMINAL_RUN_STATUSES:
            return latest

        time.sleep(2)

    raise TimeoutError(f"Apify run {run_id} did not finish within {timeout_secs} seconds.")


def build_google_places_input(payload: Dict[str, Any]) -> Dict[str, Any]:
    search_terms = _to_string_list(payload.get("search_terms") or payload.get("searchStringsArray"))
    categories = _to_string_list(
        payload.get("categories")
        or payload.get("placeCategories")
        or payload.get("categoryFilterWords")
    )

    start_urls_raw = payload.get("startUrls") or payload.get("googleMapsUrls") or payload.get("googleMapsUrlsArray")
    start_url_strings = _to_string_list(start_urls_raw)
    start_urls = [{"url": url} for url in start_url_strings]

    scrape_all_places = _to_bool(
        payload.get("allPlacesNoSearchAction")
        if payload.get("allPlacesNoSearchAction") is not None
        else payload.get("scrapeAllPlaces"),
        False,
    )

    actor_input: Dict[str, Any] = {
        "locationQuery": str(payload.get("location") or payload.get("locationQuery") or "").strip(),
        "maxCrawledPlacesPerSearch": _to_int(_first_present(payload.get("max_places"), payload.get("maxCrawledPlacesPerSearch")), 50),
        "language": _normalize_google_language(payload.get("language")),
        "scrapePlaceDetailPage": _to_bool(payload.get("scrapePlaceDetailPage"), True),
        "includeWebResults": _to_bool(payload.get("includeWebResults"), True),
        "skipClosedPlaces": _to_bool(payload.get("skipClosedPlaces"), True),
        "scrapeContacts": _to_bool(_first_present(payload.get("scrapeContacts"), payload.get("company_contacts_enrichment")), True),
        "maxLeadsPerPlace": _to_int(_first_present(payload.get("maxLeadsPerPlace"), payload.get("max_leads_per_place")), 0),
    }

    if search_terms:
        actor_input["searchStringsArray"] = search_terms
    if categories:
        actor_input["categoryFilterWords"] = categories
    if start_urls:
        actor_input["startUrls"] = start_urls
    if scrape_all_places:
        actor_input["allPlacesNoSearchAction"] = True

    raw_override = payload.get("raw_apify_input")
    if isinstance(raw_override, dict):
        actor_input.update(raw_override)

    has_required_search_source = any(
        [
            bool(actor_input.get("searchStringsArray")),
            bool(actor_input.get("categoryFilterWords")),
            bool(actor_input.get("startUrls")),
            bool(actor_input.get("allPlacesNoSearchAction")),
        ]
    )
    if not has_required_search_source:
        raise ValueError(
            "Google discovery input must include at least one of: searchStringsArray, "
            "categoryFilterWords, startUrls, or allPlacesNoSearchAction."
        )

    return actor_input


def run_google_places_actor(payload: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    token = os.getenv("APIFY_API_TOKEN", "").strip() or os.getenv("APIFY_TOKEN", "").strip()
    if not token:
        raise ValueError("Missing APIFY_API_TOKEN (or APIFY_TOKEN) environment variable")

    actor_id = _normalize_actor_id(os.getenv("APIFY_GOOGLE_PLACES_ACTOR_ID", DEFAULT_GOOGLE_ACTOR))
    actor_input = build_google_places_input(payload)

    client = ApifyClient(token)
    actor_client = client.actor(actor_id)

    wait_secs = _to_int(payload.get("apifyWaitSecs"), 1800)
    run = actor_client.call(run_input=actor_input, wait_secs=wait_secs) or {}
    run_id = run.get("id")
    run_status = str(run.get("status") or "").upper()

    if run_id and run_status not in TERMINAL_RUN_STATUSES:
        run = _wait_for_run_finish(client, run_id, timeout_secs=wait_secs)
        run_status = str(run.get("status") or "").upper()

    if run_status != "SUCCEEDED":
        status_message = run.get("statusMessage") or "No status message returned."
        raise RuntimeError(f"Apify run ended with status '{run_status}': {status_message}")

    dataset_id = run.get("defaultDatasetId")
    if not dataset_id:
        raise RuntimeError("Apify run succeeded but no dataset ID was returned.")

    rows = list(client.dataset(dataset_id).iterate_items())

    return rows, {
        "actor": actor_id,
        "run_id": run.get("id"),
        "dataset_id": dataset_id,
        "endpoint": "actor.call + dataset.iterate_items",
    }
