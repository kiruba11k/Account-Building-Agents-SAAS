from apify_client import ApifyClient
import os

APIFY_TOKEN = os.getenv("APIFY_TOKEN")
ACTOR_ID = os.getenv("APIFY_ACTOR_ID")

client = ApifyClient(APIFY_TOKEN)


def run_actor(search_url, max_results=500):

    run = client.actor(ACTOR_ID).call(
        run_input={
            "salesNavigatorSearchUrl": search_url,
            "maxResults": max_results
        }
    )

    dataset_id = run["defaultDatasetId"]

    return list(client.dataset(dataset_id).iterate_items())
