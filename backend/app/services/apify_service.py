from apify_client import ApifyClient
import os

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
