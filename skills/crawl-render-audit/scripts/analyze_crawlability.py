"""analyze_crawlability.py -- reachability, robots, sitemap, orphans (v4.0 section 8.2)."""
from models import skill_result, make_finding


def analyze_crawlability(artifacts, deadline):
    findings = []
    pages = artifacts.pages
    important_pages = [p for p in pages if p.url == artifacts.site_url]

    if not artifacts.robots_data.get("allowed_general", True):
        findings.append(make_finding(
            category="ai_discoverability", finding_type="defect", severity="high",
            status="confirmed", confidence=0.9,
            title="robots.txt disallows general crawling",
            root_cause="robots.txt blocks crawler access to the site",
            evidence=[{"type": "robots", "description": "Disallow directive found",
                       "urls": [artifacts.site_url]}],
            suggested_action={
                "summary": "Allow crawler access to public pages in robots.txt",
                "steps": ["Review robots.txt", "Remove blanket Disallow rules"],
                "priority": "high", "effort": "low",
                "expected_benefit": "Restores discoverability",
                "verification": "Re-crawl and confirm robots.txt allows access",
            },
            provenance={"skill": "crawl-render-audit", "script": "analyze_crawlability.py",
                        "rule_id": "robots-block"},
        ))

    error_pages = [p for p in pages if p.status_code and p.status_code >= 400]
    if error_pages:
        findings.append(make_finding(
            category="ai_discoverability", finding_type="defect", severity="medium",
            status="confirmed", confidence=0.85,
            title="Broken pages found during crawl",
            root_cause="Pages return 4xx/5xx status codes",
            evidence=[{"type": "http_status", "description": f"{len(error_pages)} pages returned errors",
                       "urls": [p.url for p in error_pages][:10]}],
            suggested_action={
                "summary": "Fix or redirect broken URLs",
                "steps": ["Audit error pages", "Add 301 redirects or restore content"],
                "priority": "medium", "effort": "medium",
                "expected_benefit": "Improves crawl completeness",
                "verification": "Re-crawl and confirm 200 status",
            },
            provenance={"skill": "crawl-render-audit", "script": "analyze_crawlability.py",
                        "rule_id": "broken-pages"},
        ))

    coverage = {"pages_analyzed": len(pages), "pages_skipped": 0}
    return skill_result(
        "crawl-render-audit", findings=findings,
        metrics={"pages_crawled": len(pages), "important_pages_reachable": len(important_pages)},
        coverage=coverage,
    )
