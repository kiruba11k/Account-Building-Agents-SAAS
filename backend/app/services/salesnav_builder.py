import csv
import os
import sys
from urllib.parse import quote

# 1. Directory Setup
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
TAXONOMY_DIR = os.path.join(CURRENT_DIR, "linkedin_taxonomy")
if TAXONOMY_DIR not in sys.path:
    sys.path.append(TAXONOMY_DIR)

# 2. Load Mapping Files
try:
    from regions import REGIONS_MAP
    from company_sizes import SIZE_MAP
    from revenue_ranges import REVENUE_MAP
except ImportError:
    REGIONS_MAP, SIZE_MAP, REVENUE_MAP = {}, {}, {}

def load_industries():
    lookup = {}
    csv_path = os.path.join(TAXONOMY_DIR, "industries.csv")
    if os.path.exists(csv_path):
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Key fix: Map lowercase label to ID
                lookup[row["label"].strip().lower()] = row["id"]
    return lookup

INDUSTRY_LOOKUP = load_industries()

def build_salesnav_search(filters):

    search_type = filters.get("search_type", "company")

    base_url = f"https://www.linkedin.com/sales/search/{search_type}?query="

    filter_parts = []

    # -------- Geography --------

    countries = [c.strip() for c in filters.get("geo_country","").split(";") if c.strip()]

    geo_ids = []

    for c in countries:

        gid = REGIONS_MAP.get(c)

        if gid:
            geo_ids.append(f"(id:{gid},selectionType:INCLUDED)")

    if geo_ids:

        geo_key = "GEO_REGION" if search_type == "company" else "REGION"

        filter_parts.append(
            f"(type:{geo_key},values:List({','.join(geo_ids)}))"
        )

    # -------- Industry --------

    industries = [i.strip().lower() for i in filters.get("industry_include","").split(";") if i.strip()]

    ind_ids = []

    for ind in industries:

        iid = INDUSTRY_LOOKUP.get(ind)

        if iid:
            ind_ids.append(f"(id:{iid},selectionType:INCLUDED)")

    if ind_ids:

        filter_parts.append(
            f"(type:INDUSTRY,values:List({','.join(ind_ids)}))"
        )

    # -------- Company Size --------

    emp = filters.get("employee_min")

    if emp:

        size_id = SIZE_MAP.get(emp)

        if size_id:

            filter_parts.append(
                f"(type:COMPANY_HEADCOUNT,values:List((id:{size_id},selectionType:INCLUDED)))"
            )

    # -------- Revenue --------

    revenue = filters.get("revenue_min_usd")

    if revenue:

        rev_id = REVENUE_MAP.get(revenue)

        if rev_id:

            filter_parts.append(
                f"(type:COMPANY_REVENUE,values:List((id:{rev_id},selectionType:INCLUDED)))"
            )

    # -------- Build Query --------

    query_parts = []

    if filter_parts:

        query_parts.append(f"filters:List({','.join(filter_parts)})")

    keywords = filters.get("keywords_include")

    if keywords:

        query_parts.append(f"keywords:{keywords}")

    if not query_parts:

        return base_url.replace("?query=","")

    final_query = f"({','.join(query_parts)})"

    return f"{base_url}{quote(final_query)}"
