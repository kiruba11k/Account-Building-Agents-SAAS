from urllib.parse import urlparse


def extract_domain(url):

    if not url:
        return None

    parsed = urlparse(url)

    return parsed.netloc.replace("www.", "")


def calculate_confidence(company):

    score = 0

    if company.get("website"):
        score += 25

    if company.get("industry"):
        score += 15

    if company.get("employeeCountRange"):
        score += 20

    if company.get("revenue"):
        score += 20

    if company.get("location"):
        score += 20

    return score
