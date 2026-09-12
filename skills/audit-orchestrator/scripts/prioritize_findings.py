"""prioritize_findings.py -- orders findings; cannot override confirmed critical issues
(v4.0 section 8.1)."""
_SEVERITY_RANK = {"critical": 4, "high": 3, "medium": 2, "low": 1}
_STATUS_RANK = {"confirmed": 3, "suspected": 2, "analysis_failed": 1,
                "insufficient_evidence": 0, "not_applicable": 0}


def _score(finding: dict) -> tuple:
    sev = _SEVERITY_RANK.get(finding["severity"], 0)
    stat = _STATUS_RANK.get(finding["status"], 0)
    conf = finding.get("confidence", 0.0)
    pages = len(finding.get("affected_pages") or [])
    return (sev, stat, conf, pages)


def prioritize_findings(findings: list) -> list:
    # Defense-in-depth re-check: Invariant I-1 is already enforced at finding
    # creation time (make_finding / apply_invariant_i1).
    for f in findings:
        if f["status"] == "insufficient_evidence" and f["finding_type"] != "proactive_improvement":
            raise ValueError(f"Invariant I-1 violated by finding {f['id']}")
    return sorted(findings, key=_score, reverse=True)
