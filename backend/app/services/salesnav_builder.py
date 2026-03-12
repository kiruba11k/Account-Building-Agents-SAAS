import csv
import os
from urllib.parse import quote

# Import your mappings
try:
    from app.data.regions import REGIONS_MAP
    from app.data.company_sizes import SIZE_MAP
    from app.data.revenue_ranges import REVENUE_MAP
except ImportError:
    # Use lowercase keys for more reliable matching
    REGIONS_MAP, SIZE_MAP, REVENUE_MAP = {}, {}, {}

def load_industries_from_csv():
    industry_lookup = {}
    current_dir = os.path.dirname(os.path.abspath(__file__))
    csv_path = os.path.join(current_dir, "industries.csv")
    
    if os.path.exists(csv_path):
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Ensure we map the label correctly to the id
                name = row["label"].strip().lower()
                industry_lookup[name] = row["id"]
    return industry_lookup

INDUSTRY_LOOKUP = load_industries_from_csv()

def split_values(value):
    if not value:
        return []
    if isinstance(value, list):
        return value
    return [v.strip() for v in str(value).split(";") if v.strip()]

def build_salesnav_company_search(filters):
    # Note: Use /search/people for Leads, /search/company for Accounts
    # Your prompt used /people, so I will stick with that structure
    base_url = "https://www.linkedin.com/sales/search/people?query="
    
    filter_parts = []

    # 1. Geography (Case-Insensitive Match)
    countries = split_values(filters.get("geo_country"))
    if countries:
        vals = []
        for c in countries:
            # Match against lowercase keys in your REGIONS_MAP
            geo_id = REGIONS_MAP.get(c.lower()) or REGIONS_MAP.get(c)
            if geo_id:
                vals.append(f"(id:{geo_id},selectionType:INCLUDED)")
        if vals:
            filter_parts.append(f"(type:REGION,values:List({','.join(vals)}))")

    # 2. Industry
    industries = split_values(filters.get("industry_include"))
    if industries:
        vals = []
        for ind in industries:
            ind_id = INDUSTRY_LOOKUP.get(ind.lower())
            if ind_id:
                vals.append(f"(id:{ind_id},selectionType:INCLUDED)")
        if vals:
            filter_parts.append(f"(type:INDUSTRY,values:List({','.join(vals)}))")

    # 3. Company Size
    emp_min = str(filters.get("employee_min", ""))
    hc_id = SIZE_MAP.get(emp_min)
    if hc_id:
        filter_parts.append(f"(type:COMPANY_HEADCOUNT,values:List((id:{hc_id},selectionType:INCLUDED)))")

    # 4. Revenue
    revenue = str(filters.get("revenue_min_usd", ""))
    rev_id = REVENUE_MAP.get(revenue)
    if rev_id:
        filter_parts.append(f"(type:COMPANY_REVENUE,values:List((id:{rev_id},selectionType:INCLUDED)))")

    # ----------------------------------
    # Build Query String
    # ----------------------------------
    # Keywords MUST be properly formatted and the whole query must be in parentheses
    keywords = filters.get("keywords_include", "")
    
    # Structure: (filters:List(...),keywords:AI)
    inner_query = f"filters:List({','.join(filter_parts)})"
    if keywords:
        inner_query += f",keywords:{keywords}"
    
    # Wrap in global parentheses and encode
    final_query = f"({inner_query})"
    encoded_query = quote(final_query)

    return f"{base_url}{encoded_query}"
