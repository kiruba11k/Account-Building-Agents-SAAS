import csv
import os
import sys
from functools import lru_cache
from typing import Dict, List

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
TAXONOMY_DIR = os.path.join(CURRENT_DIR, "linkedin_taxonomy")

if TAXONOMY_DIR not in sys.path:
    sys.path.append(TAXONOMY_DIR)

try:
    from company_sizes import COMPANY_SIZE_MAP
    from regions import REGION_MAP
    from revenue_ranges import REVENUE_MAP
except ImportError:
    COMPANY_SIZE_MAP = {}
    REGION_MAP = {}
    REVENUE_MAP = {}


def _load_industries() -> List[str]:
    csv_path = os.path.join(TAXONOMY_DIR, "industries.csv")
    if not os.path.exists(csv_path):
        return []

    labels: List[str] = []
    with open(csv_path, "r", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        for row in reader:
            label = (row.get("label") or "").strip()
            if label:
                labels.append(label)

    return sorted(set(labels), key=str.lower)


@lru_cache(maxsize=1)
def get_linkedin_taxonomy() -> Dict[str, List[str]]:
    countries = sorted(
        [name for name in REGION_MAP.keys() if str(name).strip().lower() != "global"],
        key=str.lower,
    )
    company_sizes = list(COMPANY_SIZE_MAP.keys())
    revenue_ranges = list(REVENUE_MAP.keys())
    industries = _load_industries()

    return {
        "countries": countries,
        "industries": industries,
        "company_sizes": company_sizes,
        "revenue_ranges": revenue_ranges,
    }
