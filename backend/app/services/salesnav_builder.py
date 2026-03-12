import csv
import os
import sys
from urllib.parse import quote

# 1. Path Setup (points to your backend/app/services/linkedin_taxonomy/)
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
TAXONOMY_DIR = os.path.join(CURRENT_DIR, "linkedin_taxonomy")

if TAXONOMY_DIR not in sys.path:
    sys.path.append(TAXONOMY_DIR)

# 2. Dynamic Imports with Error Handling
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
                # Normalizing key: "Software Development" -> "software development"
                lookup[row["label"].strip().lower()] = row["id"]
    return lookup

INDUSTRY_LOOKUP = load_industries()

def build_salesnav_search(filters):
    # Determine if this is a People or Company search
    is_people = "people" in filters.get("search_type", "people")
    base_url = f"https://www.linkedin.com/sales/search/{'people' if is_people else 'company'}?query="
    
    filter_parts = []

    # --- GEOGRAPHY ---
    raw_geo = filters.get("geo_country", "")
    countries = [c.strip().lower() for c in raw_geo.split(";") if c.strip()]
    geo_ids = []
    # Key change: Geography for People is REGION, for Company is GEO_REGION
    geo_key = "REGION" if is_people else "GEO_REGION"
    
    for c in countries:
        gid = REGIONS_MAP.get(c) or next((v for k, v in REGIONS_MAP.items() if k.lower() == c), None)
        if gid: geo_ids.append(f"(id:{gid},selectionType:INCLUDED)")
    if geo_ids:
        filter_parts.append(f"(type:{geo_key},values:List({','.join(geo_ids)}))")

    # --- INDUSTRY ---
    raw_ind = filters.get("industry_include", "")
    industries = [i.strip().lower() for i in raw_ind.split(";") if i.strip()]
    ind_ids = []
    for ind in industries:
        iid = INDUSTRY_LOOKUP.get(ind)
        if iid: ind_ids.append(f"(id:{iid},selectionType:INCLUDED)")
    if ind_ids:
        filter_parts.append(f"(type:INDUSTRY,values:List({','.join(ind_ids)}))")

    # --- COMPANY SIZE (HEADCOUNT) ---
    h_val = str(filters.get("employee_min", ""))
    hid = SIZE_MAP.get(h_val)
    if hid:
        filter_parts.append(f"(type:COMPANY_HEADCOUNT,values:List((id:{hid},selectionType:INCLUDED)))")

    # --- REVENUE ---
    r_val = str(filters.get("revenue_min_usd", ""))
    rid = REVENUE_MAP.get(r_val)
    if rid:
        filter_parts.append(f"(type:COMPANY_REVENUE,values:List((id:{rid},selectionType:INCLUDED)))")

    # --- FINAL ASSEMBLY ---
    # Construct the internal query parts
    query_body_parts = []
    if filter_parts:
        query_body_parts.append(f"filters:List({','.join(filter_parts)})")
    
    keywords = filters.get("keywords_include")
    if keywords:
        query_body_parts.append(f"keywords:{keywords}")

    # If everything is empty, return base URL
    if not query_body_parts:
        return base_url.replace("?query=", "")

    # Outer parentheses are MANDATORY for the query= parameter to work
    final_query = f"({','.join(query_body_parts)})"
    return f"{base_url}{quote(final_query)}"
