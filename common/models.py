"""Immutable shared dataclasses and schema helpers (v4.0, sections 2 and 9)."""
from __future__ import annotations
import hashlib
import json
from dataclasses import dataclass
from time import monotonic
from types import MappingProxyType
from typing import Optional


def freeze_value(value):
    """Recursively wrap dicts/lists in read-only views. Second-layer defense on top
    of frozen(=True) dataclasses (section 2): a MappingProxyType raises TypeError on
    any write attempt, so accidental mutation fails loudly instead of silently
    corrupting shared state.
    """
    if isinstance(value, dict):
        return MappingProxyType({k: freeze_value(v) for k, v in value.items()})
    if isinstance(value, list):
        return tuple(freeze_value(v) for v in value)
    if isinstance(value, tuple):
        return tuple(freeze_value(v) for v in value)
    return value


def _jsonable(value):
    """Recursive, deepcopy-free conversion to JSON-safe structures. Written by hand
    (rather than dataclasses.asdict, which deepcopies every leaf and cannot deepcopy
    a MappingProxyType) so it works directly on the frozen artifacts, mutation-proof
    dict fields included."""
    from dataclasses import is_dataclass, fields
    if is_dataclass(value) and not isinstance(value, type):
        return {f.name: _jsonable(getattr(value, f.name)) for f in fields(value)}
    if isinstance(value, MappingProxyType):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    return value


def hash_artifacts(artifacts) -> str:
    """Stable content hash used by the frozen-artifact acceptance test: any change to
    artifacts between two hashes (including a nested-dict mutation that `frozen=True`
    alone would not catch) is detected."""
    payload = _jsonable(artifacts)
    blob = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


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
