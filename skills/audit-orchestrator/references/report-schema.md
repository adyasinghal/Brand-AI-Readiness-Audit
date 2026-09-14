# Report schema

Top-level: site, audited_at, summary (total_findings, critical, high, medium,
low, proactive_improvements, insufficient_evidence_items), coverage
(pages_discovered, pages_analyzed, pages_skipped, rendered_pages,
external_claims_checked, external_footprint_queries, external_fetches,
identity_confidence, memory_budget_used_mb, runtime_seconds,
deadline_reached), warnings, findings (see finding-schema.md).


Every finding and recommendation also exposes a stable `check_id`, `mechanism`,
`implementation_detail` and `expected_outcome` from common/check_catalog.py.
Merged findings include `check_ids` for all contributing rules. Per-report `id`
is unchanged. The action object mirrors the two catalog action-detail fields.
Missing catalog entries are rejected on the public audit path. These fields do
not replace the observed root cause, evidence, status or affected-page list.


Transport diagnostics: coverage includes transport_diagnostics, transport_environment,
robots_attempt_outcomes and robots_permission. Failed robots acquisition means
permission unknown, zero inferred blocks and degraded execution. Exact TLS
verification details and recovered attempt outcomes are retained separately from
site findings. An HTTP status is not a TLS error.
