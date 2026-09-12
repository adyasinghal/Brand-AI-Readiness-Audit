"""extract_claims.py -- heuristic, deterministic claim extraction (v4.0 section 8.3)."""
import re
from models import intermediate_artifact

_DATE_RE = re.compile(
    r"\b(19|20)\d{2}[-/]\d{1,2}[-/]\d{1,2}\b"
    r"|\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},?\s+(19|20)\d{2}\b"
)
_PRICE_RE = re.compile(r"[$\u20ac\u00a3]\s?\d[\d,]*(\.\d{2})?")
_PHONE_RE = re.compile(r"\+?\d[\d\-\s\(\)]{7,}\d")


def extract_claims(artifacts, deadline):
    claims = []
    for page in artifacts.pages:
        text = page.visible_text
        for m in _DATE_RE.finditer(text):
            claims.append({"source": page.url, "subject": "date_mention", "predicate": "mentions_date",
                           "value": m.group(0), "type": "date", "importance": 0.5, "confidence": 0.6})
        for m in _PRICE_RE.finditer(text):
            claims.append({"source": page.url, "subject": "price_mention", "predicate": "mentions_price",
                           "value": m.group(0), "type": "price", "importance": 0.6, "confidence": 0.6})
        for m in _PHONE_RE.finditer(text):
            claims.append({"source": page.url, "subject": "contact", "predicate": "phone_number",
                           "value": m.group(0), "type": "contact", "importance": 0.7, "confidence": 0.5})
        for block in page.jsonld_blocks:
            if isinstance(block, dict):
                for key in ("name", "address", "telephone", "sameAs", "priceRange"):
                    if key in block:
                        claims.append({"source": page.url, "subject": block.get("@type", "entity"),
                                        "predicate": key, "value": block[key], "type": "structured",
                                        "importance": 0.8, "confidence": 0.9})
    return intermediate_artifact("claims", data={"claims": claims})
