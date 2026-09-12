# Brand AI-Readiness Audit Marketplace (v4.1)

An Agent Skill Marketplace (agentskills.io format) that audits a website for
AI discoverability and on-site engagement problems, and emits a single
structured report of findings, prioritized suggested actions, and a
first-class recommendations section.

Recommend-only: no skill ever modifies a live site.

## Skills

- **audit-orchestrator** (entrypoint) -- validates input, acquires the site
  once, schedules the DAG across a single bounded thread pool, merges and
  deduplicates findings, prioritizes them, generates recommendations,
  validates the report, and emits it.
- **crawl-render-audit** -- reachability, robots.txt, AI-crawler access,
  raw-vs-rendered gaps (heuristic + optional real headless rendering),
  structured data, llms.txt.
- **freshness-corroboration** -- claim extraction, important-fact ranking,
  one-time entity resolution, freshness, corroboration, external footprint
  (calibrated so missing evidence is never a confirmed defect).
- **engagement-audit** -- site graph, orphan pages, dead ends, breadcrumb
  cross-check.

## DAG

```
validate_input -> acquire_site (once)
-> independent batch (thread pool): crawlability, rendering,
   machine_readability, ai_crawler_access, llms_txt, extract_claims,
   resolve_entity_identity, build_site_graph
-> identify_important_facts (sequential, between the two batches)
-> dependent batch (same thread pool): freshness, corroboration, footprint,
   engagement
-> merge_findings -> prioritize_findings -> generate_recommendations
-> validate_report -> report
```

## Capability tiers (`common/capabilities.py`)

Every check in the marketplace falls into exactly one tier, surfaced in every
report under `coverage.capabilities`:

| Tier | Meaning | Checks |
|---|---|---|
| **executable** | Runs today, no external dependency | robots/AI-crawler access, crawlability, JSON-LD readability, llms.txt, heuristic claim extraction, JSON-LD-based entity resolution, site graph/engagement, freshness from dated facts, dedup/merge/prioritize/validate, rendering-gap heuristic |
| **fallback** | Has a real implementation that degrades honestly when its dependency is missing | real headless rendering (falls back to the heuristic, `suspected` instead of `confirmed`), external corroboration and footprint search (fall back to `insufficient_evidence`, never a confirmed absence) |

`coverage.capabilities.capabilities_detected` reports what was actually
available *this run* (e.g. `headless_rendering: true` if a real Chromium was
found and used; `external_search: true` if `SEARCH_API_URL` is configured).

## Runtime instrumentation (`common/instrumentation.py`)

Every report's `coverage.instrumentation` block is **measured, not
placeholder**: per-stage start/end/duration, HTTP requests attempted /
completed / failed, bytes downloaded, pages skipped (with reasons), external
fetches attempted / completed, worker-timeout events, and a real
`tracemalloc`-measured peak memory in MB. Anything genuinely unmeasured is
`null`, never a fabricated `0`.

## Recommendations (first-class output)

`report["recommendations"]` is always present and non-empty on a successful
audit -- even when there are no confirmed defects, all evidence is
insufficient, the site is small, or the site is already well-structured
(`generate_recommendations.py`). Recommendations are evidence-aware (derived
from real findings where possible), non-duplicative (reuse the dedup
similarity logic so a recommendation never restates a confirmed defect), and
always `finding_type == "proactive_improvement"`, kept separate from
`findings`. `validate_report.py` treats an empty recommendations array as a
validation warning, not a silently acceptable report.

## Second-defense immutability

On top of `frozen=True` dataclasses, every nested dict/list on `PageArtifact`
and `AuditArtifacts` is wrapped in `MappingProxyType` (`freeze_value` in
`common/models.py`): any mutation attempt raises `TypeError` immediately,
rather than silently corrupting shared state. `hash_artifacts()` provides a
stable content hash for a frozen-artifact regression check.

## Run it

```
pip install -r requirements.txt --break-system-packages
playwright install chromium   # optional: enables real headless rendering
python3 skills/audit-orchestrator/scripts/run_audit.py https://example.com
```

Set `SEARCH_API_URL` (and optionally `SEARCH_API_KEY`) to enable external
corroboration/footprint search; without it, those checks report
`insufficient_evidence`, per the calibration in v4.0 section 5.

## Tests

42 tests across 5 files, all network-free (a local `ThreadingHTTPServer`
fixture stands in for live sites -- see `tests/fixtures_server.py`):

- `tests/test_smoke.py` -- full DAG wiring against a synthetic fixture.
- `tests/test_integration.py` -- real crawls against the local fixture server:
  normal pages, robots.txt disallow, redirects, malformed JSON-LD, timeouts,
  error pages, orphan pages, JS-heavy pages (both the heuristic-only and, when
  a real Chromium is available, the confirmed-by-real-render path), and a full
  `run_audit` end-to-end pass.
- `tests/test_findings_scripts.py` -- every finding-producing script under
  normal, malformed-input, insufficient-evidence, and worker-timeout
  conditions.
- `tests/test_runtime_instrumentation.py` -- deliberately slow fixtures verify
  the shared deadline is actually respected and telemetry is real.
- `tests/test_dedup_and_recommendations.py` -- merge dedup (both directions)
  and the four required recommendation scenarios.
- `tests/test_capabilities_and_immutability.py` -- capability-tier registry
  and the `MappingProxyType` mutation-detection layer.

```
python3 -m pytest tests/ -q
```
