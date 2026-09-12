"""validate_report.py -- schema and Invariant I-1 enforcement (v4.0 section 8.1, 9)."""
REQUIRED_FINDING_FIELDS = {"id", "category", "finding_type", "title", "severity",
                            "confidence", "status", "affected_pages", "root_cause",
                            "evidence", "suggested_action", "provenance"}
VALID_SEVERITY = {"critical", "high", "medium", "low"}
VALID_TYPE = {"defect", "proactive_improvement"}
VALID_STATUS = {"confirmed", "suspected", "insufficient_evidence", "not_applicable", "analysis_failed"}


def _invariant_i1_ok(finding: dict) -> bool:
    if finding.get("status") == "insufficient_evidence":
        return finding.get("finding_type") == "proactive_improvement" and finding.get("severity") == "low"
    return True


def validate_report(report: dict) -> dict:
    warnings = list(report.get("warnings") or [])
    kept, seen_ids = [], set()

    for f in report.get("findings", []):
        missing = REQUIRED_FINDING_FIELDS - f.keys()
        if missing:
            warnings.append(f"Dropped finding {f.get('id', '?')}: missing fields {missing}")
            continue
        if f["id"] in seen_ids:
            warnings.append(f"Dropped duplicate finding id {f['id']}")
            continue
        if (f["severity"] not in VALID_SEVERITY or f["finding_type"] not in VALID_TYPE
                or f["status"] not in VALID_STATUS):
            warnings.append(f"Dropped finding {f['id']}: invalid severity/type/status combination")
            continue
        if not _invariant_i1_ok(f):
            warnings.append(f"Dropped finding {f['id']}: violates Invariant I-1")
            continue
        seen_ids.add(f["id"])
        kept.append(f)

    for req in ("site", "audited_at", "summary", "coverage"):
        if req not in report:
            warnings.append(f"Missing required report field: {req}")

    summary = {
        "total_findings": len(kept),
        "critical": sum(1 for f in kept if f["severity"] == "critical"),
        "high": sum(1 for f in kept if f["severity"] == "high"),
        "medium": sum(1 for f in kept if f["severity"] == "medium"),
        "low": sum(1 for f in kept if f["severity"] == "low"),
        "proactive_improvements": sum(1 for f in kept if f["finding_type"] == "proactive_improvement"),
        "insufficient_evidence_items": sum(1 for f in kept if f["status"] == "insufficient_evidence"),
    }
    report = dict(report)
    report["findings"] = kept
    report["summary"] = summary
    report["warnings"] = warnings
    return report
