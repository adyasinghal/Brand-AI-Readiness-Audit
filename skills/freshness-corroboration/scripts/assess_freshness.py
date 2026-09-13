"""assess_freshness.py -- dates, expired offers, stale contact/leadership (v4.0
section 8.3). A missing date is never treated as proof of staleness.

Fact-category calibration: an old date means different things depending on what
it's attached to (see extract_claims.py). "Historical" facts (founding dates,
company-history mentions) are *supposed* to be old and are never flagged as stale.
The rest are flagged with a severity that matches the real-world stakes of that
category being wrong: an expired price/offer (commercial) actively misleads a
visitor or an AI assistant quoting it, so it's high severity; a stale phone number
or address (contact) breaks the ability to reach the business, so it's also high;
operational facts (hours, "last verified" style claims) are medium; editorial dates
(blog/article timestamps) and legal boilerplate (copyright years) are low -- both
are common and expected to lag.
"""
from datetime import datetime, timezone
from models import (skill_result, make_finding, insufficient_evidence_result,
                     coverage_ratio, scale_confidence, step_down_severity)

# category -> (severity, human label used in the finding title/root_cause)
_CATEGORY_CALIBRATION = {
    "commercial": ("high", "commercial (pricing/offer) facts"),
    "contact": ("high", "contact facts"),
    "operational": ("medium", "operational facts"),
    "editorial": ("low", "editorial (article/blog) dates"),
    "legal": ("low", "legal/boilerplate dates"),
}
# Historical facts (founding dates, "since 1998"-style claims) are expected to be
# old; being old is not evidence of staleness for this category, so it is excluded
# from staleness detection entirely rather than assigned a low severity.
_EXCLUDED_FROM_STALENESS = {"historical"}


def assess_freshness(facts, artifacts, deadline):
    fact_list = facts.get("data", {}).get("facts", [])
    date_facts = [f for f in fact_list if f["type"] == "date"]

    if not date_facts:
        return insufficient_evidence_result(
            "freshness-corroboration",
            "No dated facts found; freshness cannot be assessed (absence is not proof of staleness).",
        )

    current_year = datetime.now(timezone.utc).year
    stale_all = [f for f in date_facts if any(str(y) in f["value"] for y in range(2018, current_year - 3))]
    stale_assessable = [f for f in stale_all if f.get("category") not in _EXCLUDED_FROM_STALENESS]
    excluded_count = len(stale_all) - len(stale_assessable)

    by_category = {}
    for f in stale_assessable:
        by_category.setdefault(f.get("category", "operational"), []).append(f)

    # Evidence completeness: dated facts only come from pages actually crawled, so
    # a stale-facts finding only ever speaks for that slice of the site. Scale
    # confidence/severity by how much of the discovered site was analyzed, and
    # separately note when a category's finding rests on a single fact (Round-3
    # review item 1: findings from thin samples should read as less certain than
    # ones backed by several corroborating mentions).
    acq_coverage = artifacts.acquisition_metadata.get("coverage", {})
    crawl_ratio = coverage_ratio(
        acq_coverage.get("urls_analyzed", len(artifacts.pages)),
        acq_coverage.get("urls_discovered", len(artifacts.pages)),
    )

    findings = []
    for category, facts_in_category in by_category.items():
        severity, label = _CATEGORY_CALIBRATION.get(category, ("medium", f"{category} facts"))
        sample_ratio = min(crawl_ratio, coverage_ratio(len(facts_in_category), 3))
        findings.append(make_finding(
            category="freshness", finding_type="defect",
            severity=step_down_severity(severity, sample_ratio),
            status="suspected", confidence=scale_confidence(0.6, sample_ratio),
            title=f"Old dates found among {label} without recent corroborating updates",
            root_cause=f"Dated content classified as '{category}' appears outdated relative to the current year"
                       + ("" if crawl_ratio >= 0.999 else " (within the pages actually crawled; the "
                                                           "rest of the site was not analyzed)"),
            evidence=[{"type": "date", "description": f["value"], "urls": [f["source"]]}
                      for f in facts_in_category[:5]],
            suggested_action={
                "summary": f"Review and refresh outdated {label}",
                "steps": [f"Audit pages with old {label}", "Update or remove stale references"],
                "priority": severity, "effort": "low",
                "expected_benefit": "Reduces risk of assistants citing stale facts",
                "verification": "Re-check dates after the update",
            },
            provenance={"skill": "freshness-corroboration", "script": "assess_freshness.py",
                        "rule_id": f"stale-dates:{category}"},
        ))

    return skill_result(
        "freshness-corroboration", findings=findings,
        metrics={"date_facts_found": len(date_facts), "stale_facts": len(stale_assessable),
                 "stale_facts_excluded_as_historical": excluded_count,
                 "stale_facts_by_category": {k: len(v) for k, v in by_category.items()}},
    )
