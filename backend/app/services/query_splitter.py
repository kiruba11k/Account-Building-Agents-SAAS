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

    queries = []

    for size in SIZE_BUCKETS:
        f = filters.copy()
        f["employee_min"] = size
        queries.append(build_salesnav_company_search(f))

    return queries
