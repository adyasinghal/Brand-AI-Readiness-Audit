"""analyze_engagement.py -- navigation, orphans, dead ends, breadcrumb cross-check
(v4.0 section 8.4). Consumes artifacts, site_graph, and rendering_result; runs in the
dependent batch so it overlaps external-analysis work; never writes to either input."""
from models import skill_result, make_finding


def analyze_engagement(artifacts, site_graph, rendering_result, deadline):
    findings = []
    graph = site_graph.get("data", {})
    orphans = graph.get("orphans", [])
    dead_ends = graph.get("dead_ends", [])

    if orphans:
        findings.append(make_finding(
            category="engagement", finding_type="defect", severity="medium",
            status="confirmed", confidence=0.75,
            title="Orphan pages with no internal links pointing to them",
            root_cause="Pages exist but are not linked from anywhere else on the site",
            evidence=[{"type": "site_graph", "description": f"{len(orphans)} orphan pages found",
                       "urls": orphans[:10]}],
            suggested_action={
                "summary": "Add internal links to orphan pages from relevant navigation or content",
                "steps": ["Identify high-value orphan pages", "Link them from navigation or related content"],
                "priority": "medium", "effort": "low",
                "expected_benefit": "Improves discoverability and visitor navigation",
                "verification": "Confirm pages have inbound internal links",
            },
            provenance={"skill": "engagement-audit", "script": "analyze_engagement.py",
                        "rule_id": "orphan-pages"},
        ))

    if dead_ends:
        findings.append(make_finding(
            category="engagement", finding_type="proactive_improvement", severity="low",
            status="confirmed", confidence=0.7,
            title="Dead-end pages with no outgoing links",
            root_cause="Pages provide no next step for the visitor",
            evidence=[{"type": "site_graph", "description": f"{len(dead_ends)} dead-end pages found",
                       "urls": dead_ends[:10]}],
            suggested_action={
                "summary": "Add related links or calls-to-action on dead-end pages",
                "steps": ["Add related-content links", "Add a clear next-step call-to-action"],
                "priority": "low", "effort": "low",
                "expected_benefit": "Keeps visitors engaged longer",
                "verification": "Confirm pages link to at least one next step",
            },
            provenance={"skill": "engagement-audit", "script": "analyze_engagement.py",
                        "rule_id": "dead-ends"},
        ))

    breadcrumb_mismatches = [p.url for p in artifacts.pages if p.breadcrumb_visible and not p.breadcrumb_schema]
    if breadcrumb_mismatches:
        findings.append(make_finding(
            category="engagement", finding_type="proactive_improvement", severity="low",
            status="confirmed", confidence=0.65,
            title="Visible breadcrumbs lack matching BreadcrumbList structured data",
            root_cause="Breadcrumb navigation is visible but not machine-readable",
            evidence=[{"type": "breadcrumb", "description": "Visible breadcrumb without schema",
                       "urls": breadcrumb_mismatches[:10]}],
            suggested_action={
                "summary": "Add BreadcrumbList JSON-LD matching visible breadcrumbs",
                "steps": ["Add BreadcrumbList schema to pages with visible breadcrumbs"],
                "priority": "low", "effort": "low",
                "expected_benefit": "Improves machine understanding of site structure",
                "verification": "Validate BreadcrumbList JSON-LD",
            },
            provenance={"skill": "engagement-audit", "script": "analyze_engagement.py",
                        "rule_id": "breadcrumb-mismatch"},
        ))

    gap_pages = rendering_result.get("metrics", {}).get("raw_rendered_gap_pages", [])
    return skill_result(
        "engagement-audit", findings=findings,
        metrics={"orphan_pages": len(orphans), "dead_end_pages": len(dead_ends),
                 "rendering_gap_pages": len(gap_pages)},
    )
