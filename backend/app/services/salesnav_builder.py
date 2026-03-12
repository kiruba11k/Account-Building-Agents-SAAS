import csv
import os
from urllib.parse import quote

try:
    from app.data.regions import REGIONS_MAP
    from app.data.company_sizes import SIZE_MAP
    from app.data.revenue_ranges import REVENUE_MAP
except ImportError:
    REGIONS_MAP, SIZE_MAP, REVENUE_MAP = {}, {}, {}


def load_industries_from_csv():
    """
    Load LinkedIn industry IDs from industries.csv
    """

    industry_lookup = {}

    csv_path = os.path.join(os.getcwd(), "app/data/industries.csv")

    if os.path.exists(csv_path):

        with open(csv_path, mode="r", encoding="utf-8") as f:

            reader = csv.DictReader(f)

            for row in reader:

                name = row["label"].strip().lower()
                industry_lookup[name] = row["id"]

    return industry_lookup


INDUSTRY_LOOKUP = load_industries_from_csv()


def split_values(value):

    if not value:
        return []

    return [v.strip() for v in value.split(";") if v.strip()]


def build_salesnav_company_search(filters):

    base_url = "https://www.linkedin.com/sales/search/people?query="

    filter_parts = []

    # ----------------------------------
    # Geography
    # ----------------------------------

    countries = split_values(filters.get("geo_country"))

    if countries:

        vals = []

        for c in countries:

            geo_id = REGIONS_MAP.get(c)

            if geo_id:

                vals.append(
                    f"(id:{geo_id},selectionType:INCLUDED)"
                )

        if vals:

            filter_parts.append(
                f"(type:REGION,values:List({','.join(vals)}))"
            )

    # ----------------------------------
    # Industry
    # ----------------------------------

    industries = split_values(filters.get("industry_include"))

    if industries:

        vals = []

        for ind in industries:

            ind_id = INDUSTRY_LOOKUP.get(ind.lower())

            if ind_id:

                vals.append(
                    f"(id:{ind_id},selectionType:INCLUDED)"
                )

        if vals:

            filter_parts.append(
                f"(type:INDUSTRY,values:List({','.join(vals)}))"
            )

    # ----------------------------------
    # Company Size
    # ----------------------------------

    emp_min = filters.get("employee_min")

    if emp_min:

        hc_id = SIZE_MAP.get(emp_min)

        if hc_id:

            filter_parts.append(
                f"(type:COMPANY_HEADCOUNT,values:List((id:{hc_id},selectionType:INCLUDED)))"
            )

    # ----------------------------------
    # Revenue
    # ----------------------------------

    revenue = filters.get("revenue_min_usd")

    if revenue:

        rev_id = REVENUE_MAP.get(revenue)

        if rev_id:

            filter_parts.append(
                f"(type:COMPANY_REVENUE,values:List((id:{rev_id},selectionType:INCLUDED)))"
            )

    # ----------------------------------
    # Build Query
    # ----------------------------------

    query = f"(filters:List({','.join(filter_parts)}))"

    keywords = filters.get("keywords_include")

    if keywords:

        query += f",keywords:{keywords}"

    encoded_query = quote(query)

    return f"{base_url}{encoded_query}"
