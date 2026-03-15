from urllib.parse import urlparse


def extract_domain(url):

    if not url:
        return None

    text = str(url).strip()

    if not text:
        return None

    parsed = urlparse(text if "://" in text else f"https://{text}")

    domain = (parsed.netloc or parsed.path or "").strip().lower()

    return domain.replace("www.", "") or None


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
