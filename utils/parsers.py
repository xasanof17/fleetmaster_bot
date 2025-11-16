import re

# MASTER REGEX (truck, driver, phone)
TRUCK_RE = re.compile(r"\b(\d{3,5})\b")
PHONE_RE = re.compile(r"(\+?\d[\d\-\s\(\)]{7,})")
DRIVER_RE = re.compile(r"(Mr\.?\s+[A-Za-z]+|Ms\.?\s+[A-Za-z]+|[A-Za-z]+(?:\s+[A-Za-z]+)?)")


def parse_title(title: str):
    """Extract unit, driver name, phone number from group title."""
    title = title.strip()

    unit = None
    driver = None
    phone = None

    # Extract truck number (3–5 digits)
    m = TRUCK_RE.search(title)
    if m:
        unit = m.group(1)

    # Extract phone number
    p = PHONE_RE.search(title)
    if p:
        phone = p.group(1).replace(" ", "").replace("(", "").replace(")", "")

    # Extract driver name
    d = DRIVER_RE.search(title)
    if d:
        driver = d.group(1)

    return {
        "unit": unit,
        "driver": driver,
        "phone": phone
    }
