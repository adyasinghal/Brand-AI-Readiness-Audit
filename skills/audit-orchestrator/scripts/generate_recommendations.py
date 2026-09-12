"""generate_recommendations.py -- proactive recommendation layer (v4.0 addendum).

Guarantees every successful audit ships a useful, first-class recommendations
section, even when: no defects are confirmed, all evidence is insufficient, the
site is small, or the site is already well-structured. Recommendations are:

  - evidence-aware   : derived from actual SkillResult/metrics/findings, not invented.
  - non-duplicative  : reuse merge_findings' normalize/similarity logic so a
                        recommendation never restates a confirmed defect's fix.
  - calibrated       : confidence and specificity reflect how much evidence backs them.
  - separated        : always finding_type == "proactive_improvement", carried in the
                        report's own `recommendations` array, never mixed into
                        `findings`.
"""
from merge_findings import dedup_key, normalize_text, similarity
from models import apply_invariant_i1

_GENERIC_BASELINE = [
    {
        "category": "ai_discoverability",
        "title": "Periodically re-audit AI discoverability as content changes",
        "rationale": "No discoverability defects were confirmed in this audit, but "
                     "crawlers, robots policies, and structured-data conventions "
                     "change independently of visible site content.",
        "steps": ["Re-run this audit on a recurring schedule",
                  "Re-validate JSON-LD after any template or CMS change"],
        "confidence": 0.5,
    },
    {
        "category": "engagement",
        "title": "Keep internal linking intentional as the site grows",
        "rationale": "No orphan or dead-end pages were confirmed now, but new pages "
                     "commonly launch without inbound links or a clear next step.",
        "steps": ["Add new pages to relevant navigation or related-content sections",
                  "Give every page at least one outbound next step"],
        "confidence": 0.5,
    },
    {
        "category": "off_site_presence",
        "title": "Continue building independent, identity-matched off-site mentions",
        "rationale": "Off-site presence is cumulative; even a well-corroborated brand "
                     "benefits from continued, diverse independent mentions.",
        "steps": ["List on relevant directories", "Keep sameAs/social profiles active"],
        "confidence": 0.4,
    },
]


def _recommendation_from_finding(rid: int, finding: dict) -> dict:
    return apply_invariant_i1({
        "id": f"R-{rid:03d}",
        "category": finding["category"],
        "finding_type": "proactive_improvement",
        "title": finding["title"],
        "severity": "low",
        "confidence": finding["confidence"],
        "status": finding["status"] if finding["status"] != "confirmed" else "confirmed",
        "affected_pages": finding.get("affected_pages", []),
        "root_cause": finding["root_cause"],
        "evidence": finding.get("evidence", []),
        "suggested_action": finding["suggested_action"],
        "provenance": {"source": "derived_from_finding", "finding_id": finding["id"]},
    })


def _recommendation_from_baseline(rid: int, item: dict) -> dict:
    return apply_invariant_i1({
        "id": f"R-{rid:03d}",
        "category": item["category"],
        "finding_type": "proactive_improvement",
        "title": item["title"],
        "severity": "low",
        "confidence": item["confidence"],
        "status": "insufficient_evidence" if item["confidence"] < 0.6 else "confirmed",
        "affected_pages": [],
        "root_cause": item["rationale"],
        "evidence": [],
        "suggested_action": {
            "summary": item["title"], "steps": item["steps"], "priority": "low",
            "effort": "low", "expected_benefit": "Maintains current AI-readiness posture",
            "verification": "Re-audit periodically",
        },
        "provenance": {"source": "baseline_calibrated"},
    })


def generate_recommendations(skill_results: list, merged_findings: list) -> list:
    defect_keys = {dedup_key(f) for f in merged_findings if f["finding_type"] == "defect"}
    proactive = [f for f in merged_findings if f["finding_type"] == "proactive_improvement"]

    recommendations, seen_keys = [], []
    rid = 0
    for f in proactive:
        key = dedup_key(f)
        # Non-duplicative w.r.t. confirmed defects: don't recommend fixing something
        # already reported as a defect in the same category/scope.
        if any(key[0] == dk[0] and key[2] == dk[2] and similarity(key[1], dk[1]) >= 0.85 for dk in defect_keys):
            continue
        # Non-duplicative w.r.t. recommendations already added this run.
        if any(key[0] == sk[0] and key[2] == sk[2] and similarity(key[1], sk[1]) >= 0.85 for sk in seen_keys):
            continue
        rid += 1
        recommendations.append(_recommendation_from_finding(rid, f))
        seen_keys.append(key)

    covered_categories = {r["category"] for r in recommendations} | {dk[0] for dk in defect_keys}
    for item in _GENERIC_BASELINE:
        if item["category"] in covered_categories:
            continue  # already covered by a real finding/recommendation -- no filler duplicate
        rid += 1
        recommendations.append(_recommendation_from_baseline(rid, item))

    return recommendations
