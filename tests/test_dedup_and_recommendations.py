"""Dedup algorithm tests (near-duplicate merge vs distinct non-merge) and the
recommendations layer's four required scenarios: no defects, all insufficient
evidence, a small site, and an already-well-structured site."""
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _rel in (
    "common", "skills/audit-orchestrator/scripts", "skills/crawl-render-audit/scripts",
    "skills/freshness-corroboration/scripts", "skills/engagement-audit/scripts",
):
    sys.path.insert(0, os.path.join(_ROOT, _rel))

from models import make_finding, skill_result
from merge_findings import merge_findings
from generate_recommendations import generate_recommendations


def _finding(category, root_cause, pages, finding_type="defect", status="confirmed", severity="medium"):
    return make_finding(
        category=category, finding_type=finding_type, severity=severity, status=status, confidence=0.8,
        title=root_cause, root_cause=root_cause, evidence=[{"type": "t", "description": "d", "urls": pages}],
        suggested_action={"summary": "s", "steps": [], "priority": "low", "effort": "low",
                           "expected_benefit": "b", "verification": "v"},
        provenance={"skill": "test", "script": "test.py", "rule_id": "r"}, affected_pages=pages,
    )


def test_near_duplicates_from_different_skills_merge():
    a = _finding("ai_discoverability", "robots.txt blocks crawler access to the site", ["https://x/"])
    b = _finding("ai_discoverability", "robots.txt is blocking crawler access on the site", ["https://x/"])
    results = [skill_result("skillA", findings=[a]), skill_result("skillB", findings=[b])]
    merged = merge_findings(results)
    assert len(merged) == 1
    assert len(merged[0]["provenance"]["contributing_skills"]) == 2


def test_distinct_findings_same_category_and_scope_do_not_merge():
    a = _finding("ai_discoverability", "robots.txt blocks crawler access", ["https://x/"])
    b = _finding("ai_discoverability", "page returns a 500 server error", ["https://x/"])
    results = [skill_result("skillA", findings=[a, b])]
    merged = merge_findings(results)
    assert len(merged) == 2


def test_merge_findings_rejects_intermediate_artifact_input():
    try:
        merge_findings([{"artifact_type": "claims", "status": "success", "data": {}, "warnings": []}])
        assert False, "should have raised"
    except ValueError:
        pass


def test_recommendations_present_when_no_defects_confirmed():
    results = [skill_result("s", findings=[])]
    recs = generate_recommendations(results, [])
    assert len(recs) > 0
    assert all(r["finding_type"] == "proactive_improvement" for r in recs)


def test_recommendations_present_when_all_evidence_insufficient():
    insufficient = _finding("freshness", "no dated facts found", [], finding_type="proactive_improvement",
                             status="insufficient_evidence", severity="low")
    results = [skill_result("s", findings=[insufficient])]
    recs = generate_recommendations(results, [insufficient])
    assert len(recs) > 0
    # The insufficient-evidence finding itself should surface as a recommendation, not be lost.
    assert any(r["provenance"].get("finding_id") == insufficient["id"] for r in recs)


def test_recommendations_present_for_small_well_structured_site():
    # No findings at all -- fully clean audit -- must still produce calibrated baseline recs.
    recs = generate_recommendations([], [])
    assert len(recs) >= 1
    assert {r["category"] for r in recs}.issubset({"ai_discoverability", "engagement", "off_site_presence"})


def test_recommendations_do_not_duplicate_confirmed_defects():
    same_cause = "no structured data json ld found on any crawled page"
    defect = _finding("ai_discoverability", same_cause, ["https://x/"])
    proactive = _finding("ai_discoverability", same_cause,
                          ["https://x/"], finding_type="proactive_improvement", status="confirmed", severity="low")
    results = [skill_result("s", findings=[defect, proactive])]
    merged = [defect, proactive]
    recs = generate_recommendations(results, merged)
    # The proactive near-duplicate of the confirmed defect must be suppressed as a recommendation.
    assert not any(r["provenance"].get("finding_id") == proactive["id"] for r in recs)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"OK: {name}")
