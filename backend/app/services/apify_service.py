from apify_client import ApifyClient
import os
import re

import requests

APIFY_TOKEN = os.getenv("APIFY_TOKEN")
SALESNAV_ACTOR_ID = os.getenv(
    "APIFY_SALESNAV_ACTOR_ID",
    "pratikdani/sales-navigator-company-search-scraper-no-cookies",
)
COMPANY_ENRICH_ACTOR_ID = os.getenv(
    "APIFY_COMPANY_ENRICH_ACTOR_ID",
    "apify/linkedin-company-scraper",
)

client = ApifyClient(APIFY_TOKEN)
SERPAPI_API_KEY = os.getenv("SERPAPI_API_KEY")
SERPAPI_GOOGLE_AI_MODE_ENDPOINT = "https://serpapi.com/search"


#  STEP 1 → SALESNAV SEARCH
def run_salesnav_search(search_url, max_results=500):
    run = client.actor(SALESNAV_ACTOR_ID).call(
        run_input={
            "url": search_url,
            "searchUrl": search_url,
            "maxResults": max_results
        }
    )

    dataset_id = run["defaultDatasetId"]
    return list(client.dataset(dataset_id).iterate_items())


#  STEP 2 → COMPANY DETAILS
def enrich_companies(linkedin_urls):
    run = client.actor(COMPANY_ENRICH_ACTOR_ID).call(
        run_input={
            "startUrls": [{"url": url} for url in linkedin_urls]
        }
    )

    dataset_id = run["defaultDatasetId"]
    return list(client.dataset(dataset_id).iterate_items())


def _extract_employee_band(text: str):
    if not text:
        return None

    compact = " ".join(str(text).split())
    patterns = [
        r"\b\d{1,3}(?:,\d{3})?\s*(?:to|-|–)\s*\d{1,3}(?:,\d{3})?\s+employees\b",
        r"\b\d{1,3}(?:,\d{3})?\+\s+employees\b",
        r"\b\d{1,3}(?:,\d{3})?\s+employees\b",
    ]

    for pattern in patterns:
        match = re.search(pattern, compact, flags=re.IGNORECASE)
        if match:
            return match.group(0)
    return None


def _extract_revenue_indicator(text: str):
    if not text:
        return None

    compact = " ".join(str(text).split())
    match = re.search(
        r"(?:\$|USD\s?)\d[\d,.]*(?:\s?(?:million|billion|M|B))?",
        compact,
        flags=re.IGNORECASE,
    )
    return match.group(0) if match else None


def _extract_funding_indicator(text: str):
    if not text:
        return None

    compact = " ".join(str(text).split())
    match = re.search(
        r"(?:raised|funding|series\s+[A-Z]|valuation)\b[^.]{0,80}",
        compact,
        flags=re.IGNORECASE,
    )
    return match.group(0).strip(" ,;:") if match else None


def fetch_company_signals_from_serp(company_name, linkedin_url=None):
    if not SERPAPI_API_KEY:
        return {
            "serp_enrichment_status": "skipped",
            "serp_enrichment_reason": "Missing SERPAPI_API_KEY",
        }

    search_target = company_name or linkedin_url
    if not search_target:
        return {
            "serp_enrichment_status": "skipped",
            "serp_enrichment_reason": "Missing company identifier",
        }

    query = f"{search_target} company revenue funding employee count latest"
    params = {
        "engine": "google_ai_mode",
        "q": query,
        "api_key": SERPAPI_API_KEY,
    }

    try:
        response = requests.get(
            SERPAPI_GOOGLE_AI_MODE_ENDPOINT,
            params=params,
            timeout=45,
        )
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        return {
            "serp_enrichment_status": "error",
            "serp_enrichment_reason": str(exc),
            "serp_query": query,
        }

    ai_answer = payload.get("ai_overview") or payload.get("answer_box") or {}
    snippets = []

    if isinstance(ai_answer, dict):
        for key in ["snippet", "answer", "summary", "text"]:
            value = ai_answer.get(key)
            if isinstance(value, str) and value.strip():
                snippets.append(value.strip())

        for key in ["snippets", "highlights", "bullet_points"]:
            value = ai_answer.get(key)
            if isinstance(value, list):
                snippets.extend([str(item).strip() for item in value if str(item).strip()])

    context_text = " ".join(snippets)

    return {
        "serp_enrichment_status": "ok",
        "serp_query": query,
        "serp_sources": payload.get("sources") or payload.get("organic_results") or [],
        "serp_context": context_text or None,
        "latest_revenue_indicator": _extract_revenue_indicator(context_text),
        "funding_basics_indicator": _extract_funding_indicator(context_text),
        "employee_band_indicator": _extract_employee_band(context_text),
        "serp_raw": payload,
    }
