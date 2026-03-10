from urllib.parse import urlencode

def build_salesnav_company_search(filters):
    """
    Convert dashboard filters into a Sales Navigator company search URL
    """

    base_url = "https://www.linkedin.com/sales/search/company?"

    params = {}

    if filters.get("geo_country"):
        params["geoIncluded"] = filters["geo_country"]

    if filters.get("industry_include"):
        params["industryIncluded"] = filters["industry_include"]

    if filters.get("employee_min"):
        params["companySize"] = filters["employee_min"]

    if filters.get("keywords_include"):
        params["keywords"] = filters["keywords_include"]

    return base_url + urlencode(params)
    
@app.post("/api/run-salesnav")
def run_salesnav(data: dict):

    # Step 1 → build SalesNav URL
    search_url = build_salesnav_company_search(data)

    # Step 2 → launch company search phantom
    response = launch_company_search(search_url)

    container_id = response.get("containerId")

    return {
        "message": "SalesNav search started",
        "search_url": search_url,
        "container_id": container_id
    }

