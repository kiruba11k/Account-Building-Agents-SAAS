import os
from typing import Any, Dict, List, Tuple

from apify_client import ApifyClient

DEFAULT_GOOGLE_ACTOR = "compass/crawler-google-places"


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


def _normalize_actor_id(actor_id: str) -> str:
    raw = (actor_id or DEFAULT_GOOGLE_ACTOR).strip()
    return raw.replace("~", "/")


def build_google_places_input(payload: Dict[str, Any]) -> Dict[str, Any]:
    search_terms = payload.get("search_terms") or payload.get("searchStringsArray") or []
    if isinstance(search_terms, str):
        search_terms = [s.strip() for s in search_terms.split(";") if s.strip()]

    actor_input: Dict[str, Any] = {
        "searchStringsArray": search_terms,
        "locationQuery": str(payload.get("location") or payload.get("locationQuery") or "").strip(),
        "maxCrawledPlacesPerSearch": _to_int(payload.get("max_places") or payload.get("maxCrawledPlacesPerSearch"), 50),
        "language": payload.get("language") or "English",
        "scrapePlaceDetailPage": _to_bool(payload.get("scrapePlaceDetailPage"), True),
        "includeWebResults": _to_bool(payload.get("includeWebResults"), True),
        "skipClosedPlaces": _to_bool(payload.get("skipClosedPlaces"), True),
        "scrapeContacts": _to_bool(payload.get("scrapeContacts") or payload.get("company_contacts_enrichment"), True),
        "maxLeadsPerPlace": _to_int(payload.get("maxLeadsPerPlace") or payload.get("max_leads_per_place"), 0),
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


def run_google_places_actor(payload: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    token = os.getenv("APIFY_API_TOKEN", "").strip() or os.getenv("APIFY_TOKEN", "").strip()
    if not token:
        raise ValueError("Missing APIFY_API_TOKEN (or APIFY_TOKEN) environment variable")

    actor_id = _normalize_actor_id(os.getenv("APIFY_GOOGLE_PLACES_ACTOR_ID", DEFAULT_GOOGLE_ACTOR))
    actor_input = build_google_places_input(payload)

    client = ApifyClient(token)
    actor_client = client.actor(actor_id)

    run = actor_client.call(run_input=actor_input)
    dataset_id = run.get("defaultDatasetId")
    if not dataset_id:
        return [], {
            "actor": actor_id,
            "run_id": run.get("id"),
            "dataset_id": None,
            "endpoint": "actor.call + dataset.iterate_items",
        }

    rows = list(client.dataset(dataset_id).iterate_items())

    return rows, {
        "actor": actor_id,
        "run_id": run.get("id"),
        "dataset_id": dataset_id,
        "endpoint": "actor.call + dataset.iterate_items",
    }
