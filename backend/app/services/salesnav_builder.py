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
    from regions import REGION_MAP
    from company_sizes import COMPANY_SIZE_MAP
    from revenue_ranges import REVENUE_MAP
except ImportError:
    REGION_MAP, COMPANY_SIZE_MAP, REVENUE_MAP = {}, {}, {}


def _normalize_region_map():
    return {k.strip().lower(): v for k, v in REGION_MAP.items()}


def _split_values(value):
    """Split ';' separated values and strip whitespace."""
    return [v.strip() for v in str(value or "").split(";") if v.strip()]


def _employee_min_to_size_id(employee_min):
    """Map employee_min values to Sales Navigator company size IDs."""
    if not employee_min:
        return None

    value = str(employee_min).strip()

    if value in COMPANY_SIZE_MAP:
        return COMPANY_SIZE_MAP[value]

    if not value.isdigit():
        return None

    count = int(value)

    for label, size_id in COMPANY_SIZE_MAP.items():
        label = label.strip()
        if label.endswith("+"):
            lower = label[:-1]
            if lower.isdigit() and count >= int(lower):
                return size_id
        elif "-" in label:
            lower, upper = [p.strip() for p in label.split("-", 1)]
            if lower.isdigit() and upper.isdigit() and int(lower) <= count <= int(upper):
                return size_id

    return None


def load_industries():
    lookup = {}
    csv_path = os.path.join(TAXONOMY_DIR, "industries.csv")
    if os.path.exists(csv_path):
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                lookup[row["label"].strip().lower()] = row["id"]
    return lookup


INDUSTRY_LOOKUP = load_industries()
REGION_LOOKUP = _normalize_region_map()


def build_salesnav_company_search(filters):
    search_type = filters.get("search_type", "company")

    base_url = f"https://www.linkedin.com/sales/search/{search_type}?query="

    filter_parts = []

    # -------- Geography --------
    countries = _split_values(filters.get("geo_country", ""))

    geo_ids = []
    for country in countries:
        gid = REGION_LOOKUP.get(country.lower())
        if gid:
            geo_ids.append(f"(id:{gid},selectionType:INCLUDED)")

    if geo_ids:
        geo_values = ",".join(geo_ids)

        geo_key = "REGION"
        filter_parts.append(f"(type:{geo_key},values:List({geo_values}))")

    # -------- Industry --------
    industries = [i.lower() for i in _split_values(filters.get("industry_include", ""))]

    ind_ids = []
    for ind in industries:
        iid = INDUSTRY_LOOKUP.get(ind)
        if iid:
            ind_ids.append(f"(id:{iid},selectionType:INCLUDED)")

    if ind_ids:
        filter_parts.append(f"(type:INDUSTRY,values:List({','.join(ind_ids)}))")

    # -------- Company Size --------
    employee_values = _split_values(filters.get("employee_min"))
    size_ids = []
    for emp in employee_values:
        size_id = _employee_min_to_size_id(emp)
        if size_id and size_id not in size_ids:
            size_ids.append(size_id)

    if size_ids:
        size_values = ",".join(f"(id:{sid},selectionType:INCLUDED)" for sid in size_ids)
        filter_parts.append(f"(type:COMPANY_HEADCOUNT,values:List({size_values}))")

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

    keywords = _split_values(filters.get("keywords_include"))
    if keywords:
        query_parts.append(f"keywords:{' OR '.join(keywords)}")

    if not query_parts:
        return base_url.replace("?query=", "")

    final_query = f"({','.join(query_parts)})"

    return f"{base_url}{quote(final_query)}"
