"""analyze_rendering.py -- raw vs rendered content gaps (v4.0 section 8.2). Returns gap
pages only via SkillResult.metrics; never writes back into PageArtifact."""
from models import skill_result, make_finding, insufficient_evidence_result


def analyze_rendering(artifacts, deadline, limits):
    rendered_pages = [p for p in artifacts.pages if p.render_status == "rendered"]
    if not rendered_pages:
        return insufficient_evidence_result(
            "crawl-render-audit",
            "No headless rendering available in this environment; rendering-dependent "
            "checks are reported as insufficient evidence, not defects.",
            metrics={"rendered_pages": 0, "raw_rendered_gap_pages": []},
        )

    gap_pages = [p.url for p in rendered_pages if len(p.visible_text) < 200]

    findings = []
    if gap_pages:
        findings.append(make_finding(
            category="ai_discoverability", finding_type="defect", severity="high",
            status="confirmed", confidence=0.8,
            title="Content requires JavaScript rendering to appear",
            root_cause="Raw HTML lacks the content visible after rendering",
            evidence=[{"type": "render_gap", "description": "Static fetch returns near-empty content",
                       "urls": gap_pages[:10]}],
            suggested_action={
                "summary": "Server-side render or pre-render key content",
                "steps": ["Add SSR or static generation for key pages"],
                "priority": "high", "effort": "high",
                "expected_benefit": "Content becomes machine-readable without JS",
                "verification": "Confirm raw HTML contains key facts",
            },
            provenance={"skill": "crawl-render-audit", "script": "analyze_rendering.py",
                        "rule_id": "render-gap"},
        ))

    return skill_result(
        "crawl-render-audit", findings=findings,
        metrics={"rendered_pages": len(rendered_pages), "raw_rendered_gap_pages": gap_pages},
    )
