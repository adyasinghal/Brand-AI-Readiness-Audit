"""assess_external_footprint.py -- calibrated footprint findings (v4.0 section 5, 8.3).
Search non-detection is never proof of real-world absence. No outbound web access in
this sandboxed reference implementation; a real deployment plugs a search API in here,
respecting MAX_FOOTPRINT_QUERIES and MAX_EXTERNAL_FETCHES (section 6)."""
from models import insufficient_evidence_result


def assess_external_footprint(artifacts, identity, deadline, limits):
    if identity.get("status") != "success" or identity.get("data", {}).get("confidence", 0) < 0.85:
        return insufficient_evidence_result(
            "freshness-corroboration",
            "External footprint not assessed: identity unresolved or below confidence threshold.",
        )

    return insufficient_evidence_result(
        "freshness-corroboration",
        "External footprint search unavailable in this environment.",
        metrics={"queries_attempted": 0, "queries_completed": 0},
    )
