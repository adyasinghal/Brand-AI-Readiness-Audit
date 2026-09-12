"""check_ai_crawler_access.py -- compares general vs AI-specific robots verdicts
(v4.0 section 8.2)."""
from models import skill_result, make_finding


def check_ai_crawler_access(artifacts, deadline):
    directives = artifacts.robots_data.get("ai_crawler_directives", {})
    blocked = [agent for agent, verdict in directives.items() if verdict == "disallow"]

    findings = []
    if blocked:
        findings.append(make_finding(
            category="ai_discoverability", finding_type="defect", severity="high",
            status="confirmed", confidence=0.9,
            title="AI crawlers are blocked by robots.txt",
            root_cause=f"robots.txt disallows: {', '.join(blocked)}",
            evidence=[{"type": "robots", "description": "AI crawler directives disallow access",
                       "urls": [artifacts.site_url]}],
            suggested_action={
                "summary": "Allow known AI crawler user-agents in robots.txt",
                "steps": [f"Remove Disallow rules for {a}" for a in blocked],
                "priority": "high", "effort": "low",
                "expected_benefit": "Enables AI assistants to crawl and cite the site",
                "verification": "Re-check robots.txt for the listed user-agents",
            },
            provenance={"skill": "crawl-render-audit", "script": "check_ai_crawler_access.py",
                        "rule_id": "ai-crawler-blocked"},
        ))

    return skill_result("crawl-render-audit", findings=findings, metrics={"blocked_ai_crawlers": blocked})
