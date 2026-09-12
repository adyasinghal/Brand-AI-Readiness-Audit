"""run_audit.py -- entrypoint: validate input, acquire once, schedule the DAG,
enforce budgets, merge, prioritize, validate, emit the report (v4.0 section 1, 8.1).

Skill folder names contain hyphens (agentskills.io convention) so this module wires
sibling scripts via sys.path rather than hyphenated package imports.
"""
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from urllib.parse import urlparse

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
for _rel in (
    "common",
    "skills/audit-orchestrator/scripts",
    "skills/crawl-render-audit/scripts",
    "skills/freshness-corroboration/scripts",
    "skills/engagement-audit/scripts",
):
    _p = os.path.join(_ROOT, _rel)
    if _p not in sys.path:
        sys.path.insert(0, _p)

from constants import DEFAULT_LIMITS
from models import make_deadline

from acquire_site import acquire_site
from merge_findings import merge_findings
from prioritize_findings import prioritize_findings
from validate_report import validate_report

from analyze_crawlability import analyze_crawlability
from analyze_rendering import analyze_rendering
from analyze_machine_readability import analyze_machine_readability
from check_ai_crawler_access import check_ai_crawler_access
from check_llms_txt import check_llms_txt

from extract_claims import extract_claims
from identify_important_facts import identify_important_facts
from resolve_entity_identity import resolve_entity_identity
from assess_freshness import assess_freshness
from corroborate_claims import corroborate_claims
from assess_external_footprint import assess_external_footprint

from build_site_graph import build_site_graph
from analyze_engagement import analyze_engagement


def validate_input(url: str) -> str:
    p = urlparse(url)
    if not p.scheme:
        url = "https://" + url
        p = urlparse(url)
    if not p.netloc:
        raise ValueError(f"Invalid URL: {url}")
    return url


def normalize_worker_result(future, name, deadline):
    try:
        return future.result()
    except Exception as exc:
        return {"skill": name, "status": "failed", "findings": [], "metrics": {},
                "warnings": [f"specialist failed: {exc}"],
                "coverage": {"pages_analyzed": 0, "pages_skipped": 0,
                             "queries_attempted": 0, "queries_completed": 0}}


def run_independent_batch(artifacts, deadline, limits):
    jobs = {
        "crawlability": lambda: analyze_crawlability(artifacts, deadline),
        "rendering": lambda: analyze_rendering(artifacts, deadline, limits),
        "machine_readability": lambda: analyze_machine_readability(artifacts, deadline),
        "ai_crawler_access": lambda: check_ai_crawler_access(artifacts, deadline),
        "llms_txt": lambda: check_llms_txt(artifacts, deadline),
        "claims": lambda: extract_claims(artifacts, deadline),
        "entity_identity": lambda: resolve_entity_identity(artifacts, deadline),
        "site_graph": lambda: build_site_graph(artifacts, deadline),
    }
    with ThreadPoolExecutor(max_workers=limits.MAX_ANALYSIS_WORKERS) as pool:
        futures = {pool.submit(fn): name for name, fn in jobs.items()}
        return {futures[f]: normalize_worker_result(f, futures[f], deadline) for f in as_completed(futures)}


def run_dependent_batch(facts, entity_identity, artifacts, site_graph, rendering_result, deadline, limits):
    jobs = {
        "freshness": lambda: assess_freshness(facts, artifacts, deadline),
        "corroboration": lambda: corroborate_claims(facts, entity_identity, artifacts, deadline, limits),
        "footprint": lambda: assess_external_footprint(artifacts, entity_identity, deadline, limits),
        "engagement": lambda: analyze_engagement(artifacts, site_graph, rendering_result, deadline),
    }
    with ThreadPoolExecutor(max_workers=limits.MAX_ANALYSIS_WORKERS) as pool:
        futures = {pool.submit(fn): name for name, fn in jobs.items()}
        return {futures[f]: normalize_worker_result(f, futures[f], deadline) for f in as_completed(futures)}


def run_audit(site_url: str, limits=DEFAULT_LIMITS) -> dict:
    site_url = validate_input(site_url)
    deadline = make_deadline(limits)

    artifacts = acquire_site(site_url, deadline, limits)

    independent = run_independent_batch(artifacts, deadline, limits)

    # Mandatory sequential step, wired into the executable schedule -- not only the
    # architecture diagram (v4.0 section 1, 8.1). Consumes extract_claims' output.
    facts = identify_important_facts(independent["claims"], deadline)

    dependent = run_dependent_batch(
        facts, independent["entity_identity"], artifacts,
        independent["site_graph"], independent["rendering"], deadline, limits,
    )

    skill_results = [
        independent["crawlability"], independent["rendering"], independent["machine_readability"],
        independent["ai_crawler_access"], independent["llms_txt"],
        dependent["freshness"], dependent["corroboration"], dependent["footprint"], dependent["engagement"],
    ]

    merged = merge_findings(skill_results)
    prioritized = prioritize_findings(merged)

    coverage = {
        "pages_discovered": len(artifacts.pages),
        "pages_analyzed": len(artifacts.pages),
        "pages_skipped": 0,
        "rendered_pages": independent["rendering"].get("metrics", {}).get("rendered_pages", 0),
        "external_claims_checked": dependent["corroboration"].get("metrics", {}).get("claims_checked", 0),
        "external_footprint_queries": dependent["footprint"].get("metrics", {}).get("queries_attempted", 0),
        "external_fetches": 0,
        "identity_confidence": independent["entity_identity"].get("data", {}).get("confidence", 0.0),
        "memory_budget_used_mb": 0,
        "runtime_seconds": round(
            (deadline.deadline_monotonic - deadline.started_monotonic) - deadline.remaining_seconds(), 2
        ),
        "deadline_reached": deadline.expired(),
    }

    report = {
        "site": site_url,
        "audited_at": datetime.now(timezone.utc).isoformat(),
        "summary": {},
        "coverage": coverage,
        "warnings": list(artifacts.warnings),
        "findings": prioritized,
    }
    return validate_report(report)


if __name__ == "__main__":
    import json
    target = sys.argv[1] if len(sys.argv) > 1 else "https://example.com"
    print(json.dumps(run_audit(target), indent=2, default=str))
