import csv
import os
import sys
import re
from urllib.parse import quote

# -------------------------------------------------
# Directory Setup
# -------------------------------------------------

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
TAXONOMY_DIR = os.path.join(CURRENT_DIR, "linkedin_taxonomy")

if TAXONOMY_DIR not in sys.path:
    sys.path.append(TAXONOMY_DIR)

# -------------------------------------------------
# Load Mapping Files
# -------------------------------------------------

try:
    from regions import REGION_MAP
    from company_sizes import COMPANY_SIZE_MAP
    from revenue_ranges import REVENUE_MAP
except ImportError:
    REGION_MAP, COMPANY_SIZE_MAP, REVENUE_MAP = {}, {}, {}


def _normalize_region_map():
    return {k.strip().lower(): v for k, v in REGION_MAP.items()}


def _split_values(value):
    return [v.strip() for v in str(value or "").split(";") if v.strip()]


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


# -------------------------------------------------
# Employee Range Mapping
# -------------------------------------------------

def _employee_min_to_size_id(employee_min):

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

            if lower.isdigit() and upper.isdigit():

                if int(lower) <= count <= int(upper):
                    return size_id

    return None


def _safe_int(value):
    try:
        return int(str(value).strip())
    except Exception:
        return None


def _company_size_bounds(label):
    value = str(label or "").strip()
    if not value:
        return None

    if value in COMPANY_SIZE_MAP:
        parsed = value
    else:
        parsed = value

    if parsed.endswith("+"):
        lower_text = parsed[:-1].strip()
        if lower_text.isdigit():
            return int(lower_text), float("inf")
        return None

    if "-" in parsed:
        lower_text, upper_text = [part.strip() for part in parsed.split("-", 1)]
        if lower_text.isdigit() and upper_text.isdigit():
            return int(lower_text), int(upper_text)
        return None

    if parsed.isdigit():
        count = int(parsed)
        return count, count

    return None


def _headcount_ids_for_range(employee_min, employee_max):
    if not str(employee_min or "").strip() and not str(employee_max or "").strip():
        return []

    min_bounds = _company_size_bounds(employee_min) if employee_min else None
    max_bounds = _company_size_bounds(employee_max) if employee_max else None

    range_min = min_bounds[0] if min_bounds else _safe_int(employee_min)
    range_max = max_bounds[1] if max_bounds else _safe_int(employee_max)

    if range_min is None:
        range_min = 0
    if range_max is None:
        range_max = float("inf")

    if range_max < range_min:
        range_min, range_max = range_max, range_min

    matched_size_ids = []
    for label, size_id in COMPANY_SIZE_MAP.items():
        bounds = _company_size_bounds(label)
        if not bounds:
            continue
        bucket_min, bucket_max = bounds
        overlaps = bucket_max >= range_min and bucket_min <= range_max
        if overlaps:
            matched_size_ids.append(size_id)

    return matched_size_ids


def _parse_revenue_value(text):
    value = str(text or "").upper().replace("$", "").replace(",", "").strip()
    if not value:
        return None

    if value.endswith("M"):
        number = value[:-1]
        return float(number) * 1_000_000 if number.replace(".", "", 1).isdigit() else None

    if value.endswith("B"):
        number = value[:-1]
        return float(number) * 1_000_000_000 if number.replace(".", "", 1).isdigit() else None

    if value.isdigit():
        return float(value)

    return None


def _revenue_bounds(label):
    text = str(label or "").strip()
    if not text:
        return None

    if "+" in text:
        lower = _parse_revenue_value(text.replace("+", ""))
        if lower is None:
            return None
        return lower, float("inf")

    parts = re.split(r"\s*-\s*", text)
    if len(parts) == 2:
        lower = _parse_revenue_value(parts[0])
        upper = _parse_revenue_value(parts[1])
        if lower is None or upper is None:
            return None
        return lower, upper

    value = _parse_revenue_value(text)
    if value is None:
        return None
    return value, value


def _revenue_ids_for_range(revenue_min, revenue_max):
    if not str(revenue_min or "").strip() and not str(revenue_max or "").strip():
        return []

    min_bounds = _revenue_bounds(revenue_min) if revenue_min else None
    max_bounds = _revenue_bounds(revenue_max) if revenue_max else None

    range_min = min_bounds[0] if min_bounds else _parse_revenue_value(revenue_min)
    range_max = max_bounds[1] if max_bounds else _parse_revenue_value(revenue_max)

    if range_min is None:
        range_min = 0
    if range_max is None:
        range_max = float("inf")

    if range_max < range_min:
        range_min, range_max = range_max, range_min

    matched = []
    for label, revenue_id in REVENUE_MAP.items():
        bounds = _revenue_bounds(label)
        if not bounds:
            continue
        bucket_min, bucket_max = bounds
        overlaps = bucket_max >= range_min and bucket_min <= range_max
        if overlaps:
            matched.append(revenue_id)

    return matched


# -------------------------------------------------
# Build Sales Navigator Company Search
# -------------------------------------------------

def build_salesnav_company_search(filters):

    # FORCE COMPANY SEARCH
    base_url = "https://www.linkedin.com/sales/search/company?query="

    filter_parts = []

    # -------------------------
    # Geography
    # -------------------------

    countries = _split_values(filters.get("geo_country"))

    geo_ids = []

    for country in countries:

        gid = REGION_LOOKUP.get(country.lower())

        if gid:
            geo_ids.append(f"(id:{gid},selectionType:INCLUDED)")

    if geo_ids:

        geo_values = ",".join(geo_ids)

        filter_parts.append(f"(type:REGION,values:List({geo_values}))")

    # -------------------------
    # Industry
    # -------------------------

    industries_include = _split_values(filters.get("industry_include"))
    industries_exclude = _split_values(filters.get("industry_exclude"))
    industry_values = []

    for ind in industries_include:
        iid = INDUSTRY_LOOKUP.get(ind.lower())
        if iid:
            industry_values.append(f"(id:{iid},selectionType:INCLUDED)")

    for ind in industries_exclude:
        iid = INDUSTRY_LOOKUP.get(ind.lower())
        if iid:
            industry_values.append(f"(id:{iid},selectionType:EXCLUDED)")

    if industry_values:
        filter_parts.append(f"(type:INDUSTRY,values:List({','.join(industry_values)}))")

    # -------------------------
    # Company Size
    # -------------------------

    size_ids = _headcount_ids_for_range(filters.get("employee_min"), filters.get("employee_max"))

    if size_ids:

        size_values = ",".join(
            f"(id:{sid},selectionType:INCLUDED)" for sid in size_ids
        )

        filter_parts.append(
            f"(type:COMPANY_HEADCOUNT,values:List({size_values}))"
        )

    # -------------------------
    # Revenue
    # -------------------------

    revenue_ids = _revenue_ids_for_range(filters.get("revenue_min_usd"), filters.get("revenue_max_usd"))
    if revenue_ids:
        revenue_values = ",".join(f"(id:{rid},selectionType:INCLUDED)" for rid in revenue_ids)
        filter_parts.append(f"(type:COMPANY_REVENUE,values:List({revenue_values}))")

    # -------------------------
    # Build Query
    # -------------------------

    query_parts = []

    if filter_parts:
        query_parts.append(f"filters:List({','.join(filter_parts)})")

    keywords = _split_values(filters.get("keywords_include"))
    keywords_exclude = _split_values(filters.get("keywords_exclude"))

    if keywords:

        query_parts.append(f"keywords:{' OR '.join(keywords)}")

    if keywords_exclude:
        query_parts.append(f"excludedKeywords:{' OR '.join(keywords_exclude)}")

    if not query_parts:
        return base_url.replace("?query=", "")

    final_query = f"({','.join(query_parts)})"

    return f"{base_url}{quote(final_query)}"
