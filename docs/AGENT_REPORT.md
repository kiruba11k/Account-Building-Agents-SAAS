# Account Building Agents SaaS — Full Agent & API Report

## 1) System Overview

This platform runs **3 background agents** and streams progress/results to the UI:

1. **SalesNav Agent** (`agent_type = salesnav`)  
2. **Google Discovery Agent** (`agent_type = google`)  
3. **Firmographic Enricher** (`agent_type = enrichment`)

Each run creates a `lead_requests` row, then writes output rows into `companies` (or in-memory stream fallback) while emitting live events over Server-Sent Events (SSE).  

---

## 2) Data Model (Canonical Output Shape)

All agents eventually map output into the `Company` SQL model fields below:

- `id`
- `request_id`
- `company_url`
- `company_name`
- `description`
- `company_id`
- `regular_company_url`
- `industry`
- `employees_count`
- `employee_count_range`
- `logo_url`
- `is_hiring`
- `query`
- `timestamp`
- `search_account_profile_id`
- `search_account_profile_name`
- `raw_data` (JSON with full source payload)

`LeadRequest` tracking fields:

- `id`
- `request_name`
- `status` (`Running`, `Completed`, `Failed`, etc.)
- `phase` (`starting`, `searching`, `processing`, `enriching`, `completed`, `failed`)
- `progress` (0–100)
- `container_id` (legacy / optional)
- `total_results`
- `agent_type` (`salesnav`, `google`, `enrichment`)
- `filters` (input payload snapshot)

---

## 3) Agent-by-Agent Deep Dive

## 3.1 SalesNav Agent

### Purpose
Find companies from LinkedIn Sales Navigator queries, enrich them with company details, and stream discovered companies live.

### Start Endpoint
`POST /api/run-salesnav`

### Input Payload (UI fields)
- `request_name`
- `salesnav_url` (optional; if provided, used directly)
- `geo_country` (semicolon-separated countries)
- `industry_include` (semicolon-separated)
- `industry_exclude` (semicolon-separated)
- `employee_min`
- `employee_max`
- `revenue_min_usd`
- `revenue_max_usd`
- `keywords_include` (semicolon-separated)
- `keywords_exclude` (semicolon-separated)
- `max_results`
- Optional metadata fields from UI defaults (e.g., `notes`, `company_status`, `source_priority`, `dedupe_key`, `output_fields_profile`)

### Internal Workflow
1. Creates request row with status `Running` and `agent_type = salesnav`.
2. Builds one or many Sales Navigator URLs:
   - Uses direct `salesnav_url` if present.
   - Else builds URL from taxonomy filters.
   - If no employee/revenue bounds are given, it auto-splits into default size buckets (`1-10`, `11-50`, ... `1001-5000`).
3. Runs parallel workers over query buckets.
4. For each bucket:
   - Calls Apify SalesNav actor to get company profile URLs.
   - Batches URLs in chunks of 25.
   - Calls Apify LinkedIn company enrichment actor.
   - Deduplicates by fingerprint (URL/domain/name).
5. Streams each discovered company as `type = company` event.
6. Finalizes request as `Completed` (if >0 rows) or `Failed`.

### External APIs Used
- **Apify Actor (Sales Navigator scrape)**
  - Actor ID env/default: `APIFY_SALESNAV_ACTOR_ID` / `pratikdani/sales-navigator-company-search-scraper-no-cookies`
- **Apify Actor (Company enrichment)**
  - Actor ID env/default: `APIFY_COMPANY_ENRICH_ACTOR_ID` / `apify/linkedin-company-scraper`

### SalesNav Streaming Company Event (example)
```json
{
  "type": "company",
  "request_id": 101,
  "id": 23,
  "query": "2",
  "company_name": "Acme Corp",
  "company_url": "https://www.linkedin.com/company/acme/",
  "industry": "Software Development",
  "employees_count": "201",
  "total_results": 23,
  "raw_data": {
    "linkedinUrl": "https://www.linkedin.com/company/acme/",
    "website": "https://acme.com"
  }
}
```

### Typical Stored Columns (SalesNav)
- High confidence/populated:
  - `company_name`, `company_url`, `industry`, `employees_count`, `raw_data`
- May be empty depending on source:
  - `description`, `logo_url`, `employee_count_range`, etc.

---

## 3.2 Google Discovery Agent

### Purpose
Run Google Places discovery via Apify, optionally scrape additional fields, enrich with SERP/Groq signals, persist + stream results.

### Start Endpoint
`POST /api/run-google-discovery`

### Input Payload (UI fields)
- `request_name`
- `search_terms` (array)
- `categories` (array)
- `location`
- `max_places`
- `language`
- `scrapePlaceDetailPage` (bool)
- `includeWebResults` (bool)
- `skipClosedPlaces` (bool)
- `company_contacts_enrichment` (bool; mapped to `scrapeContacts`)
- `max_leads_per_place` (int; mapped to `maximumLeadsEnrichmentRecords`)
- `scrapeDirectories` (bool)
- `scrapeImageAuthors` (bool)
- `scrapeReviewsPersonalData` (bool)
- `scrapeTableReservationProvider` (bool)
- `apify_actor_id` (optional override; default `compass/crawler-google-places`)
- `raw_apify_input` (optional JSON merge override)

### Internal Workflow
1. Creates request row with `agent_type = google`.
2. Builds normalized Apify input (`searchStringsArray`, location, flags, language).
3. Starts Google Places actor run (`actor.start`).
4. Polls run status and dataset incrementally.
5. Deduplicates by `placeId`/`googleMapsUrl`/website/title.
6. For each place row:
   - Calls SERP enrichment (`fetch_company_signals_from_serp`) for revenue/funding/employee-band indicators.
   - Merges place row + signals.
   - Saves into `companies` table.
   - Streams `type = company` event.
7. Marks request `Completed` at end.

### External APIs Used
- **Apify Google Places actor**
  - Token env: `APIFY_API_TOKEN` or `APIFY_TOKEN`
  - Actor default: `compass/crawler-google-places`
- **SerpAPI Google AI Mode endpoint**
  - `https://serpapi.com/search` with `engine=google_ai_mode`
  - API key env: `SERPAPI_API_KEY`
- **Groq Chat Completions API** (used by SERP helper extractor)
  - `https://api.groq.com/openai/v1/chat/completions`
  - API key env: `GROQ_API_KEY`
  - model env/default: `GROQ_MODEL` / `llama-3.3-70b-versatile`

### Google Streaming Company Event (example)
```json
{
  "type": "company",
  "request_id": 202,
  "agent_type": "google",
  "company_name": "Sunrise Dental Clinic",
  "company_url": "https://sunrisedental.example",
  "industry": "Dentist",
  "employee_band_indicator": "11-50 employees",
  "latest_revenue_indicator": "$3.2M",
  "funding_basics_indicator": "bootstrapped",
  "company_reference_link": "https://example.com/profile",
  "total_results": 44
}
```

### Typical Stored Columns (Google)
- Mapped core fields:
  - `company_name` ← `title|name`
  - `company_url` ← `website`
  - `description` ← `address`
  - `company_id` ← `placeId`
  - `regular_company_url` ← `googleMapsUrl`
  - `industry` ← `categoryName`
  - `employees_count` ← `reviewsCount`
  - `employee_count_range` ← SERP-derived `employee_band_indicator`
  - `logo_url` ← `imageUrl`
  - `raw_data` ← full merged payload
- Plus flattened export fields from `raw_data` when downloading results.

---

## 3.3 Firmographic Enricher Agent

### Purpose
Given a list of company identifiers (LinkedIn URLs, domains, names), enrich firmographic profile and stream rows.

### Start Endpoint
`POST /api/run-firmographic-enricher`

### Input Payload (UI fields)
- `request_name`
- `company_inputs` (array of company names/domains/LinkedIn URLs)

### Internal Workflow
1. Creates request row with `agent_type = enrichment`.
2. Splits inputs into:
   - `linkedin_urls` (matching LinkedIn company URL pattern)
   - `generic_identifiers` (names/domains/etc.)
3. For LinkedIn URLs:
   - Calls Apify LinkedIn company enrichment actor.
   - Calls SERP/Groq enrichment for extra signals.
   - Stores + streams each enriched company.
4. For generic identifiers:
   - Runs SERP/Groq only.
   - Stores lightweight record with signal indicators.
5. Finalizes request status.

### External APIs Used
- **Apify LinkedIn company scraper actor** (`apify/linkedin-company-scraper`)
- **SerpAPI + Groq** for signal extraction (same helper as Google pipeline)

### Enrichment Streaming Company Event (example)
```json
{
  "type": "company",
  "request_id": 303,
  "agent_type": "enrichment",
  "company_url": "https://acme.com",
  "company_name": "Acme",
  "regular_company_url": "https://www.linkedin.com/company/acme/",
  "industry": "FinTech",
  "employees_count": "500",
  "employee_count_range": "201-500 employees",
  "total_results": 12
}
```

### Enrichment Preferred UI Columns
The results UI pins this column set for enrichment:

1. `company_url`
2. `company_name`
3. `regular_company_url`
4. `industry`
5. `employees_count`
6. `employee_count_range`
7. `hiring_status`
8. `serp_sources`
9. `latest_revenue_indicator`
10. `funding_basics_indicator`

---

## 4) Platform API Endpoints (Backend)

## 4.1 Agent Launch Endpoints

### `POST /api/run-salesnav`
- **Request body:** SalesNav filter payload
- **Response:**
```json
{ "request_id": 101 }
```

### `POST /api/run-google-discovery`
- **Request body:** Google discovery payload
- **Response:**
```json
{
  "request_id": 202,
  "agent_type": "google",
  "status": "Running",
  "phase": "starting",
  "message": "Google scraper queued. Processing in background."
}
```

### `POST /api/run-firmographic-enricher`
- **Request body:** enrichment payload
- **Response:**
```json
{ "request_id": 303, "agent_type": "enrichment" }
```

### `GET /api/linkedin-taxonomy`
- **Purpose:** load dropdown options for countries, industries, company sizes, revenue ranges.

---

## 4.2 Monitoring & Results Endpoints

### `GET /api/request/{request_id}`
Returns request tracking state and original filters snapshot.

**Example response**
```json
{
  "request_id": 202,
  "request_name": "NY Dental",
  "agent_type": "google",
  "status": "Running",
  "phase": "processing",
  "progress": 62,
  "total_results": 44,
  "container_id": null,
  "filters": {
    "location": "New York, USA",
    "search_terms": ["dental clinic"]
  }
}
```

### `GET /api/results/{request_id}?page=1&limit=50`
Returns paginated rows from `companies`. If DB is empty, falls back to in-memory streamed rows.

**Example response**
```json
{
  "total": 120,
  "page": 1,
  "limit": 50,
  "results": [
    {
      "id": 1,
      "request_id": 202,
      "company_url": "https://sunrisedental.example",
      "company_name": "Sunrise Dental Clinic",
      "industry": "Dentist",
      "raw_data": { "placeId": "abc123" }
    }
  ]
}
```

### `GET /api/requests`
Returns all historical requests (all agents).

### `GET /api/download/{request_id}?format=csv|json|xlsx`
Exports full results.
- Defaults to CSV.
- Flattens `raw_data` into top-level columns for export where possible.

---

## 4.3 Streaming Endpoints

### `GET /api/stream/{request_id}`
Polling endpoint returning accumulated in-memory updates.

### `GET /api/stream/{request_id}/events`
SSE endpoint for live stream with keepalive comments.

**Event envelope format:**
```text
data: {json_payload}\n\n
```

**Event types emitted**
- `status`
- `company`
- `warning`
- `error`
- `end`

**Status event example**
```json
{
  "type": "status",
  "request_id": 202,
  "agent_type": "google",
  "status": "Running",
  "phase": "processing",
  "progress": 62,
  "total_results": 44
}
```

**End event example**
```json
{
  "type": "end",
  "request_id": 202,
  "status": "Completed",
  "phase": "completed",
  "progress": 100,
  "total_results": 120
}
```

---

## 5) Output Columns by Agent (Practical Submission Table)

## 5.1 SalesNav (expected output columns)

| Column | Meaning | Example |
|---|---|---|
| `company_name` | Company name from enrichment | `Acme Corp` |
| `company_url` | LinkedIn/company URL | `https://www.linkedin.com/company/acme/` |
| `industry` | Industry label | `Software Development` |
| `employees_count` | Employee count if available | `201` |
| `query` | Query bucket identifier | `2` |
| `raw_data` | Full source payload | `{ "website": "https://acme.com" }` |

## 5.2 Google Discovery (expected output columns)

| Column | Meaning | Example |
|---|---|---|
| `company_name` | Place/business title | `Sunrise Dental Clinic` |
| `company_url` | Website URL | `https://sunrisedental.example` |
| `description` | Usually address/category text | `22 W 48th St, New York, NY` |
| `company_id` | Place identifier | `ChI...` |
| `regular_company_url` | Google Maps URL | `https://maps.google.com/...` |
| `industry` | Category name | `Dentist` |
| `employees_count` | Reviews count surrogate | `127` |
| `employee_count_range` | SERP-derived band | `11-50 employees` |
| `logo_url` | Place image | `https://lh3.googleusercontent...` |
| `latest_revenue_indicator`* | Revenue indicator (in raw/enriched payload) | `$3.2M` |
| `funding_basics_indicator`* | Funding signal | `bootstrapped` |
| `company_reference_link`* | Best source URL | `https://example.com/about` |

\*These are typically carried via merged/stream payload and surfaced through dynamic columns/export flattening.

## 5.3 Firmographic Enricher (expected output columns)

| Column | Meaning | Example |
|---|---|---|
| `company_url` | Canonical URL/domain | `https://acme.com` |
| `company_name` | Company name | `Acme` |
| `regular_company_url` | LinkedIn URL or fallback | `https://www.linkedin.com/company/acme/` |
| `industry` | Industry | `FinTech` |
| `employees_count` | Employee count | `500` |
| `employee_count_range` | Employee band | `201-500 employees` |
| `latest_revenue_indicator`* | SERP signal | `$120M` |
| `funding_basics_indicator`* | SERP/Groq signal | `Series C raised...` |
| `serp_sources`* | Source metadata if present | `[...source links...]` |

\*Usually found in merged payload / `raw_data` and surfaced by dynamic columns/export flattening.

---

## 6) Frontend API Usage Map

- `SalesNav.jsx`
  - `GET /api/linkedin-taxonomy`
  - `POST /api/run-salesnav`
- `GoogleAgent.jsx`
  - `POST /api/run-google-discovery`
  - `GET /api/request/{id}` (active request resume check)
- `Enrichment.jsx`
  - `POST /api/run-firmographic-enricher`
  - `GET /api/request/{id}` (active request resume check)
- `Requests.jsx`
  - `GET /api/requests`
- `Results.jsx`
  - `GET /api/request/{id}`
  - `GET /api/results/{id}`
  - `GET /api/stream/{id}/events`
  - `GET /api/download/{id}`

---

## 7) Environment Variables / Integrations Checklist

- `APIFY_TOKEN` or `APIFY_API_TOKEN` (required for Apify-based agents)
- `APIFY_SALESNAV_ACTOR_ID` (optional override)
- `APIFY_COMPANY_ENRICH_ACTOR_ID` (optional override)
- `SERPAPI_API_KEY` (for SERP enrichment)
- `GROQ_API_KEY` (for LLM extraction of signals)
- `GROQ_MODEL` (optional model override)
- Legacy Phantom variables present in code (not active in current pipelines):
  - `PHANTOM_API_KEY`
  - `PHANTOM_AGENT_ID`
  - `PHANTOM_IDENTITY_ID`

---

## 8) End-to-End Example (Google Agent)

1. Client calls `POST /api/run-google-discovery`.
2. Backend returns `request_id` immediately.
3. UI subscribes to `GET /api/stream/{request_id}/events`.
4. Backend streams `status` and `company` events as Apify dataset grows.
5. UI polls `GET /api/results/{request_id}` for paginated table data.
6. User exports via `GET /api/download/{request_id}?format=csv`.

---

## 9) Submission Notes

- This document is implementation-aligned with current backend/frontend code paths.
- Dynamic output columns can vary by source payload quality (especially in `raw_data` flattening and SERP-derived indicators).
- For client submissions, include both canonical SQL columns and dynamic fields as “source-dependent columns”.
