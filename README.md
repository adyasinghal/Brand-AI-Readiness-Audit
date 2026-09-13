# Brand AI-Readiness Audit Marketplace (v4.4.1)

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

## Changelog (v4.2 -> v4.3)

Six further correctness/rigor gaps, found by re-reading the actual code against
the Round-3 handout rather than assuming the v4.2 pass covered everything:

1. **True cancellation for the one genuine hang risk.** A `ThreadPoolExecutor`
   future timeout can *detect* a hung specialist but cannot kill its thread.
   That's an accepted, documented limitation for in-process analysis functions
   (the v4.0 architecture's explicit shared-memory choice), but headless
   rendering spawns a real browser process that can genuinely hang. Added
   `common/subprocess_isolation.py`: rendering now runs in a real child process
   with `join(timeout)` + `terminate()` + `kill()` -- the parent is guaranteed to
   regain control by the deadline no matter what the browser does. Verified with
   a test that hands it a function that loops forever and confirms it's killed
   within bounds.
2. **Retries, redirects, and timeouts are now counted as distinct telemetry**
   (`redirects_followed`, `requests_timed_out`) instead of folding into a single
   generic "failed" bucket, so budget exhaustion and fetch failure are
   separately reportable.
3. **Coverage metrics were not factual**: `run_audit.py` reported
   `pages_discovered == pages_analyzed == len(artifacts.pages)` -- one number,
   reused three times, regardless of how many links were actually discovered
   vs. fetched vs. containing real content. `analyze_crawlability.py` also
   hardcoded `pages_skipped: 0`. Both fixed: `acquire_site.py` now tracks a real
   `discovered` superset (every unique link seen, whether or not it was ever
   fetched) separately from fetched/analyzed/blocked/timed-out/skipped, with a
   reason-coded skip breakdown.
4. **External corroboration didn't compare claim values** -- `corroborate_claims.py`
   treated "the search returned anything" as corroboration and never actually
   populated its own contradiction-detection code path. Rewritten to normalize
   and compare claim values (phone/price digit-sequences, structured text)
   against result content, distinguish `corroborated` / `contradicted` /
   `not_found` / `not_checked` (the last two are never conflated), record the
   actual query issued per claim, and represent a conflicting value explicitly
   (both values + source) rather than a vague warning. `assess_external_footprint.py`
   now also records its query formulation and a `source_diversity` (distinct-
   domain) proxy for source quality.
5. **Recommendations guaranteed even with zero findings** -- already correctly
   implemented (`_GENERIC_BASELINE` in `generate_recommendations.py`) and
   already tested; re-verified, no change needed.
6. **Report could omit execution status, limitations, or a confidence score.**
   Added `skills/audit-orchestrator/scripts/execution_summary.py`:
   `execution_status` (completed / completed_with_timeouts / degraded /
   partial_deadline_reached, derived from real deadline/skill-failure/worker-
   timeout state), `limitations` (plain-English, each gated on an actual signal
   from the run -- never unconditional boilerplate), and `confidence` (the
   *minimum* of crawl completeness, identity confidence, and an execution
   penalty, with the method spelled out -- a weak link caps the score rather
   than being averaged away). `validate_report.py` now requires all three.

33 new tests across `tests/test_isolation_and_coverage.py`,
`tests/test_corroboration_quality.py`, and `tests/test_report_completeness.py`.
101/101 tests pass; three existing assertions were updated to check the more
specific, now-real distinction they previously couldn't (a generic
`"fetch_failed"` became `"fetch_timeout"` for an actual timeout, and the
cross-origin-redirect warning is now `"fetch_cross_origin_redirect_blocked"`).

## Changelog (v4.3 -> v4.4)

Round-3 review follow-ups:

1. **`merge_findings.merge_evidence` now dedupes evidence entries** (by type +
   description + sorted urls) instead of blindly concatenating them across
   merged findings, so a near-duplicate merge no longer carries repeated
   evidence.
2. **Fixed a real, silent bug**: `extract_claims.py`, `resolve_entity_identity.py`,
   and `analyze_machine_readability.py` all checked `isinstance(block, dict)`
   on JSON-LD blocks, but real `PageArtifact.jsonld_blocks` are frozen into
   `MappingProxyType` by `freeze_value()` (v4.0 section 2) -- so on every real
   crawl, entity resolution, structured-claim extraction, and machine-readability
   schema checks were silently seeing zero JSON-LD blocks. Only synthetic-dict
   test fixtures (not real crawls) exercised the `dict` branch, which is why 101
   passing tests never caught it. Fixed by checking `collections.abc.Mapping`
   instead.
3. **Sitemap-only pages are now actually crawled, not just counted.**
   `acquire_site.py` recorded sitemap URLs in `discovered` for coverage stats
   but never queued them for fetching -- a page listed only in the sitemap and
   linked from nowhere else would never be fetched at all, so `isolated_clusters`
   could never fire from that path. Sitemap URLs are now also seeded into the
   crawl queue (depth 1, subject to every existing bound).
4. **New fixtures** (`tests/fixtures_server.py`) and tests
   (`tests/test_scenario_fixtures.py`): a multi-brand (conflicting-identity)
   site, a stale-commercial-facts product page, and a broken-navigation
   (sitemap-only, isolated-cluster) page pair -- plus external-search-unavailable
   combos (unconfigured provider; provider configured but failing mid-query)
   evaluated against a real fixture-crawled identity instead of a synthetic one.
5. **SKILL.md documentation audit**: all four skills now declare `allowed-tools`
   and a `Dependencies` section (Python packages, optional capabilities, env
   vars), and the three non-entrypoint skills each gained a concrete
   input/output `Example`.

107/107 tests pass (101 prior + 6 new in `tests/test_scenario_fixtures.py`).

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

107 tests across 11 files, all network-free (a local `ThreadingHTTPServer`
fixture stands in for live sites -- see `tests/fixtures_server.py`):

- `tests/test_smoke.py` -- full DAG wiring against a synthetic fixture.
- `tests/test_integration.py` -- real crawls against the local fixture server.
- `tests/test_findings_scripts.py` -- every finding-producing script under
  normal, malformed-input, insufficient-evidence, and worker-timeout
  conditions.
- `tests/test_runtime_instrumentation.py` -- deliberately slow fixtures verify
  the shared deadline is actually respected and telemetry is real.
- `tests/test_dedup_and_recommendations.py` -- merge dedup (both directions)
  and the four required recommendation scenarios.
- `tests/test_capabilities_and_immutability.py` -- capability-tier registry
  and the `MappingProxyType` mutation-detection layer.
- `tests/test_safety.py` -- SSRF/URL-safety classification, every robots.txt
  fetch state and its fail-closed behavior, real sitemap.xml/llms.txt fetch
  states, mid-stream byte-budget truncation, same-origin vs. cross-origin
  redirects, and a static guard against mutating HTTP methods.
- `tests/test_isolation_and_coverage.py` -- subprocess-isolation hard-kill
  guarantee, distinct redirect/timeout/retry counters, and factual
  discovered/fetched/analyzed coverage breakdowns.
- `tests/test_corroboration_quality.py` -- claim-value comparison (phone/price
  digit-sequence matching), not-checked-vs-not-found, query recording, and
  explicit conflict representation.
- `tests/test_report_completeness.py` -- execution_status derivation,
  signal-gated limitations, confidence scoring, and a real end-to-end report's
  field completeness.
- `tests/test_scenario_fixtures.py` -- multi-brand identity conflict, stale
  commercial facts, broken-navigation isolated clusters, and external-search-
  unavailable combos, all against real fixture-crawled data.

```
python3 -m pytest tests/ -q
```


### Packaging and measurement notes

- Runtime dependencies are in `requirements.txt`; test/render dependencies are in `requirements-dev.txt`.
- Runtime telemetry reports both the Python `tracemalloc` peak and a best-effort parent-process RSS measurement. These are distinct metrics; Chromium child-process RSS is not claimed unless separately available.
- The package is intentionally read-only and excludes generated cache artifacts from release archives.
