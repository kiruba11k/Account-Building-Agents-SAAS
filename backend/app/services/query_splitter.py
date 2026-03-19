from app.services.salesnav_builder import build_salesnav_company_search

SIZE_BUCKETS = [
    "1-10",
    "11-50",
    "51-200",
    "201-500",
    "501-1000",
    "1001-5000"
]


def split_queries(filters):
    direct_salesnav_url = str(filters.get("salesnav_url") or "").strip()
    if direct_salesnav_url:
        return [direct_salesnav_url]

    employee_min = str(filters.get("employee_min") or "").strip()
    employee_max = str(filters.get("employee_max") or "").strip()
    revenue_min = str(filters.get("revenue_min_usd") or "").strip()
    revenue_max = str(filters.get("revenue_max_usd") or "").strip()

    if employee_min or employee_max or revenue_min or revenue_max:
        return [build_salesnav_company_search(filters)]

    queries = []

    for size in SIZE_BUCKETS:
        f = filters.copy()
        f["employee_min"] = size
        queries.append(build_salesnav_company_search(f))

    return queries
