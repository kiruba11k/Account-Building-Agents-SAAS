import os
import time
from typing import Any, Dict

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


def run_google_places_actor_stream(payload, request, db, push_update):
    """
    STREAMING version (fits YOUR main.py architecture)
    """

    token = os.getenv("APIFY_API_TOKEN")
    if not token:
        raise ValueError("Missing APIFY_API_TOKEN")

    client = ApifyClient(token)

    actor_input = build_google_places_input(payload)

    actor = client.actor(payload.get("apify_actor_id", DEFAULT_GOOGLE_ACTOR))

    run = actor.start(run_input=actor_input)
    run_id = run["id"]

    seen_ids = set()
    inserted = 0

    while True:
        run_info = client.run(run_id).get()
        status = run_info["status"]
        dataset_id = run_info.get("defaultDatasetId")

        # ✅ STREAM RESULTS LIVE
        if dataset_id:
            items = list(client.dataset(dataset_id).iterate_items())

            for row in items:
                uid = row.get("placeId") or str(hash(str(row)))

                if uid in seen_ids:
                    continue

                seen_ids.add(uid)
                inserted += 1

                push_update(
                    request.id,
                    {
                        "type": "company",
                        "request_id": request.id,
                        "agent_type": request.agent_type,
                        "company_name": row.get("title") or row.get("name"),
                        "company_url": row.get("website"),
                        "industry": row.get("categoryName"),
                        "total_results": inserted,
                        "raw_data": row,
                    },
                )

        # ✅ UPDATE PROGRESS
        progress = run_info.get("stats", {}).get("progress", 50)

        db.query(type(request)).filter_by(id=request.id).update(
            {
                "progress": min(progress, 95),
                "phase": "processing",
                "total_results": inserted,
            }
        )
        db.commit()

        push_update(
            request.id,
            {
                "type": "status",
                "request_id": request.id,
                "status": "Running",
                "phase": "processing",
                "progress": min(progress, 95),
                "total_results": inserted,
            },
        )

        if status in TERMINAL_RUN_STATUSES:
            break

        time.sleep(3)

    return inserted
