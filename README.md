# Brand AI-Readiness Audit Marketplace (v4.2)

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

## Safety (`common/url_safety.py`, `acquire_site.py`)

Every URL the audit is about to fetch -- the initial target, robots.txt,
sitemap.xml, llms.txt, every discovered link, and every redirect hop -- passes
`classify_url()` first:

- only `http`/`https`; credentials-in-URL (`user:pass@host`) are rejected
- known cloud-metadata hosts/IPs (e.g. `169.254.169.254`) are rejected
  unconditionally, with no override
- by default, loopback/private/link-local/multicast/reserved addresses are all
  rejected; DNS resolution failure is treated as unsafe, not skipped
- an `allow_private_targets` flag exists solely so tests can point the audit at
  a local fixture server -- production callers (the CLI, `run_audit()`'s
  default) never set it
- redirects are followed one hop at a time so each hop is re-validated;
  cross-origin redirects are recorded and not followed
- response bodies are streamed and truncated against `MAX_TOTAL_BYTES` *during*
  download, never after a full read

Robots.txt is never allowed to fail open: a confirmed 404 (`absent`) is the
only failure-adjacent state that means "allowed everything". Every other
outcome -- `timeout`, `inaccessible` (other HTTP/connection error),
`malformed` (undecodable body), or `blocked` (the robots URL itself failed the
SSRF check) -- makes the crawl conservative (the single initial page only, no
links followed) and is reported as `insufficient_evidence` by
`analyze_crawlability`/`check_ai_crawler_access`, never inferred as either an
allow or a confirmed disallow. `sitemap.xml` and `llms.txt` are now actually
fetched (previously both were hardcoded to "not found" regardless of the real
site -- see CHANGELOG below); their present/absent/inaccessible/malformed
states are all distinguished and recorded in `sitemap_data`/`llms_txt_data`.

Only GET requests are ever issued against the target site. Headless rendering
(when available) only calls `page.goto()` and reads text -- it never submits a
form, clicks, types, or evaluates page-mutating script.

## Changelog (v4.1 -> v4.2)

Fixed three correctness/safety gaps found by re-reading the actual code
against the Round-3 handout's hard safety requirements, not just the v4.0
architecture document:

1. **No SSRF protection existed at all** -- any URL, including
   `169.254.169.254` or a private/loopback address, would have been crawled.
   Added `common/url_safety.py` and wired it into every fetch.
2. **Robots.txt failed open**: `allowed = rp.can_fetch(...) if robots_ok else
   True` meant a robots.txt fetch failure was treated as *allowed*. Fixed to
   fail closed (conservative single-page crawl) and to distinguish
   ok/absent/timeout/inaccessible/malformed/blocked instead of a single
   boolean.
3. **`llms.txt` and `sitemap.xml` were never fetched** -- both were hardcoded
   to "not found"/"not discovered" regardless of the actual site. Both are now
   really fetched and parsed, bounded, with their fetch status recorded.

Also fixed: byte budgets are now enforced by streaming and truncating mid-
download instead of only checking the total after each full response; redirects
are now followed one hop at a time with same-origin enforcement instead of via
`requests`' built-in `allow_redirects=True` (which does not re-validate SSRF
per hop). 25 new tests in `tests/test_safety.py` cover all of the above; none
of the 42 pre-existing tests needed behavior changes (three test call sites
needed an explicit `allow_private_targets=True` to keep pointing at the local
fixture server, and two fixtures needed a `status` field added).

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

68 tests across 7 files, all network-free (a local `ThreadingHTTPServer`
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
- `tests/test_safety.py` -- SSRF/URL-safety classification (schemes,
  credentials, loopback/private/link-local/metadata, DNS-failure), every
  robots.txt fetch state (ok/absent/timeout/inaccessible/malformed) and its
  fail-closed behavior, real sitemap.xml/llms.txt fetch states, mid-stream
  byte-budget truncation, same-origin vs. cross-origin redirect handling, and
  a static guard against mutating HTTP methods or form-submitting/JS-evaluating
  Playwright calls.

```
python3 -m pytest tests/ -q
```
