import os
from typing import Any, Dict, List

import requests

APIFY_BASE = "https://api.apify.com/v2/acts/compass~crawler-google-places"


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


def build_google_places_input(payload: Dict[str, Any]) -> Dict[str, Any]:
    search_terms = payload.get("search_terms") or payload.get("searchStringsArray") or []
    if isinstance(search_terms, str):
        search_terms = [s.strip() for s in search_terms.split(";") if s.strip()]

    actor_input: Dict[str, Any] = {
        "searchStringsArray": search_terms,
        "locationQuery": str(payload.get("location") or payload.get("locationQuery") or "").strip(),
        "maxCrawledPlacesPerSearch": int(payload.get("max_places") or payload.get("maxCrawledPlacesPerSearch") or 50),
        "language": payload.get("language") or "English",
        # Good GTM defaults: scrape details + web results + closed place filtering.
        "scrapePlaceDetailPage": _to_bool(payload.get("scrapePlaceDetailPage"), True),
        "includeWebResults": _to_bool(payload.get("includeWebResults"), True),
        "skipClosedPlaces": _to_bool(payload.get("skipClosedPlaces"), True),
        # Useful for company enrichment (enabled if website exists).
        "scrapeContacts": _to_bool(payload.get("scrapeContacts") or payload.get("company_contacts_enrichment"), True),
        "maxLeadsPerPlace": int(payload.get("maxLeadsPerPlace") or payload.get("max_leads_per_place") or 0),
    }

    categories = payload.get("categories") or payload.get("placeCategories")
    if categories:
        if isinstance(categories, str):
            categories = [c.strip() for c in categories.split(";") if c.strip()]
        actor_input["placeCategories"] = categories

    raw_override = payload.get("raw_apify_input")
    if isinstance(raw_override, dict):
        actor_input.update(raw_override)

    return actor_input


def run_google_places_actor(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    token = os.getenv("APIFY_API_TOKEN", "").strip()
    if not token:
        raise ValueError("Missing APIFY_API_TOKEN environment variable")

    actor_input = build_google_places_input(payload)

    response = requests.post(
        f"{APIFY_BASE}/run-sync-get-dataset-items",
        params={"token": token},
        json=actor_input,
        timeout=300,
    )
    response.raise_for_status()

    data = response.json()
    if isinstance(data, list):
        return data

    return []
