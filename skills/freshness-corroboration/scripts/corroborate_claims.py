"""corroborate_claims.py -- consumes the shared identity artifact; bounded external
checks (v4.0 section 8.3). Uses the pluggable search_provider (fallback/optional
capability). When no provider is configured, or the provider call fails for any
reason, this reports insufficient_evidence -- never a confirmed contradiction or a
confirmed corroboration built on absence (v4.0 section 5, generalized by
Invariant I-1)."""
from models import skill_result, make_finding, insufficient_evidence_result
from search_provider import is_configured, search, SearchProviderError


def corroborate_claims(facts, entity_identity, artifacts, deadline, limits, instrumentation=None):
    if entity_identity.get("status") not in ("success", "partial"):
        return insufficient_evidence_result(
            "freshness-corroboration", "Entity identity unresolved; corroboration suppressed."
        )

    if not is_configured():
        return insufficient_evidence_result(
            "freshness-corroboration",
            "No external search provider configured (SEARCH_API_URL unset); "
            "corroboration is an optional capability in this deployment.",
            metrics={"claims_checked": 0, "claims_corroborated": 0, "provider_configured": False},
        )

    fact_list = facts.get("data", {}).get("facts", [])[: limits.MAX_CLAIMS_CORROBORATED]
    name = entity_identity.get("data", {}).get("canonical_name", "")
    checked, corroborated, contradicted = 0, 0, []
    provider_failed = False

    for fact in fact_list:
        # MAX_EXTERNAL_FETCHES is a combined budget shared with assess_external_footprint,
        # which runs concurrently in the same dependent batch (v4.0 section 6).
        if instrumentation is not None and instrumentation.external_fetches_attempted >= limits.MAX_EXTERNAL_FETCHES:
            break
        checked += 1
        query = f"{name} {fact.get('value', '')}"
        try:
            results = search(query, max_results=3, timeout_s=limits.PER_FETCH_TIMEOUT_MS / 1000)
            if instrumentation is not None:
                instrumentation.record_external_fetch(ok=True)
            if results:
                corroborated += 1
        except SearchProviderError:
            if instrumentation is not None:
                instrumentation.record_external_fetch(ok=False)
            provider_failed = True
            break  # bounded: stop on first provider failure rather than retry-storming

    if provider_failed:
        return insufficient_evidence_result(
            "freshness-corroboration",
            "External search provider failed during corroboration; remaining claims "
            "are reported as insufficient evidence, not contradicted.",
            metrics={"claims_checked": checked, "claims_corroborated": corroborated, "provider_configured": True},
        )

    findings = []
    if contradicted:
        findings.append(make_finding(
            category="corroboration", finding_type="defect", severity="medium",
            status="suspected", confidence=0.6,
            title="Independent sources appear to contradict on-site claims",
            root_cause="External search results disagree with claims found on the site",
            evidence=[{"type": "corroboration", "description": c, "urls": []} for c in contradicted[:5]],
            suggested_action={
                "summary": "Review and reconcile contradicted claims",
                "steps": ["Compare on-site claim to external sources", "Update whichever is stale"],
                "priority": "medium", "effort": "medium",
                "expected_benefit": "Reduces risk of assistants surfacing conflicting facts",
                "verification": "Re-run corroboration after updating",
            },
            provenance={"skill": "freshness-corroboration", "script": "corroborate_claims.py",
                        "rule_id": "contradicted-claim"},
        ))

    return skill_result(
        "freshness-corroboration", findings=findings,
        metrics={"claims_checked": checked, "claims_corroborated": corroborated, "provider_configured": True},
    )
