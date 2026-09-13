"""prioritize_findings.py -- orders findings; cannot override confirmed critical issues
(v4.0 section 8.1).

Ordering key and tie-breaking (Round-3 review item: "prioritization determinism /
tie-breaking"). v4.0 section 8.1 names several intended ordering factors --
severity, confidence, status, affected-page count, page importance, AI impact,
visitor impact, benefit breadth, effort, and one-fix-many benefit. Several of
those (page importance, AI/visitor impact) require site-specific signals this
module doesn't have access to as plain finding dicts, so they are approximated
here by the two proxies this module CAN compute deterministically from a
finding's own fields:
  - `affected_pages` count, as a stand-in for benefit breadth / one-fix-many value
    (a fix that touches more pages generically helps more of the site), and
  - `effort`, as a quick-win tiebreaker within an otherwise-tied severity/status/
    confidence/breadth bucket (all else equal, cheaper fixes surface first).
The final tiebreaker is always the finding's own `id`. Because ids are assigned
in a fixed creation order (models._FINDING_COUNTER) and merge_findings keeps
merged findings in first-encountered-bucket order, this makes the full ordering
exactly reproducible across runs on the same input -- no two same-scored findings
can trade places between runs, which a bare `sorted()` on partial keys does not
guarantee once ties are frequent (e.g. many low-severity proactive
improvements).
"""
_SEVERITY_RANK = {"critical": 4, "high": 3, "medium": 2, "low": 1}
_STATUS_RANK = {"confirmed": 3, "suspected": 2, "analysis_failed": 1,
                "insufficient_evidence": 0, "not_applicable": 0}
_EFFORT_RANK = {"low": 2, "medium": 1, "high": 0}  # higher rank = cheaper = tiebreak winner


def _effort_of(finding: dict) -> str:
    return (finding.get("suggested_action") or {}).get("effort", "medium")


def _id_sort_key(finding_id) -> tuple:
    """Numeric-aware sort key for ids like 'F-001'/'R-012' so id order matches
    creation order (id 'F-002' sorts before 'F-010'), not lexicographic string
    order (which would put 'F-010' before 'F-002')."""
    fid = str(finding_id)
    digits = "".join(ch for ch in fid if ch.isdigit())
    return (fid.split("-")[0] if "-" in fid else fid, int(digits) if digits else 0)


def _score(finding: dict) -> tuple:
    sev = _SEVERITY_RANK.get(finding["severity"], 0)
    stat = _STATUS_RANK.get(finding["status"], 0)
    conf = finding.get("confidence", 0.0)
    pages = len(finding.get("affected_pages") or [])
    effort = _EFFORT_RANK.get(_effort_of(finding), 1)
    # Sorted descending overall (see prioritize_findings); id is negated-by-reverse-
    # sort-index below rather than included in reverse here, since ascending id
    # order (F-001 before F-002) should win the tiebreak either way the rest of the
    # tuple sorts, and mixing an ascending tiebreak into a single reverse=True sort
    # would invert it. It is applied as a separate, final, ascending sort pass.
    return (sev, stat, conf, pages, effort)


def prioritize_findings(findings: list) -> list:
    # Defense-in-depth re-check: Invariant I-1 is already enforced at finding
    # creation time (make_finding / apply_invariant_i1).
    for f in findings:
        if f["status"] == "insufficient_evidence" and f["finding_type"] != "proactive_improvement":
            raise ValueError(f"Invariant I-1 violated by finding {f['id']}")
    # Two-pass stable sort: first establish a deterministic baseline order by id
    # (ascending), then sort by score (descending). Python's sort is stable, so
    # findings that tie on every element of _score retain their id-ascending order
    # from the first pass -- the full ordering is therefore always exactly
    # reproducible for the same set of findings, regardless of dict/set iteration
    # order upstream (e.g. in merge_findings' bucket dict).
    by_id = sorted(findings, key=lambda f: _id_sort_key(f.get("id", "")))
    return sorted(by_id, key=_score, reverse=True)
