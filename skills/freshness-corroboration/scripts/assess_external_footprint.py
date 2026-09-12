"""assess_external_footprint.py -- calibrated footprint findings (v4.0 section 5, 8.3).
Search non-detection is never proof of real-world absence. Uses the pluggable
search_provider (fallback/optional capability); degrades to insufficient_evidence,
never a confirmed absence, whenever the provider is unconfigured or fails."""
from models import skill_result, make_finding, insufficient_evidence_result
from search_provider import is_configured, search, SearchProviderError


def assess_external_footprint(artifacts, identity, deadline, limits, instrumentation=None):
    if identity.get("status") != "success" or identity.get("data", {}).get("confidence", 0) < 0.85:
        return insufficient_evidence_result(
            "freshness-corroboration",
            "External footprint not assessed: identity unresolved or below confidence threshold.",
        )

    if not is_configured():
        return insufficient_evidence_result(
            "freshness-corroboration",
            "No external search provider configured (SEARCH_API_URL unset); "
            "footprint assessment is an optional capability in this deployment.",
            metrics={"queries_attempted": 0, "queries_completed": 0, "provider_configured": False},
        )

    name = identity["data"]["canonical_name"]
    queries = [name, f"{name} reviews", f"{name} official", f"{name} contact"][: limits.MAX_FOOTPRINT_QUERIES]
    attempted, completed, matched_hits = 0, 0, []

    for q in queries:
        # MAX_EXTERNAL_FETCHES is a combined budget shared with corroborate_claims,
        # which runs concurrently in the same dependent batch (v4.0 section 6).
        if instrumentation is not None and instrumentation.external_fetches_attempted >= limits.MAX_EXTERNAL_FETCHES:
            break
        attempted += 1
        try:
            hits = search(q, max_results=5, timeout_s=limits.PER_FETCH_TIMEOUT_MS / 1000)
            if instrumentation is not None:
                instrumentation.record_external_fetch(ok=True)
            completed += 1
            matched_hits.extend(h for h in hits if identity["data"]["domain"] not in h.get("url", ""))
        except SearchProviderError:
            if instrumentation is not None:
                instrumentation.record_external_fetch(ok=False)
            break  # bounded: stop on first failure, don't retry-storm

    if completed == 0:
        return insufficient_evidence_result(
            "freshness-corroboration",
            "External search provider failed before any query completed.",
            metrics={"queries_attempted": attempted, "queries_completed": completed, "provider_configured": True},
        )

    coverage_adequate = completed == len(queries)
    severity = "medium" if (not matched_hits and coverage_adequate) else "low"
    findings = [make_finding(
        category="off_site_presence", finding_type="proactive_improvement",
        severity=severity, status="confirmed" if matched_hits or coverage_adequate else "insufficient_evidence",
        confidence=min(identity["data"]["confidence"], completed / max(1, len(queries))),
        title="Limited independent web presence found under the resolved brand identity"
        if not matched_hits else "Independent web presence found under the resolved brand identity",
        root_cause="Few identity-matched independent sources were found within tested coverage"
        if not matched_hits else "Independent sources reference the resolved brand identity",
        evidence=[{"type": "search_hit", "description": h.get("title", ""), "urls": [h.get("url", "")]}
                  for h in matched_hits[:5]],
        suggested_action={
            "summary": "Strengthen off-site presence (directories, press, social profiles)"
            if not matched_hits else "Maintain and diversify existing off-site mentions",
            "steps": ["List on relevant directories", "Pursue press or partner mentions",
                      "Keep social/sameAs profiles active"],
            "priority": "low", "effort": "medium",
            "expected_benefit": "Improves independent corroboration signals used by AI assistants",
            "verification": "Re-run footprint assessment after outreach",
        },
        provenance={"skill": "freshness-corroboration", "script": "assess_external_footprint.py",
                    "rule_id": "footprint-signal"},
    )]

    return skill_result(
        "freshness-corroboration", findings=findings,
        metrics={"queries_attempted": attempted, "queries_completed": completed,
                 "matched_hits": len(matched_hits), "provider_configured": True},
    )
