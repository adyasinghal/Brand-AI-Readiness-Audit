# Execution policy

DAG: validate_input -> acquire_site (once) -> independent batch (8 jobs, thread
pool) -> identify_important_facts (sequential, CPU-only) -> dependent batch (4
jobs, same thread pool) -> merge_findings -> prioritize_findings ->
validate_report.

Budgets (seconds): ACQUISITION 110, RENDERING 55, EXTERNAL_ANALYSIS 55,
FINALIZATION_RESERVE 20, TOTAL_AUDIT_TIMEOUT 270. Worst case ~245s, 25s margin.

One shared, monotonic `AuditDeadline` governs every stage. A stage that
exhausts its budget returns partial or insufficient-evidence output; nothing
is silently dropped and a timeout is never treated as proof of a defect.

## Safety (see `common/url_safety.py` and `acquire_site.py`)

Every outbound URL -- initial target, robots.txt, sitemap.xml, llms.txt,
discovered links, redirect targets -- passes `classify_url()` before any
request is issued: only http/https, no credentials-in-URL, no cloud-metadata
hosts/IPs (blocked unconditionally), and by default no loopback/private/
link-local/reserved addresses (an `allow_private_targets` flag exists solely
for pointing tests at a local fixture server; production callers never set
it). Redirects are followed manually, one hop at a time, so each hop is
re-validated and cross-origin redirects are not followed. robots.txt failures
(timeout/HTTP error/undecodable body) make the crawl conservative rather than
assuming permission -- see `acquire_site.py`'s `_robots_policy`. Response
bodies are streamed and truncated against `MAX_TOTAL_BYTES` during download,
not after.
