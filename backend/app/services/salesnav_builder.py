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
