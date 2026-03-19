from urllib.parse import unquote

from app.services.query_splitter import split_queries
from app.services.salesnav_builder import build_salesnav_company_search


def test_form_filters_are_reflected_in_generated_salesnav_url():
    filters = {
        "geo_country": "United States;Canada",
        "industry_include": "Software Development",
        "industry_exclude": "Hospitals and Health Care",
        "employee_min": "51-200",
        "employee_max": "1001-5000",
        "revenue_min_usd": "$10M - $50M",
        "revenue_max_usd": "$500M - $1B",
        "keywords_include": "ai;ml",
        "keywords_exclude": "agency",
    }

    url = build_salesnav_company_search(filters)
    decoded = unquote(url)

    assert "https://www.linkedin.com/sales/search/company?query=" in url
    assert "(type:REGION,values:List(" in decoded
    assert "(id:103644278,selectionType:INCLUDED)" in decoded  # United States
    assert "(id:101174742,selectionType:INCLUDED)" in decoded  # Canada

    assert "(type:INDUSTRY,values:List(" in decoded
    assert "selectionType:INCLUDED" in decoded
    assert "selectionType:EXCLUDED" in decoded

    assert "(type:COMPANY_HEADCOUNT,values:List(" in decoded
    assert "(id:D,selectionType:INCLUDED)" in decoded  # 51-200
    assert "(id:G,selectionType:INCLUDED)" in decoded  # 1001-5000

    assert "(type:COMPANY_REVENUE,values:List(" in decoded
    assert "id:REVENUE_10M_50M" in decoded
    assert "id:REVENUE_500M_1B" in decoded

    assert "keywords:ai OR ml" in decoded
    assert "excludedKeywords:agency" in decoded


def test_split_queries_respects_explicit_range_filters_from_form():
    filters = {
        "employee_min": "11-50",
        "employee_max": "201-500",
        "revenue_min_usd": "$1M - $10M",
        "revenue_max_usd": "$50M - $100M",
    }

    queries = split_queries(filters)

    assert len(queries) == 1
    decoded = unquote(queries[0])
    assert "(type:COMPANY_HEADCOUNT,values:List(" in decoded
    assert "(type:COMPANY_REVENUE,values:List(" in decoded


def test_split_queries_uses_direct_salesnav_url_when_provided():
    direct_url = "https://www.linkedin.com/sales/search/company?query=(filters:List())"
    assert split_queries({"salesnav_url": direct_url}) == [direct_url]
