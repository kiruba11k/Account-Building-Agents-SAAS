from apify_client import ApifyClient
import os

APIFY_TOKEN = os.getenv("APIFY_TOKEN")

client = ApifyClient(APIFY_TOKEN)


#  STEP 1 → SALESNAV SEARCH
def run_salesnav_search(search_url, max_results=500):

    ACTOR_ID = "curious_coder/linkedin-sales-navigator-search-scraper"

    run = client.actor(ACTOR_ID).call(
        run_input={
            "searchUrl": search_url,
            "maxResults": max_results
        }
    )

    dataset_id = run["defaultDatasetId"]
    return list(client.dataset(dataset_id).iterate_items())


#  STEP 2 → COMPANY DETAILS
def enrich_companies(linkedin_urls):

    ACTOR_ID = "apify/linkedin-company-scraper"

    run = client.actor(ACTOR_ID).call(
        run_input={
            "startUrls": [{"url": url} for url in linkedin_urls]
        }
    )

    dataset_id = run["defaultDatasetId"]
    return list(client.dataset(dataset_id).iterate_items())
