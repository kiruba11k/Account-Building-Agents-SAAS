import os
import time
from typing import Any, Callable, Dict, Iterable, Optional

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
    except Exception:
        return default


def _string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value, str):
        return [line.strip() for line in value.splitlines() if line.strip()]
    return []


def _normalize_search_strings(search_terms: list[str], categories: list[str]) -> list[str]:
    # Legacy UI versions shipped with a default "restaurant" value, which would
    # keep biasing results even after users added other terms.
    normalized = search_terms or categories
    if len(normalized) > 1:
        normalized = [term for term in normalized if term.lower() not in {"restaurant", "restaurants"}]
    return normalized or ["business"]


def build_google_places_input(payload: Dict[str, Any]) -> Dict[str, Any]:
    search_terms = _string_list(payload.get("search_terms"))
    categories = _string_list(payload.get("categories"))

    actor_input: Dict[str, Any] = {
        "locationQuery": str(payload.get("location") or "").strip(),
        "searchStringsArray": _normalize_search_strings(search_terms, categories),
        "maxCrawledPlacesPerSearch": _to_int(payload.get("max_places"), 50),
        "language": str(payload.get("language") or "en"),
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

    raw_override = payload.get("raw_apify_input")
    if isinstance(raw_override, dict):
        actor_input.update(raw_override)

    return actor_input


def _extract_progress(run_info: Dict[str, Any]) -> int:
    stats = run_info.get("stats") or {}
    progress = stats.get("progress")

    if isinstance(progress, dict):
        for key in ("current", "percent", "value"):
            candidate = progress.get(key)
            if isinstance(candidate, (int, float)):
                return int(candidate)

    if isinstance(progress, (int, float)):
        return int(progress)

    return 50


def _stream_dataset_rows(client: ApifyClient, dataset_id: str) -> Iterable[Dict[str, Any]]:
    for row in client.dataset(dataset_id).iterate_items():
        if isinstance(row, dict):
            yield row


def run_google_places_actor_stream(
    payload: Dict[str, Any],
    request,
    db,
    push_update,
    on_row: Optional[Callable[[Dict[str, Any]], None]] = None,
    poll_interval_seconds: int = 3,
):
    token = os.getenv("APIFY_API_TOKEN") or os.getenv("APIFY_TOKEN")
    if not token:
        raise ValueError("Missing APIFY_API_TOKEN/APIFY_TOKEN")

    client = ApifyClient(token)

    actor_input = build_google_places_input(payload)
    actor_id = payload.get("apify_actor_id") or DEFAULT_GOOGLE_ACTOR
    actor = client.actor(actor_id)

    run = actor.start(run_input=actor_input)
    run_id = run["id"]

    seen_ids = set()
    inserted = 0

    while True:
        run_info = client.run(run_id).get()
        status = run_info.get("status")
        dataset_id = run_info.get("defaultDatasetId")

        if dataset_id:
            for row in _stream_dataset_rows(client, dataset_id):
                uid = row.get("placeId") or row.get("googleMapsUrl") or str(hash(str(row)))

                if uid in seen_ids:
                    continue

                seen_ids.add(uid)
                inserted += 1

                if callable(on_row):
                    on_row(row)
                else:
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

        progress = min(_extract_progress(run_info), 95)

        db.query(type(request)).filter_by(id=request.id).update(
            {
                "progress": progress,
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
                "progress": progress,
                "total_results": inserted,
            },
        )

        if status in TERMINAL_RUN_STATUSES:
            break

        time.sleep(max(1, poll_interval_seconds))

    return inserted
