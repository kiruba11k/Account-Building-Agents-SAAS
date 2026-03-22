from apify_client import ApifyClient
import os
import re
import json

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
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
GROQ_CHAT_COMPLETIONS_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"


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


def _extract_text_blocks(payload: dict):
    snippets = []
    text_blocks = payload.get("text_blocks")
    if not isinstance(text_blocks, list):
        return snippets

    for block in text_blocks:
        if not isinstance(block, dict):
            continue
        snippet = block.get("snippet")
        if isinstance(snippet, str) and snippet.strip():
            snippets.append(snippet.strip())

        list_items = block.get("list")
        if isinstance(list_items, list):
            for item in list_items:
                if isinstance(item, dict):
                    value = item.get("snippet")
                    if isinstance(value, str) and value.strip():
                        snippets.append(value.strip())

    return snippets


def _extract_references(payload: dict):
    references = payload.get("references")
    if isinstance(references, list):
        return [ref for ref in references if isinstance(ref, dict)]

    fallback = payload.get("sources") or payload.get("organic_results") or []
    return [ref for ref in fallback if isinstance(ref, dict)]


def _normalize_text(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()


def _pick_company_reference_link(company_name: str, sources: list[dict]):
    if not sources:
        return None

    company_tokens = [token for token in _normalize_text(company_name).split() if token]
    if not company_tokens:
        return sources[0].get("link")

    best = None
    best_score = -1

    for source in sources:
        haystack = " ".join(
            [
                str(source.get("title") or ""),
                str(source.get("snippet") or ""),
                str(source.get("link") or ""),
                str(source.get("source") or ""),
            ]
        )
        normalized_haystack = _normalize_text(haystack)
        score = sum(1 for token in company_tokens if token in normalized_haystack)
        if score > best_score and source.get("link"):
            best = source.get("link")
            best_score = score

    return best or sources[0].get("link")


def _extract_with_groq(company_name: str, context_text: str, sources: list[dict]):
    if not GROQ_API_KEY or not context_text:
        return {}

    safe_sources = [
        {
            "title": source.get("title"),
            "link": source.get("link"),
            "source": source.get("source"),
            "snippet": source.get("snippet"),
        }
        for source in (sources or [])[:8]
        if isinstance(source, dict)
    ]

    prompt = {
        "company_name": company_name,
        "context": context_text,
        "sources": safe_sources,
        "instructions": {
            "employee_band_indicator": "Return employee band/range if present (e.g., '1-15 employees').",
            "latest_revenue_indicator": "Return latest revenue figure/range if present.",
            "funding_basics_indicator": "Return funding basics (bootstrapped/unfunded/raised amount/stage).",
            "company_reference_link": "Return best source URL most directly tied to the company metrics.",
            "confidence": "low|medium|high",
        },
        "output_format": "strict JSON object only",
    }

    try:
        response = requests.post(
            GROQ_CHAT_COMPLETIONS_ENDPOINT,
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": GROQ_MODEL,
                "temperature": 0,
                "response_format": {"type": "json_object"},
                "messages": [
                    {
                        "role": "system",
                        "content": "You extract structured company metrics from search summaries.",
                    },
                    {
                        "role": "user",
                        "content": json.dumps(prompt),
                    },
                ],
            },
            timeout=45,
        )
        response.raise_for_status()
        payload = response.json()
        content = (
            payload.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
            .strip()
        )
        parsed = json.loads(content) if content else {}
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


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

    snippets.extend(_extract_text_blocks(payload))
    if isinstance(payload.get("reconstructed_markdown"), str):
        snippets.append(payload.get("reconstructed_markdown").strip())

    context_text = " ".join(snippets)
    sources = _extract_references(payload)
    llm_extraction = _extract_with_groq(search_target, context_text, sources)

    revenue_indicator = llm_extraction.get("latest_revenue_indicator") or _extract_revenue_indicator(context_text)
    funding_indicator = llm_extraction.get("funding_basics_indicator") or _extract_funding_indicator(context_text)
    employee_band = llm_extraction.get("employee_band_indicator") or _extract_employee_band(context_text)
    reference_link = llm_extraction.get("company_reference_link") or _pick_company_reference_link(search_target, sources)

    return {
        "serp_enrichment_status": "ok",
        "serp_query": query,
        "serp_sources": sources,
        "serp_context": context_text or None,
        "latest_revenue_indicator": revenue_indicator,
        "funding_basics_indicator": funding_indicator,
        "employee_band_indicator": employee_band,
        "company_reference_link": reference_link,
        "llm_extraction_confidence": llm_extraction.get("confidence"),
        "llm_provider": "groq" if llm_extraction else None,
        "serp_raw": payload,
    }
