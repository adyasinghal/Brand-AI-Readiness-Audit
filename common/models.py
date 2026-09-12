"""Immutable shared dataclasses and schema helpers (v4.0, sections 2 and 9)."""
from __future__ import annotations
from dataclasses import dataclass
from time import monotonic
from typing import Optional


@dataclass(frozen=True)
class PageArtifact:
    """Acquisition-owned observations only. No analysis conclusions belong here (section 2)."""
    url: str
    status_code: Optional[int]
    content_type: Optional[str]
    evidence_snippet: Optional[str]
    visible_text: str
    title: Optional[str]
    meta_description: Optional[str]
    canonical_url: Optional[str]
    headings: tuple
    internal_links: tuple
    external_links: tuple
    jsonld_blocks: tuple
    page_type: Optional[str]
    fetch_duration_ms: Optional[int]
    render_status: str
    breadcrumb_visible: tuple
    breadcrumb_schema: Optional[dict]
    ai_crawler_directives: dict
    warnings: tuple = ()


@dataclass(frozen=True)
class AuditArtifacts:
    """Immutable, read-only snapshot. No specialist may mutate, append to, or replace
    fields on it (section 1 invariant)."""
    site_url: str
    normalized_origin: str
    pages: tuple
    robots_data: dict
    llms_txt_data: dict
    sitemap_data: dict
    acquisition_metadata: dict
    warnings: tuple


@dataclass(frozen=True)
class AuditDeadline:
    started_monotonic: float
    deadline_monotonic: float
    stage_deadlines: dict

    def remaining_seconds(self) -> float:
        return max(0.0, self.deadline_monotonic - monotonic())

    def expired(self) -> bool:
        return self.remaining_seconds() <= 0.0


def make_deadline(limits) -> AuditDeadline:
    now = monotonic()
    return AuditDeadline(
        started_monotonic=now,
        deadline_monotonic=now + limits.TOTAL_AUDIT_TIMEOUT_S,
        stage_deadlines={
            "acquisition": now + limits.ACQUISITION_BUDGET_S,
            "rendering": now + limits.ACQUISITION_BUDGET_S + limits.RENDERING_BUDGET_S,
            "external_analysis": now + limits.ACQUISITION_BUDGET_S
            + limits.RENDERING_BUDGET_S + limits.EXTERNAL_ANALYSIS_BUDGET_S,
        },
    )


def skill_result(skill: str, findings=None, metrics=None, warnings=None,
                  coverage=None, status="success") -> dict:
    return {
        "skill": skill,
        "status": status,
        "findings": findings or [],
        "metrics": metrics or {},
        "warnings": warnings or [],
        "coverage": coverage or {"pages_analyzed": 0, "pages_skipped": 0,
                                  "queries_attempted": 0, "queries_completed": 0},
    }


def insufficient_evidence_result(skill: str, reason: str, metrics=None) -> dict:
    return skill_result(skill, status="insufficient_evidence",
                         warnings=[reason], metrics=metrics or {})


def intermediate_artifact(artifact_type: str, data=None, status="success", warnings=None) -> dict:
    return {"artifact_type": artifact_type, "status": status,
            "data": data or {}, "warnings": warnings or []}


_FINDING_COUNTER = {"n": 0}


def apply_invariant_i1(finding: dict) -> dict:
    """Invariant I-1 (section 9): insufficient_evidence implies proactive_improvement + low."""
    if finding.get("status") == "insufficient_evidence":
        finding["finding_type"] = "proactive_improvement"
        finding["severity"] = "low"
    return finding


def make_finding(category, finding_type, severity, status, confidence, title,
                  root_cause, evidence, suggested_action, provenance,
                  affected_pages=None) -> dict:
    _FINDING_COUNTER["n"] += 1
    finding = {
        "id": f"F-{_FINDING_COUNTER['n']:03d}",
        "category": category,
        "finding_type": finding_type,
        "title": title,
        "severity": severity,
        "confidence": confidence,
        "status": status,
        "affected_pages": affected_pages or [],
        "root_cause": root_cause,
        "evidence": evidence,
        "suggested_action": suggested_action,
        "provenance": provenance,
    }
    return apply_invariant_i1(finding)
