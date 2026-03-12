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
    base_url = "https://www.linkedin.com/sales/search/people?query="
    filter_parts = []

    # --- 1. GEOGRAPHY (REGION for people search) ---
    raw_geo = filters.get("geo_country", "")
    countries = [c.strip().lower() for c in raw_geo.split(";") if c.strip()]
    geo_ids = []
    for c in countries:
        # Check for case-insensitive matches in your regions.py
        gid = REGIONS_MAP.get(c) or next((v for k, v in REGIONS_MAP.items() if k.lower() == c), None)
        if gid:
            geo_ids.append(f"(id:{gid},selectionType:INCLUDED)")
    if geo_ids:
        filter_parts.append(f"(type:REGION,values:List({','.join(geo_ids)}))")

    # --- 2. INDUSTRY ---
    raw_ind = filters.get("industry_include", "")
    industries = [i.strip().lower() for i in raw_ind.split(";") if i.strip()]
    ind_ids = []
    for ind in industries:
        iid = INDUSTRY_LOOKUP.get(ind)
        if iid:
            ind_ids.append(f"(id:{iid},selectionType:INCLUDED)")
    if ind_ids:
        filter_parts.append(f"(type:INDUSTRY,values:List({','.join(ind_ids)}))")

    # --- 3. COMPANY SIZE (Uses Enums like 'F' for 501-1000) ---
    emp_min = str(filters.get("employee_min", ""))
    hc_id = SIZE_MAP.get(emp_min)
    if hc_id:
        filter_parts.append(f"(type:COMPANY_HEADCOUNT,values:List((id:{hc_id},selectionType:INCLUDED)))")

    # --- 4. REVENUE (Uses Enums like 'REVENUE_10M_50M') ---
    rev_min = str(filters.get("revenue_min_usd", ""))
    rid = REVENUE_MAP.get(rev_min)
    if rid:
        filter_parts.append(f"(type:COMPANY_REVENUE,values:List((id:{rid},selectionType:INCLUDED)))")

    # --- FINAL ASSEMBLY ---
    # Construct the query components
    query_components = []
    if filter_parts:
        query_components.append(f"filters:List({','.join(filter_parts)})")
    
    keywords = filters.get("keywords_include")
    if keywords:
        query_components.append(f"keywords:{keywords}")

    # Wrap the entire query in parentheses as required by LinkedIn
    final_query = f"({','.join(query_components)})"
    return f"{base_url}{quote(final_query)}"
