import os
import time
from typing import Any, Dict, List, Tuple

from apify_client import ApifyClient

DEFAULT_GOOGLE_ACTOR = "compass/crawler-google-places"
TERMINAL_RUN_STATUSES = {"SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"}


def _to_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ["true", "1", "yes"]
    return default


def _to_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except:
        return default


def build_google_places_input(payload: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "locationQuery": payload.get("location", ""),
        "searchStringsArray": payload.get("search_terms", ["restaurant"]),
        "maxCrawledPlacesPerSearch": _to_int(payload.get("max_places"), 50),
        "language": payload.get("language", "en"),
        "scrapePlaceDetailPage": _to_bool(payload.get("scrapePlaceDetailPage")),
        "includeWebResults": _to_bool(payload.get("includeWebResults")),
        "skipClosedPlaces": _to_bool(payload.get("skipClosedPlaces")),
        "scrapeContacts": _to_bool(payload.get("company_contacts_enrichment")),
        "maximumLeadsEnrichmentRecords": _to_int(payload.get("max_leads_per_place"), 0),
        "scrapeReviewsPersonalData": _to_bool(payload.get("scrapeReviewsPersonalData"), True),
        "scrapeDirectories": _to_bool(payload.get("scrapeDirectories")),
        "scrapeImageAuthors": _to_bool(payload.get("scrapeImageAuthors")),
        "scrapeTableReservationProvider": _to_bool(payload.get("scrapeTableReservationProvider")),
    }


def run_google_places_actor(payload: Dict[str, Any], request_id: str, db):
    """
    Background worker:
    - Starts Apify actor
    - Polls run
    - Streams partial results into DB
    """

    token = os.getenv("APIFY_API_TOKEN")
    if not token:
        raise ValueError("Missing APIFY_API_TOKEN")

    client = ApifyClient(token)

    actor_input = build_google_places_input(payload)

    actor = client.actor(payload.get("apify_actor_id", DEFAULT_GOOGLE_ACTOR))

    #  Start run
    run = actor.start(run_input=actor_input)
    run_id = run["id"]

    db.update_request(request_id, {"status": "Running", "progress": 5})

    seen_ids = set()

    while True:
        run_info = client.run(run_id).get()
        status = run_info["status"]

        dataset_id = run_info.get("defaultDatasetId")

        #  Fetch partial results
        if dataset_id:
            items = list(client.dataset(dataset_id).iterate_items())

            new_items = []
            for item in items:
                uid = item.get("placeId") or str(hash(str(item)))
                if uid not in seen_ids:
                    seen_ids.add(uid)
                    new_items.append(item)

            if new_items:
                db.insert_results(request_id, new_items)

        #  Update progress
        progress = run_info.get("stats", {}).get("progress", 50)
        db.update_request(request_id, {
            "status": status,
            "progress": min(progress, 95)
        })

        if status in TERMINAL_RUN_STATUSES:
            break

        time.sleep(3)

    if status != "SUCCEEDED":
        db.update_request(request_id, {
            "status": "Failed",
            "progress": 100
        })
        return

    db.update_request(request_id, {
        "status": "Completed",
        "progress": 100
    })
