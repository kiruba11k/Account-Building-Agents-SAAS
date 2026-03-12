import csv
import os
import sys
from urllib.parse import quote

# 1. Setup the Path to your taxonomy folder
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
TAXONOMY_DIR = os.path.join(CURRENT_DIR, "linkedin_taxonomy")

# Add TAXONOMY_DIR to sys.path so we can import .py files from it
if TAXONOMY_DIR not in sys.path:
    sys.path.append(TAXONOMY_DIR)

# 2. Import the dictionaries from your .py files
try:
    from regions import REGIONS_MAP
    from company_sizes import SIZE_MAP
    from revenue_ranges import REVENUE_MAP
except ImportError:
    print("Warning: Could not find mapping files in linkedin_taxonomy folder.")
    REGIONS_MAP, SIZE_MAP, REVENUE_MAP = {}, {}, {}

def load_industries_from_csv():
    """Loads industry IDs from industries.csv inside the taxonomy folder"""
    industry_lookup = {}
    csv_path = os.path.join(TAXONOMY_DIR, "industries.csv")
    
    if os.path.exists(csv_path):
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Normalizing key to lowercase for easier matching
                name = row["label"].strip().lower()
                industry_lookup[name] = row["id"]
    return industry_lookup

INDUSTRY_LOOKUP = load_industries_from_csv()

def build_salesnav_company_search(filters):
    base_url = "https://www.linkedin.com/sales/search/people?query="
    filter_parts = []

    # Geography Mapping
    countries = [c.strip().lower() for c in filters.get("geo_country", "").split(";") if c.strip()]
    geo_vals = []
    for c in countries:
        # Check if the country name exists in your regions.py dictionary
        geo_id = REGIONS_MAP.get(c) 
        if geo_id:
            geo_vals.append(f"(id:{geo_id},selectionType:INCLUDED)")
    if geo_vals:
        filter_parts.append(f"(type:REGION,values:List({','.join(geo_vals)}))")

    # Industry Mapping
    industries = [i.strip().lower() for i in filters.get("industry_include", "").split(";") if i.strip()]
    ind_vals = []
    for ind in industries:
        ind_id = INDUSTRY_LOOKUP.get(ind)
        if ind_id:
            ind_vals.append(f"(id:{ind_id},selectionType:INCLUDED)")
    if ind_vals:
        filter_parts.append(f"(type:INDUSTRY,values:List({','.join(ind_vals)}))")

    # Headcount (Size)
    emp_min = str(filters.get("employee_min", ""))
    hc_id = SIZE_MAP.get(emp_min)
    if hc_id:
        filter_parts.append(f"(type:COMPANY_HEADCOUNT,values:List((id:{hc_id},selectionType:INCLUDED)))")

    # Revenue
    revenue = str(filters.get("revenue_min_usd", ""))
    rev_id = REVENUE_MAP.get(revenue)
    if rev_id:
        filter_parts.append(f"(type:COMPANY_REVENUE,values:List((id:{rev_id},selectionType:INCLUDED)))")

    # Keyword and Final Construction
    inner_query = f"filters:List({','.join(filter_parts)})"
    keywords = filters.get("keywords_include")
    if keywords:
        inner_query += f",keywords:{keywords}"

    # Return encoded URL
    return f"{base_url}{quote('(' + inner_query + ')')}"
