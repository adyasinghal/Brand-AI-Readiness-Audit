"""run_audit.py -- entrypoint: validate input, acquire once, schedule the DAG,
enforce budgets, merge, prioritize, generate recommendations, validate, emit the
report (v4.0 section 1, 8.1, plus the instrumentation/recommendations addendum).

Skill folder names contain hyphens (agentskills.io convention) so this module wires
sibling scripts via sys.path rather than hyphenated package imports.
"""
import os
import sys
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError, as_completed
from datetime import datetime, timezone
from time import monotonic
from urllib.parse import urlparse
from dotenv import load_dotenv

load_dotenv()  # for local development convenience; production uses environment variables

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
from instrumentation import Instrumentation
from capabilities import detect_capabilities, capability_report

from acquire_site import acquire_site
from merge_findings import merge_findings
from prioritize_findings import prioritize_findings
from generate_recommendations import generate_recommendations
from validate_report import validate_report
from execution_summary import derive_execution_status, derive_limitations, overall_confidence

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

# Per-worker timeout used only to *detect and record* a hung specialist so the
# instrumentation layer can report it; the shared AuditDeadline remains the source
# of truth for stage budgets.
_WORKER_TIMEOUT_S = 30


def validate_input(url: str) -> str:
    p = urlparse(url)
    if not p.scheme:
        url = "https://" + url
        p = urlparse(url)
    if not p.netloc:
        raise ValueError(f"Invalid URL: {url}")
    return url


def _await_result(future, name, stage, instrumentation):
    try:
        return future.result(timeout=_WORKER_TIMEOUT_S)
    except FutureTimeoutError:
        instrumentation.record_worker_timeout(stage, name)
        return {"skill": name, "status": "insufficient_evidence", "findings": [], "metrics": {},
                "warnings": [f"specialist '{name}' exceeded {_WORKER_TIMEOUT_S}s and was abandoned"],
                "coverage": {"pages_analyzed": 0, "pages_skipped": 0,
                             "queries_attempted": 0, "queries_completed": 0}}
    except Exception as exc:
        return {"skill": name, "status": "failed", "findings": [], "metrics": {},
                "warnings": [f"specialist failed: {exc}"],
                "coverage": {"pages_analyzed": 0, "pages_skipped": 0,
                             "queries_attempted": 0, "queries_completed": 0}}


def run_independent_batch(artifacts, deadline, limits, capabilities, instrumentation):
    instrumentation.start_stage("independent_batch")
    jobs = {
        "crawlability": lambda: analyze_crawlability(artifacts, deadline),
        "rendering": lambda: analyze_rendering(artifacts, deadline, limits, capabilities),
        "machine_readability": lambda: analyze_machine_readability(artifacts, deadline),
        "ai_crawler_access": lambda: check_ai_crawler_access(artifacts, deadline),
        "llms_txt": lambda: check_llms_txt(artifacts, deadline),
        "claims": lambda: extract_claims(artifacts, deadline),
        "entity_identity": lambda: resolve_entity_identity(artifacts, deadline),
        "site_graph": lambda: build_site_graph(artifacts, deadline),
    }
    with ThreadPoolExecutor(max_workers=limits.MAX_ANALYSIS_WORKERS) as pool:
        futures = {pool.submit(fn): name for name, fn in jobs.items()}
        results = {futures[f]: _await_result(f, futures[f], "independent_batch", instrumentation)
                   for f in as_completed(futures)}
    instrumentation.end_stage("independent_batch")
    return results


def run_dependent_batch(facts, entity_identity, artifacts, site_graph, rendering_result,
                         deadline, limits, instrumentation):
    instrumentation.start_stage("dependent_batch")
    jobs = {
        "freshness": lambda: assess_freshness(facts, artifacts, deadline),
        "corroboration": lambda: corroborate_claims(facts, entity_identity, artifacts, deadline, limits, instrumentation),
        "footprint": lambda: assess_external_footprint(artifacts, entity_identity, deadline, limits, instrumentation),
        "engagement": lambda: analyze_engagement(artifacts, site_graph, rendering_result, deadline),
    }
    with ThreadPoolExecutor(max_workers=limits.MAX_ANALYSIS_WORKERS) as pool:
        futures = {pool.submit(fn): name for name, fn in jobs.items()}
        results = {futures[f]: _await_result(f, futures[f], "dependent_batch", instrumentation)
                   for f in as_completed(futures)}
    instrumentation.end_stage("dependent_batch")
    return results


def run_audit(site_url: str, limits=DEFAULT_LIMITS, allow_private_targets: bool = False) -> dict:
    """allow_private_targets defaults to False (safe): the CLI and any production
    caller never sets it. It exists only so tests can point the audit at a local
    ThreadingHTTPServer on 127.0.0.1 without weakening the default SSRF policy."""
    site_url = validate_input(site_url)
    deadline = make_deadline(limits)
    instrumentation = Instrumentation()
    capabilities = detect_capabilities()

    artifacts = acquire_site(site_url, deadline, limits, instrumentation,
                              allow_private_targets=allow_private_targets)

    independent = run_independent_batch(artifacts, deadline, limits, capabilities, instrumentation)

    # Mandatory sequential step, wired into the executable schedule -- not only the
    # architecture diagram (v4.0 section 1, 8.1). Consumes extract_claims' output.
    instrumentation.start_stage("identify_important_facts")
    facts = identify_important_facts(independent["claims"], deadline)
    instrumentation.end_stage("identify_important_facts")

    dependent = run_dependent_batch(
        facts, independent["entity_identity"], artifacts,
        independent["site_graph"], independent["rendering"], deadline, limits, instrumentation,
    )

    skill_results = [
        independent["crawlability"], independent["rendering"], independent["machine_readability"],
        independent["ai_crawler_access"], independent["llms_txt"],
        dependent["freshness"], dependent["corroboration"], dependent["footprint"], dependent["engagement"],
    ]

    merged = merge_findings(skill_results)
    prioritized = prioritize_findings(merged)
    recommendations = generate_recommendations(skill_results, prioritized)

    memory_peak_mb = instrumentation.stop_memory_tracking_mb()
    telemetry = instrumentation.as_dict(memory_peak_mb)

    acq_coverage = artifacts.acquisition_metadata.get("coverage", {})
    coverage = {
        # Factual, non-equated coverage counts (Round-3 handout, Priority 2 #3):
        # discovered/fetched/analyzed are different numbers and must not collapse
        # into one len(pages) reused three times.
        "pages_discovered": acq_coverage.get("urls_discovered", len(artifacts.pages)),
        "pages_fetched_attempted": acq_coverage.get("urls_fetched_attempted", len(artifacts.pages)),
        "pages_fetched_ok": acq_coverage.get("urls_fetched_ok", len(artifacts.pages)),
        "pages_analyzed": acq_coverage.get("urls_analyzed", len(artifacts.pages)),
        "pages_blocked": acq_coverage.get("urls_blocked", 0),
        "pages_timed_out": acq_coverage.get("urls_timed_out", 0),
        "pages_failed_other": acq_coverage.get("urls_failed_other", 0),
        "pages_never_attempted": acq_coverage.get("urls_never_attempted", 0),
        "pages_skipped": telemetry["pages_skipped"],
        "skip_reason_counts": acq_coverage.get("skip_reason_counts", {}),
        "rendered_pages": independent["rendering"].get("metrics", {}).get("rendered_pages", 0),
        "external_claims_checked": dependent["corroboration"].get("metrics", {}).get("claims_checked", 0),
        "external_footprint_queries": dependent["footprint"].get("metrics", {}).get("queries_attempted", 0),
        "external_fetches": telemetry["external_fetches_attempted"],
        "identity_confidence": independent["entity_identity"].get("data", {}).get("confidence", 0.0),
        "memory_budget_used_mb": memory_peak_mb,  # None if unmeasured, never a fabricated 0
        "runtime_seconds": round(monotonic() - deadline.started_monotonic, 3),  # measured, not derived from the budget
        "deadline_reached": deadline.expired(),
        "capabilities": capability_report(capabilities),
        "instrumentation": telemetry,
    }

    report = {
        "site": site_url,
        "audited_at": datetime.now(timezone.utc).isoformat(),
        "summary": {},
        "coverage": coverage,
        "warnings": list(artifacts.warnings),
        "findings": prioritized,
        "recommendations": recommendations,
    }

    # Never-empty, never-misleading report fields (Round-3 handout item 6): every
    # audit -- success, degraded, or deadline-truncated -- gets a real
    # execution_status, a limitations list derived from actual telemetry (not
    # boilerplate), and an overall confidence score with its method shown.
    execution_status = derive_execution_status(deadline, skill_results, telemetry["worker_timeout_events"])
    report["execution_status"] = execution_status
    report["limitations"] = derive_limitations(artifacts, capabilities, coverage, execution_status)
    report["confidence"] = overall_confidence(coverage, execution_status)

    return validate_report(report)


if __name__ == "__main__":
    import json
    target = sys.argv[1] if len(sys.argv) > 1 else "https://example.com"
    print(json.dumps(run_audit(target), indent=2, default=str))
