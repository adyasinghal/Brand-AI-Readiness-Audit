"""check_llms_txt.py -- presence/validity is a metric; absence is proactive only
(v4.0 section 8.2)."""
from models import skill_result, make_finding


def check_llms_txt(artifacts, deadline):
    present = artifacts.llms_txt_data.get("present", False)
    findings = []
    if not present:
        findings.append(make_finding(
            category="ai_discoverability", finding_type="proactive_improvement", severity="low",
            status="confirmed", confidence=0.6,
            title="No llms.txt file found",
            root_cause="Site does not publish an llms.txt guidance file",
            evidence=[{"type": "llms_txt", "description": "/llms.txt not found",
                       "urls": [artifacts.site_url.rstrip('/') + "/llms.txt"]}],
            suggested_action={
                "summary": "Publish an llms.txt summarizing key pages for AI assistants",
                "steps": ["Create /llms.txt", "List key pages and a short site summary"],
                "priority": "low", "effort": "low",
                "expected_benefit": "Gives assistants a curated entry point",
                "verification": "Confirm /llms.txt is reachable and valid",
            },
            provenance={"skill": "crawl-render-audit", "script": "check_llms_txt.py",
                        "rule_id": "no-llms-txt"},
        ))
    return skill_result("crawl-render-audit", findings=findings, metrics={"llms_txt_present": present})
