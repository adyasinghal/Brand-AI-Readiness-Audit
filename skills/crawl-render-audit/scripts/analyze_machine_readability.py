"""analyze_machine_readability.py -- headings, JSON-LD, semantic linkage (v4.0 section 8.2)."""
from models import skill_result, make_finding


def analyze_machine_readability(artifacts, deadline):
    pages = artifacts.pages
    no_jsonld = [p for p in pages if not p.jsonld_blocks]
    no_headings = [p for p in pages if not p.headings]

    findings = []
    if pages and len(no_jsonld) == len(pages):
        findings.append(make_finding(
            category="ai_discoverability", finding_type="defect", severity="high",
            status="confirmed", confidence=0.85,
            title="No structured data (JSON-LD) found on any crawled page",
            root_cause="Pages lack schema.org JSON-LD markup",
            evidence=[{"type": "structured_data", "description": f"0/{len(pages)} pages contain JSON-LD",
                       "urls": [p.url for p in pages][:10]}],
            suggested_action={
                "summary": "Add Organization/Product/Article JSON-LD to key pages",
                "steps": ["Identify page types", "Add matching schema.org JSON-LD blocks"],
                "priority": "high", "effort": "medium",
                "expected_benefit": "Facts become machine-extractable",
                "verification": "Validate JSON-LD with a schema.org validator",
            },
            provenance={"skill": "crawl-render-audit", "script": "analyze_machine_readability.py",
                        "rule_id": "no-jsonld"},
        ))
    if no_headings:
        findings.append(make_finding(
            category="ai_discoverability", finding_type="proactive_improvement", severity="low",
            status="confirmed", confidence=0.7,
            title="Some pages lack semantic headings",
            root_cause="Pages have no h1-h6 elements",
            evidence=[{"type": "headings", "description": f"{len(no_headings)} pages have no headings",
                       "urls": [p.url for p in no_headings][:10]}],
            suggested_action={
                "summary": "Add semantic heading structure",
                "steps": ["Add an h1 per page", "Structure sections with h2/h3"],
                "priority": "low", "effort": "low",
                "expected_benefit": "Improves text extraction quality",
                "verification": "Inspect DOM for heading tags",
            },
            provenance={"skill": "crawl-render-audit", "script": "analyze_machine_readability.py",
                        "rule_id": "no-headings"},
        ))

    return skill_result(
        "crawl-render-audit", findings=findings,
        metrics={"pages_with_jsonld": len(pages) - len(no_jsonld), "pages_without_headings": len(no_headings)},
    )
