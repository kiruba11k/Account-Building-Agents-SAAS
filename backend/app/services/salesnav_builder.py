# app/services/salesnav_builder.py

from urllib.parse import quote


def _split_values(value):
    """
    Convert semicolon-separated values into list
    Example: "US;Canada" -> ["US","Canada"]
    """
    if not value:
        return []
    return [v.strip() for v in value.split(";") if v.strip()]


def build_salesnav_company_search(filters):
    """
    Convert dashboard filters into a Sales Navigator company search URL
    """

    base_url = "https://www.linkedin.com/sales/search/company?query="

    filter_parts = []

    # -------------------------
    # Geography
    # -------------------------

    countries = _split_values(filters.get("geo_country"))

    if countries:
        values = ",".join(
            f"(text:{country})" for country in countries
        )

        filter_parts.append(
            f"(type:GEO_REGION,values:List({values}))"
        )

    # -------------------------
    # Industry
    # -------------------------

    industries = _split_values(filters.get("industry_include"))

    if industries:
        values = ",".join(
            f"(text:{industry})" for industry in industries
        )

        filter_parts.append(
            f"(type:INDUSTRY,values:List({values}))"
        )

    # -------------------------
    # Company Size
    # -------------------------

    if filters.get("employee_min"):

        size = filters["employee_min"]

        filter_parts.append(
            f"(type:COMPANY_HEADCOUNT_RANGE,values:List((text:{size}+)))"
        )

    # -------------------------
    # Keywords
    # -------------------------

    if filters.get("keywords_include"):

        keywords = filters["keywords_include"]

        filter_parts.append(
            f"(type:KEYWORD,values:List((text:{keywords})))"
        )

    # -------------------------
    # Revenue
    # -------------------------

    if filters.get("revenue_min_usd"):

        rev = filters["revenue_min_usd"]

        filter_parts.append(
            f"(type:COMPANY_REVENUE,values:List((text:{rev}+)))"
        )

    # -------------------------
    # Build Query
    # -------------------------

    if not filter_parts:
        return "https://www.linkedin.com/sales/search/company"

    query = f"(filters:List({','.join(filter_parts)}))"

    encoded_query = quote(query)

    return f"{base_url}{encoded_query}"
