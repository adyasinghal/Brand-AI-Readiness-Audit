"""check_ai_crawler_access.py -- compares general vs AI-specific robots verdicts
(v4.0 section 8.2). When robots.txt could not be retrieved/parsed, directives are
empty and this reports insufficient evidence rather than silently implying
AI crawlers are allowed."""
from models import skill_result, make_finding, apply_invariant_i1


def check_ai_crawler_access(artifacts, deadline):
    directives = artifacts.robots_data.get("ai_crawler_directives", {})
    robots_status = artifacts.robots_data.get("status", "not_checked")
    blocked = [agent for agent, verdict in directives.items() if verdict == "disallow"]

    findings = []
    if not directives and robots_status not in ("ok", "absent", "not_checked"):
        findings.append(apply_invariant_i1(make_finding(
            category="ai_discoverability", finding_type="proactive_improvement", severity="low",
            status="insufficient_evidence", confidence=0.3,
            title="AI-crawler access could not be checked",
            root_cause=f"robots.txt status was '{robots_status}'; AI-crawler directives were not evaluated",
            evidence=[{"type": "robots", "description": f"robots.txt status: {robots_status}", "urls": []}],
            suggested_action={
                "summary": "Confirm robots.txt is reliably reachable", "steps": ["Re-run once reachable"],
                "priority": "low", "effort": "low", "expected_benefit": "Enables a real verdict",
                "verification": "Re-run and confirm robots_data.status is 'ok' or 'absent'",
            },
            provenance={"skill": "crawl-render-audit", "script": "check_ai_crawler_access.py",
                        "rule_id": "ai-crawler-unchecked"},
        )))
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
