import requests
import os

PHANTOM_API_KEY = os.getenv("PHANTOM_API_KEY")

headers = {
    "X-Phantombuster-Key-1": PHANTOM_API_KEY,
    "Content-Type": "application/json"
}

BASE_URL = "https://api.phantombuster.com/api/v2"

SEARCH_AGENT_ID = os.getenv("PHANTOM_SEARCH_AGENT_ID")
SCRAPER_AGENT_ID = os.getenv("PHANTOM_AGENT_ID")

def launch_agent(filters):
    url = f"{BASE_URL}/agents/launch"
    payload = {
        "id": PHANTOM_AGENT_ID,
        "argument": filters
    }
    response = requests.post(url, json=payload, headers=headers)
    return response.json()

def get_container_status(container_id):
    url = f"{BASE_URL}/containers/fetch"
    response = requests.get(url, headers=headers, params={"id": container_id})
    return response.json()

def fetch_container_output(container_id):
    url = f"{BASE_URL}/containers/fetch-output"
    response = requests.get(url, headers=headers, params={"id": container_id})
    return response.json()

def launch_company_search(search_url):

    payload = {
        "id": SEARCH_AGENT_ID,
        "argument": {
            "search": search_url
        }
    }

    r = requests.post(
        f"{BASE_URL}/agents/launch",
        json=payload,
        headers=headers
    )

    return r.json()


def launch_company_scraper(company_urls):

    payload = {
        "id": SCRAPER_AGENT_ID,
        "argument": {
            "linkedInCompanyPages": company_urls
        }
    }

    r = requests.post(
        f"{BASE_URL}/agents/launch",
        json=payload,
        headers=headers
    )

    return r.json()
