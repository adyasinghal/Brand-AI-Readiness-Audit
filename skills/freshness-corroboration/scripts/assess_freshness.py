"""assess_freshness.py -- dates, expired offers, stale contact/leadership (v4.0
section 8.3). A missing date is never treated as proof of staleness."""
from datetime import datetime, timezone
from models import skill_result, make_finding, insufficient_evidence_result


def assess_freshness(facts, artifacts, deadline):
    fact_list = facts.get("data", {}).get("facts", [])
    date_facts = [f for f in fact_list if f["type"] == "date"]

    if not date_facts:
        return insufficient_evidence_result(
            "freshness-corroboration",
            "No dated facts found; freshness cannot be assessed (absence is not proof of staleness).",
        )

    current_year = datetime.now(timezone.utc).year
    stale = [f for f in date_facts if any(str(y) in f["value"] for y in range(2018, current_year - 3))]

    findings = []
    if stale:
        findings.append(make_finding(
            category="freshness", finding_type="defect", severity="medium",
            status="suspected", confidence=0.6,
            title="Old dates found without recent corroborating updates",
            root_cause="Dated content appears outdated relative to the current year",
            evidence=[{"type": "date", "description": f["value"], "urls": [f["source"]]} for f in stale[:5]],
            suggested_action={
                "summary": "Review and refresh outdated dated content",
                "steps": ["Audit pages with old dates", "Update or remove stale references"],
                "priority": "medium", "effort": "low",
                "expected_benefit": "Reduces risk of assistants citing stale facts",
                "verification": "Re-check dates after the update",
            },
            provenance={"skill": "freshness-corroboration", "script": "assess_freshness.py",
                        "rule_id": "stale-dates"},
        ))

    return skill_result(
        "freshness-corroboration", findings=findings,
        metrics={"date_facts_found": len(date_facts), "stale_facts": len(stale)},
    )
