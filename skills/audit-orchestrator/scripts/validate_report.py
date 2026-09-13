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


def _validate_finding_like(items: list, warnings: list, label: str) -> list:
    kept, seen_ids = [], set()
    for f in items:
        missing = REQUIRED_FINDING_FIELDS - f.keys()
        if missing:
            warnings.append(f"Dropped {label} {f.get('id', '?')}: missing fields {missing}")
            continue
        if f["id"] in seen_ids:
            warnings.append(f"Dropped duplicate {label} id {f['id']}")
            continue
        if (f["severity"] not in VALID_SEVERITY or f["finding_type"] not in VALID_TYPE
                or f["status"] not in VALID_STATUS):
            warnings.append(f"Dropped {label} {f['id']}: invalid severity/type/status combination")
            continue
        if not _invariant_i1_ok(f):
            warnings.append(f"Dropped {label} {f['id']}: violates Invariant I-1")
            continue
        seen_ids.add(f["id"])
        kept.append(f)
    return kept


def validate_report(report: dict) -> dict:
    warnings = list(report.get("warnings") or [])

    kept_findings = _validate_finding_like(report.get("findings", []), warnings, "finding")
    kept_recommendations = _validate_finding_like(report.get("recommendations", []), warnings, "recommendation")

    for req in ("site", "audited_at", "summary", "coverage", "execution_status", "limitations", "confidence"):
        if req not in report:
            warnings.append(f"Missing required report field: {req}")

    if not kept_recommendations:
        # A successful audit must always ship a recommendations section (v4.0
        # addendum): an empty one here is a validation failure to surface, not a
        # silently acceptable report.
        warnings.append("No recommendations were generated for this audit -- "
                         "recommendations are a required, first-class section.")

    summary = {
        "total_findings": len(kept_findings),
        "critical": sum(1 for f in kept_findings if f["severity"] == "critical"),
        "high": sum(1 for f in kept_findings if f["severity"] == "high"),
        "medium": sum(1 for f in kept_findings if f["severity"] == "medium"),
        "low": sum(1 for f in kept_findings if f["severity"] == "low"),
        "proactive_improvements": sum(1 for f in kept_findings if f["finding_type"] == "proactive_improvement"),
        "insufficient_evidence_items": sum(1 for f in kept_findings if f["status"] == "insufficient_evidence"),
        "total_recommendations": len(kept_recommendations),
    }
    report = dict(report)
    report["findings"] = kept_findings
    report["recommendations"] = kept_recommendations
    report["summary"] = summary
    report["warnings"] = warnings
    return report
